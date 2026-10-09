"""Collect CC0 1K color maps, one conservative surface family per record.

No renderer thumbnails, PBR auxiliary maps, size variants or generated surface
variants are counted as assets. Remote scripts are never executed. Downloads
are serialized, bounded, pinned by content digest and safe to rebuild offline.
"""

import argparse
from collections import Counter
import hashlib
import io
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
import warnings
import zipfile

import numpy as np
from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from motionlab.image_assets import validate_image

LOCAL = ROOT / "data/upstream/phase2-materials"
OUTPUT = ROOT / "data/phase2-material-items.json"
MANIFEST = LOCAL / "manifest.json"
DATE = "2026-10-09"
INTERVAL = 1.25
MAX_METADATA = 16 * 1024 * 1024
MAX_ARCHIVE = 32 * 1024 * 1024
MAX_IMAGE = 4 * 1024 * 1024
MAX_TOTAL_ORIGINALS = 768 * 1024 * 1024
MAX_CANDIDATES = 3000
POLICY_VERSION = 4
DECISIONS = LOCAL / "decisions.json"
REVIEWED_AMBIENT_EQUIVALENTS = {
    # First-party 1K color-map contact sheet reviewed on 2026-10-09.
    # These regular running-bond surfaces repeat a clean small brick grid;
    # their main visible differences are color and the scale of the crop.
    "Bricks009": "Bricks006", "Bricks010": "Bricks006", "Bricks017": "Bricks006",
    "Bricks053": "Bricks006", "Bricks086": "Bricks006", "Bricks101": "Bricks006",
    "Bricks025": "Bricks004", "Bricks051": "Bricks004", "Bricks092": "Bricks004",
    "Tiles004": "Tiles003", "Tiles073": "Tiles003", "Tiles132A": "Tiles003",
    "Tiles018": "Tiles017", "Tiles074": "Tiles012",
    "Wood041": "WoodFloor007", "WoodFloor051": "WoodFloor007",
    "WoodFloor071": "WoodFloor030",
}
REVIEWED_POLY_EQUIVALENTS = {
    # Regular clean running-bond brick and plain long plank grids vary mainly
    # by tint, rotation and crop size. Distressed and irregular surfaces remain.
    "dark_brick_wall": "brick", "factory_brick": "brick", "large_red_bricks": "brick",
    "embedded_plank_flooring": "brick", "painted_brick": "brick",
    "japanese_cedar_planks": "brown_planks", "hinoki_planks": "brown_planks",
    "roof_planks": "brown_planks", "wooden_planks": "brown_planks",
    "stone_embedded_concrete": "rock_embedded_floor",
}
UA = "MotionLab/1.0 (+https://github.com/JTech-CO/Motion-Lab; CC0 material import)"
ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,100}\Z")
HOST_PATHS = {
    "ambientcg.com": ("/robots.txt", "/api/v3/assets", "/get"),
    "docs.ambientcg.com": ("/robots.txt", "/license/", "/api/", "/api/v3/assets/"),
    "api.polyhaven.com": ("/robots.txt", "/assets", "/files/"),
    "polyhaven.com": ("/robots.txt", "/license", "/our-api"),
    "dl.polyhaven.org": ("/robots.txt", "/file/ph-assets/Textures/"),
    "acg-download.struffelproductions.com": ("/robots.txt", "/file/ambientCG-Web/download/"),
    "creativecommons.org": ("/publicdomain/zero/1.0/legalcode.txt",),
    "raw.githubusercontent.com": ("/Poly-Haven/Public-API/master/ToS.md",),
}
POLICY_URLS = {
    "ambient-license.html": "https://docs.ambientcg.com/license/",
    "ambient-api.html": "https://docs.ambientcg.com/api/",
    "ambient-api-assets.html": "https://docs.ambientcg.com/api/v3/assets/",
    "poly-license.html": "https://polyhaven.com/license",
    "poly-api.html": "https://polyhaven.com/our-api",
    "poly-api-terms.md": "https://raw.githubusercontent.com/Poly-Haven/Public-API/master/ToS.md",
    "CC0-1.0.txt": "https://creativecommons.org/publicdomain/zero/1.0/legalcode.txt",
}


def sha256(body):
    return hashlib.sha256(body).hexdigest()


def save_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(prefix=".material-", suffix=".json", dir=path.parent)
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def local_path(relative):
    if not isinstance(relative, str) or not re.fullmatch(r"[A-Za-z0-9_./-]{1,240}", relative):
        raise ValueError("Unsupported local artifact path")
    if any(part in ("", ".", "..") for part in relative.split("/")):
        raise ValueError("Unsupported local artifact path")
    artifact_root = LOCAL.resolve()
    artifact_root.relative_to(ROOT.resolve())
    path = (artifact_root / relative).resolve()
    path.relative_to(artifact_root)
    return path


def checked_url(url):
    if not isinstance(url, str) or len(url) > 1200 or any(ord(c) < 32 for c in url):
        raise ValueError("Unsupported material URL")
    parsed = urllib.parse.urlsplit(url)
    prefixes = HOST_PATHS.get(parsed.hostname)
    if (parsed.scheme != "https" or parsed.username or parsed.password or parsed.fragment
            or parsed.port not in (None, 443) or not prefixes
            or not any(parsed.path == p or (p.endswith("/") and parsed.path.startswith(p)) for p in prefixes)
            or ".." in urllib.parse.unquote(parsed.path).split("/")):
        raise ValueError("Material URL is outside the source allowlist")
    return url


class NetworkStopped(RuntimeError):
    pass


class SafeRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, newurl):
        checked_url(newurl)
        return super().redirect_request(request, fp, code, message, headers, newurl)


class Collector:
    def __init__(self, offline=False):
        self.offline = offline
        self.artifacts = json.loads(MANIFEST.read_text(encoding="utf-8")).get("artifacts", {}) if MANIFEST.is_file() else {}
        self.last_request = 0.0
        self.robots = {}
        self.opener = urllib.request.build_opener(SafeRedirect())
        self.requests = 0

    def request(self, url, maximum, *, allow_missing=False):
        checked_url(url)
        if self.offline:
            raise FileNotFoundError("Artifact missing in offline mode")
        wait = INTERVAL - (time.monotonic() - self.last_request)
        if wait > 0:
            time.sleep(wait)
        self.last_request = time.monotonic()
        self.requests += 1
        try:
            with self.opener.open(urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Encoding": "identity"}), timeout=45) as response:
                checked_url(response.geturl())
                declared = response.headers.get("Content-Length", "")
                if declared.isdigit() and int(declared) > maximum:
                    raise ValueError("Remote artifact exceeds the bounded size")
                body = response.read(maximum + 1)
                if len(body) > maximum:
                    raise ValueError("Remote artifact exceeds the bounded size")
                return body
        except urllib.error.HTTPError as error:
            if error.code in (403, 429):
                raise NetworkStopped(f"Provider returned {error.code}; all network collection stopped") from error
            if allow_missing and error.code in (404, 410):
                return b""
            raise

    def artifact(self, relative, url, maximum, *, md5=None, allow_missing=False):
        checked_url(url)
        path = local_path(relative)
        registered = self.artifacts.get(relative)
        if path.is_file():
            if path.stat().st_size > maximum:
                raise ValueError("Cached artifact exceeds the bounded size")
            body = path.read_bytes()
            if registered and registered.get("url") == url and registered.get("sha256") == sha256(body) and len(body) <= maximum:
                return body
            raise ValueError("Cached artifact differs from its recorded provenance")
        body = self.request(url, maximum, allow_missing=allow_missing)
        if md5 and hashlib.md5(body).hexdigest() != md5:
            raise ValueError("Downloaded source differs from the provider checksum")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body)
        self.artifacts[relative] = {"url": url, "sha256": sha256(body), "bytes": len(body)}
        return body

    def check_robots(self, host):
        relative = f"policy/robots-{host}.txt"
        body = self.artifact(relative, f"https://{host}/robots.txt", 64 * 1024, allow_missing=True)
        parser = urllib.robotparser.RobotFileParser()
        parser.parse(body.decode("utf-8", "replace").splitlines())
        self.robots[host] = parser
        return parser

    def flush(self):
        save_json(MANIFEST, {"version": 1, "updatedAt": DATE, "userAgent": UA, "intervalSeconds": INTERVAL,
                             "artifacts": self.artifacts})


def material_families(ambient, poly):
    """Conservative grouping, including common Substance source generators."""
    parents = {item["id"]: item["id"] for item in ambient}
    def find(key):
        while key != parents[key]:
            parents[key] = parents[parents[key]]
            key = parents[key]
        return key
    def union(a, b):
        if a in parents and b in parents:
            left, right = sorted((find(a), find(b)))
            parents[right] = left
    source_groups = {}
    for variant, canonical in REVIEWED_AMBIENT_EQUIVALENTS.items():
        union(variant, canonical)
    for item in ambient:
        name = item["id"]
        relations = item.get("relations", {})
        for variation in relations.get("variations", []):
            union(name, variation if isinstance(variation, str) else variation.get("id", ""))
        # Alphabetic surface variants are never separate cards.
        base = re.sub(r"(?<=\d)[A-Za-z]+$", "", name)
        if base in source_groups:
            union(name, source_groups[base])
        source_groups[base] = name
        generators = tuple(sorted(relations.get("parents", [])))
        if generators:
            key = ("generator", generators)
            if key in source_groups:
                union(name, source_groups[key])
            source_groups[key] = name
    groups = {}
    for item in ambient:
        groups.setdefault(("ambientcg", find(item["id"])), []).append(item)
    # Numeric suffices on a photographed surface are neighboring samples.
    for name, item in sorted(poly.items()):
        base = re.sub(r"(?:_\d+|\d+)$", "", name)
        base = REVIEWED_POLY_EQUIVALENTS.get(base, base)
        groups.setdefault(("polyhaven", base), []).append({"id": name, **item})
    return [{"provider": key[0], "family": key[1], "members": sorted(members, key=lambda x: x["id"])}
            for key, members in sorted(groups.items())]


def decode_image(body):
    if len(body) > MAX_IMAGE or not (body.startswith(b"\xff\xd8\xff") or body.startswith(b"\x89PNG\r\n\x1a\n")
                                   or body[:4] == b"RIFF" and body[8:12] == b"WEBP"):
        raise ValueError("Color map has unsupported image magic or size")
    with warnings.catch_warnings():
        warnings.simplefilter("error", Image.DecompressionBombWarning)
        with Image.open(io.BytesIO(body)) as image:
            if image.format not in ("JPEG", "PNG", "WEBP") or getattr(image, "n_frames", 1) != 1:
                raise ValueError("Only one static color map is supported")
            if not 32 <= image.width <= 4096 or not 32 <= image.height <= 4096 or image.width * image.height > 4_194_304:
                raise ValueError("Color map exceeds pixel bounds")
            image.load()
            return ImageOps.exif_transpose(image).convert("RGB")


def extract_color_map(body, name):
    """Read only a bounded color entry; never extract ZIP paths to disk."""
    with zipfile.ZipFile(io.BytesIO(body)) as archive:
        infos = archive.infolist()
        if len(infos) > 100 or sum(i.file_size for i in infos) > 64 * 1024 * 1024:
            raise ValueError("Material archive exceeds bounds")
        selected = [entry for entry in infos if re.fullmatch(re.escape(name) + r"_1K(?:-JPG)?_(?:Color|Diffuse)\.(?:jpg|png)", entry.filename)]
        if len(selected) != 1:
            raise ValueError("Material archive has no unambiguous 1K color map")
        entry = selected[0]
        if (entry.file_size > MAX_IMAGE or entry.flag_bits & 1 or entry.compress_size == 0
                or entry.file_size > max(100_000, entry.compress_size * 200)):
            raise ValueError("Unsafe material archive entry")
        return entry.filename, archive.read(entry)


def image_features(image):
    """Geometry hashes plus color/texture statistics, including tile rotations."""
    small = np.asarray(image.resize((64, 64), Image.Resampling.LANCZOS), dtype=np.float64) / 255.0
    gray = np.dot(small, [0.299, 0.587, 0.114])
    n = 32
    transform = np.cos(np.pi * (2 * np.arange(n)[None, :] + 1) * np.arange(8)[:, None] / (2 * n))
    hashes = []
    for mirrored in (gray, np.fliplr(gray)):
        for rotation in range(4):
            thumb = np.asarray(Image.fromarray((np.rot90(mirrored, rotation) * 255).astype(np.uint8)).resize((n, n)), dtype=np.float64)
            coefficients = (transform @ thumb @ transform.T).flatten()[1:]
            bits = coefficients > np.median(coefficients)
            hashes.append(sum(int(value) << index for index, value in enumerate(bits)))
    quantiles = np.quantile(small.reshape(-1, 3), [0.05, 0.25, 0.5, 0.75, 0.95], axis=0).ravel()
    power = np.abs(np.fft.fftshift(np.fft.fft2(gray - gray.mean()))) ** 2
    yy, xx = np.indices(power.shape)
    radius = np.sqrt((xx - 32) ** 2 + (yy - 32) ** 2)
    spectrum = np.asarray([power[(radius >= low) & (radius < high)].sum()
                           for low, high in zip([1, 2, 4, 8, 12, 18, 26], [2, 4, 8, 12, 18, 26, 46])])
    spectrum = spectrum / max(spectrum.sum(), 1e-12)
    edge = float(np.mean(np.abs(np.diff(gray, axis=0))) + np.mean(np.abs(np.diff(gray, axis=1))))
    gray_quantiles = np.quantile(gray, [0.05, 0.25, 0.5, 0.75, 0.95])
    return {"hashes": hashes, "quantiles": quantiles.tolist(), "grayQuantiles": (gray_quantiles - gray_quantiles[2]).tolist(), "spectrum": spectrum.tolist(), "edge": edge,
            "mean": small.mean(axis=(0, 1)).tolist()}


def near_image(left, right):
    color = float(np.max(np.abs(np.asarray(left["quantiles"]) - right["quantiles"])))
    contrast = float(np.max(np.abs(np.asarray(left["grayQuantiles"]) - right["grayQuantiles"])))
    if color > 0.075 and contrast > 0.04:
        return None
    spectrum = float(np.sum(np.abs(np.asarray(left["spectrum"]) - right["spectrum"])))
    hamming = min((a ^ b).bit_count() for a in left["hashes"] for b in right["hashes"])
    if hamming <= 8 and (color <= 0.075 or contrast <= 0.04):
        return "perceptual-geometry"
    if (np.ptp(left["grayQuantiles"]) <= 0.08 and np.ptp(right["grayQuantiles"]) <= 0.08
            and contrast <= 0.025 and abs(left["edge"] - right["edge"]) <= 0.018):
        return "low-contrast-surface-family"
    # Catches near-isotropic texture crops whose positional hashes differ.
    if ((color <= 0.045 or contrast <= 0.035) and spectrum <= 0.18 and abs(left["edge"] - right["edge"]) <= 0.018
            and max(left["edge"], right["edge"]) <= 0.23):
        return "texture-statistics"
    return None


def inventories(collector):
    ambient = []
    for offset in range(0, 3000, 500):
        url = "https://ambientcg.com/api/v3/assets?" + urllib.parse.urlencode({
            "type": "material", "sort": "alphabet", "limit": 500, "offset": offset,
            "include": "type,relations,title,downloads,tags,technique"})
        page = json.loads(collector.artifact(f"metadata/ambient-{offset}.json", url, MAX_METADATA))
        if page["totalResults"] > MAX_CANDIDATES:
            raise ValueError("Material inventory exceeds the source bound")
        ambient.extend(page["assets"])
        if offset + 500 >= page["totalResults"]:
            break
    poly = json.loads(collector.artifact("metadata/poly-textures.json", "https://api.polyhaven.com/assets?type=textures", MAX_METADATA))
    if (len(poly) > MAX_CANDIDATES or len({item["id"] for item in ambient}) != len(ambient)
            or len(ambient) != page["totalResults"]
            or any(item.get("type") != "material" for item in ambient)
            or any(not isinstance(item, dict) or item.get("type") != 1 for item in poly.values())):
        raise ValueError("Invalid or oversized material inventory")
    for name in [item["id"] for item in ambient] + list(poly):
        if not ID_RE.fullmatch(name):
            raise ValueError("Unsupported provider material identifier")
    return ambient, poly


def source_color(collector, provider, item):
    name = item["id"]
    existing_relative = f"originals/{provider}/{name}.jpg"
    path = local_path(existing_relative)
    if path.is_file():
        metadata = collector.artifacts[existing_relative]
        return collector.artifact(existing_relative, metadata["url"], MAX_IMAGE), metadata
    if provider == "polyhaven":
        url = f"https://api.polyhaven.com/files/{name}"
        files = json.loads(collector.artifact(f"metadata/poly-files/{name}.json", url, 1024 * 1024))
        channels = [channel for channel in files if channel.lower() in ("diffuse", "diff", "color", "albedo")]
        if len(channels) != 1:
            raise ValueError("No unambiguous diffuse color channel")
        file = files[channels[0]].get("1k", {}).get("jpg")
        if not file or not isinstance(file.get("size"), int) or not 4 <= file["size"] <= MAX_IMAGE:
            raise ValueError("No bounded 1K JPEG color map")
        body = collector.artifact(existing_relative, checked_url(file["url"]), MAX_IMAGE, md5=file.get("md5"))
        metadata = collector.artifacts[existing_relative]
        metadata.update({"channel": channels[0], "providerMd5": file.get("md5"), "sourceResolution": "1K"})
        return body, metadata
    files = [entry for entry in item.get("downloads", []) if entry.get("attributes") == "1K-JPG" and entry.get("extension") == "zip"]
    if len(files) != 1 or not 4 <= files[0].get("size", 0) <= MAX_ARCHIVE:
        raise ValueError("No bounded 1K JPEG source pack")
    file = files[0]
    body = collector.request(checked_url(file["url"]), MAX_ARCHIVE)
    filename, color = extract_color_map(body, name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(color)
    metadata = {"url": file["url"], "sha256": sha256(color), "bytes": len(color), "channel": "Color",
                "sourceResolution": "1K", "archiveSha256": sha256(body), "archiveBytes": len(body), "archiveEntry": filename}
    collector.artifacts[existing_relative] = metadata
    return color, metadata


def prune_owned_orphans(records, collector):
    """Remove only reviewed importer-owned images after a completed build."""
    image_root = (ROOT / "dist/assets/materials").resolve()
    original_root = (LOCAL / "originals").resolve()
    image_root.relative_to(ROOT.resolve())
    original_root.relative_to(ROOT.resolve())
    kept_web = {(ROOT / "dist" / item["image"]["path"]).resolve() for item in records}
    kept_original = {(ROOT / item["provenance"]["originalPath"]).resolve() for item in records}
    targets = []
    for path in image_root.glob("phase2-material-*.jpg"):
        resolved = path.resolve()
        resolved.relative_to(image_root)
        if resolved not in kept_web:
            targets.append(resolved)
    for path in original_root.rglob("*.jpg"):
        resolved = path.resolve()
        resolved.relative_to(original_root)
        if resolved not in kept_original:
            targets.append(resolved)
            relative = resolved.relative_to(LOCAL.resolve()).as_posix()
            if relative in collector.artifacts:
                collector.artifacts[relative]["retained"] = False
    # All targets have been resolved and bounded before the first deletion.
    for path in targets:
        path.unlink()
    return len(targets)


def run(offline=False, limit=MAX_CANDIDATES):
    collector = Collector(offline)
    records, accepted_features, accepted_web_features, rejected, families = [], [], [], [], []
    decisions = json.loads(DECISIONS.read_text(encoding="utf-8")) if DECISIONS.is_file() else {}
    report = {"date": DATE, "policyVersion": POLICY_VERSION, "candidateFamilies": 0, "accepted": 0, "rejected": rejected,
              "countUnit": "One 1K diffuse/color surface family, not preview renders, PBR channels, resolutions, colors or neighboring samples",
              "similarityPolicy": "Explicit variations, shared Substance parents, reviewed repeating brick grids and numeric neighboring samples group first; rotation/mirror perceptual hashes and texture statistics compare every remaining original and stored JPEG globally.",
              "limitations": "No automated image distance proves semantic uniqueness. Highly similar texture statistics are conservatively excluded. Full PBR auxiliary channels remain available only from the original source link."}
    try:
        for name, url in POLICY_URLS.items():
            collector.artifact("policy/" + name, url, 512 * 1024)
        for host in ("ambientcg.com", "polyhaven.com", "api.polyhaven.com"):
            collector.check_robots(host)
        for url in ("https://ambientcg.com/api/v3/assets", "https://ambientcg.com/get", "https://api.polyhaven.com/assets", "https://api.polyhaven.com/files/example"):
            host = urllib.parse.urlsplit(url).hostname
            if not collector.robots[host].can_fetch(UA, url):
                raise NetworkStopped("Provider robots disallows the registered API path")
        license_text = local_path("policy/CC0-1.0.txt").read_text(encoding="utf-8")
        if "CC0 1.0 Universal" not in license_text or "Waiver" not in license_text:
            raise ValueError("The full CC0 legal code was not retrieved")
        ambient, poly = inventories(collector)
        families = material_families(ambient, poly)
        report.update({"rawAmbientMaterials": len(ambient), "rawPolyMaterials": len(poly), "candidateFamilies": len(families),
                       "removedMetadataFamilyVariants": len(ambient) + len(poly) - len(families)})
        save_json(LOCAL / "families.json", families)
        original_bytes = 0
        for family in families[:limit]:
            item = family["members"][0]
            provider, name = family["provider"], item["id"]
            decision_key = provider + "/" + name
            old_decision = decisions.get(decision_key)
            if (old_decision and old_decision.get("policyVersion") in (3, POLICY_VERSION)
                    and old_decision.get("status") == "rejected" and old_decision.get("features")):
                # Rejected full images are not distributed. Keep source digests,
                # bounded derived fingerprints and the conservative decision.
                rejected.append(old_decision["rejection"])
                continue
            try:
                body, source = source_color(collector, provider, item)
                image = decode_image(body)
                features = image_features(image)
                if features["edge"] <= 0.004 and np.ptp(features["grayQuantiles"]) <= 0.025:
                    rejection = {"provider": provider, "id": name, "reason": "near-flat-color-map"}
                    rejected.append(rejection)
                    decisions[decision_key] = {"policyVersion": POLICY_VERSION, "status": "rejected", "rejection": rejection, "features": features, "source": source}
                    original_path = local_path(f"originals/{provider}/{name}.jpg")
                    original_path.unlink()
                    source["retained"] = False
                    continue
                match = next(((record["id"], reason) for record, feature in zip(records, accepted_features)
                              if (reason := near_image(features, feature))), None)
                if match:
                    rejection = {"provider": provider, "id": name, "reason": match[1], "similarTo": match[0]}
                    rejected.append(rejection)
                    decisions[decision_key] = {"policyVersion": POLICY_VERSION, "status": "rejected", "rejection": rejection, "features": features, "source": source}
                    original_path = local_path(f"originals/{provider}/{name}.jpg")
                    original_path.unlink()
                    source["retained"] = False
                    continue
                identifier = "phase2-material-" + provider + "-" + name.lower().replace("_", "-")
                image.thumbnail((1024, 1024), Image.Resampling.LANCZOS)
                output = io.BytesIO()
                image.save(output, format="JPEG", quality=90, optimize=True, progressive=True, exif=b"")
                rendered = output.getvalue()
                web_features = image_features(decode_image(rendered))
                web_match = next(((record["id"], reason) for record, feature in zip(records, accepted_web_features)
                                  if (reason := near_image(web_features, feature))), None)
                if web_match:
                    rejection = {"provider": provider, "id": name, "reason": "stored-jpeg-" + web_match[1], "similarTo": web_match[0]}
                    rejected.append(rejection)
                    decisions[decision_key] = {"policyVersion": POLICY_VERSION, "status": "rejected", "rejection": rejection,
                                               "features": features, "webFeatures": web_features, "source": source}
                    local_path(f"originals/{provider}/{name}.jpg").unlink()
                    source["retained"] = False
                    continue
                original_bytes += len(body)
                if original_bytes > MAX_TOTAL_ORIGINALS:
                    raise NetworkStopped("Accepted material original byte budget reached")
                source["retained"] = True
                path = ROOT / "dist/assets/materials" / (identifier + ".jpg")
                path.resolve().relative_to(ROOT.resolve())
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(rendered)
                descriptor = {"path": "assets/materials/" + path.name, "mime": "image/jpeg", "width": image.width,
                              "height": image.height, "sha256": sha256(rendered), "sourceSha256": sha256(body)}
                validate_image(descriptor)
                provider_name = "ambientCG" if provider == "ambientcg" else "Poly Haven"
                title = item.get("title") or item.get("name") or name
                source_url = f"https://ambientcg.com/a/{name}" if provider == "ambientcg" else f"https://polyhaven.com/a/{name}"
                tag_source = item.get("tags", [])
                if isinstance(tag_source, str):
                    tag_source = tag_source.split(",")
                tags = [tag.strip()[:50] for tag in tag_source if isinstance(tag, str) and tag.strip()][:20]
                record = {"id": identifier, "title": title, "description": f"{provider_name} {title}: a CC0 1K {source['channel']} color map for static texture and material design. Auxiliary PBR channels are available at the original source.",
                          "category": "material", "domain": "design", "kind": "image", "language": "image", "license": "CC0-1.0",
                          "licenseText": license_text, "licenseUrl": "https://creativecommons.org/publicdomain/zero/1.0/",
                          "sourceName": provider_name, "sourceUrl": source_url, "projectUrl": "https://ambientcg.com/" if provider == "ambientcg" else "https://polyhaven.com/textures",
                          "tags": ["material", "texture", "design", "albedo", "cc0", *tags], "colors": [], "code": None, "codePath": None,
                          "image": descriptor, "preview": {"type": "image", "variant": "material"}, "access": "public", "updatedAt": DATE,
                          "verifiedAt": DATE, "verification": "official-api-cc0-original-color-map-and-conservative-family-reviewed",
                          "provenance": {"method": "official-api-1k-color-map", "originalPath": f"data/upstream/phase2-materials/originals/{provider}/{name}.jpg",
                                         "sourceArtifact": source, "family": family["family"], "variantIdsExcluded": [member["id"] for member in family["members"] if member["id"] != name],
                                         "licenseEvidence": "data/upstream/phase2-materials/policy/" + ("ambient-license.html" if provider == "ambientcg" else "poly-license.html")}}
                records.append(record)
                accepted_features.append(features)
                accepted_web_features.append(web_features)
                decisions[decision_key] = {"policyVersion": POLICY_VERSION, "status": "accepted", "source": source, "features": features, "webFeatures": web_features}
            except (ValueError, OSError, KeyError, zipfile.BadZipFile) as error:
                if isinstance(error, urllib.error.HTTPError) and error.code in (403, 429):
                    raise NetworkStopped(f"Provider returned {error.code}; collection stopped") from error
                rejected.append({"provider": provider, "id": name, "reason": str(error)[:160]})
            finally:
                if (len(records) + len(rejected)) % 10 == 0:
                    collector.flush()
                    save_json(DECISIONS, decisions)
                    if not offline:
                        save_json(OUTPUT, records)
                    print(json.dumps({"processed": len(records) + len(rejected), "accepted": len(records), "families": len(families)}, ensure_ascii=False), flush=True)
        report["completed"] = limit >= len(families)
    except NetworkStopped as error:
        report["completed"] = False
        report["networkStop"] = str(error)
    finally:
        if report.get("completed"):
            report["orphanImagesRemoved"] = prune_owned_orphans(records, collector)
            representatives = {family["provider"] + "/" + member["id"]:
                               family["provider"] + "/" + family["members"][0]["id"]
                               for family in families for member in family["members"]}
            included = {item["provenance"]["originalPath"].split("originals/", 1)[1].removesuffix(".jpg") for item in records}
            for key, decision in decisions.items():
                decision["includedInFinalCatalog"] = key in included
                source = decision.get("source")
                if isinstance(source, dict):
                    source["retained"] = key in included
                if key not in included and decision.get("status") == "accepted":
                    decision["status"] = "family-merged"
                    decision["mergedInto"] = representatives.get(key)
        collector.flush()
        save_json(DECISIONS, decisions)
        save_json(OUTPUT, records)
        report.update({"accepted": len(records), "requestsThisRun": collector.requests,
                       "acceptedOriginalBytes": sum(item["provenance"]["sourceArtifact"]["bytes"] for item in records),
                       "storedJpegBytes": sum((ROOT / "dist" / item["image"]["path"]).stat().st_size for item in records),
                       "acceptedOriginalBudgetBytes": MAX_TOTAL_ORIGINALS,
                       "retention": "Accepted original color maps retained; rejected images discarded after recording source hashes, fingerprints and family decisions. Offline replay preserves those conservative rejections.",
                       "acceptedByProvider": dict(Counter(item["sourceName"] for item in records)),
                       "rejectionsByReason": dict(Counter(item["reason"] for item in rejected))})
        save_json(LOCAL / "report.json", report)
        save_json(LOCAL / "features.json", {record["id"]: feature for record, feature in zip(records, accepted_features)})
        save_json(LOCAL / "web-features.json", {record["id"]: feature for record, feature in zip(records, accepted_web_features)})
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--limit", type=int, default=MAX_CANDIDATES)
    args = parser.parse_args()
    if not 1 <= args.limit <= MAX_CANDIDATES:
        parser.error("limit must be from 1 to 3000")
    result = run(args.offline, args.limit)
    print(json.dumps({key: value for key, value in result.items() if key != "rejected"}, ensure_ascii=False, indent=2))
