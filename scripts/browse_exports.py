"""Build a discovery index and bounded, lossless source shards for the website."""

import hashlib
import json
import os
from pathlib import Path
import re
import stat
import tempfile

from scripts.package import checked_path

MAX_BROWSE_BYTES = 32 * 1024 * 1024
MAX_DETAIL_BYTES = 512 * 1024
MAX_DETAIL_ITEMS = 64
DETAIL_NAME = re.compile(r"[a-f0-9]{64}\.json")
HOME_TRANSITION_ID = "gl-transitions-drop-zone-flicker"


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")


def strings(value, maximum=40):
    return [entry for entry in value if isinstance(entry, str)][:maximum] if isinstance(value, list) else []


def text(value, maximum=4000):
    return value[:maximum] if isinstance(value, str) else ""


def searchable_text(entry):
    """Preserve every original field searched by the browser, without its code."""
    analysis = entry.get("analysis") or {}
    review = entry.get("referenceReview") if entry.get("kind") == "reference" else None
    if review:
        analysis = {**analysis, **{key: review.get(key) for key in
                                 ("assetType", "effects", "components", "useCases", "evidence")}}
    evidence = analysis.get("evidence") or {}
    values = [text(entry.get("title")), text(entry.get("description"), 6000),
              text(entry.get("sourceName")), text(entry.get("id")), text(entry.get("license")),
              text(entry.get("language")), " ".join(strings(entry.get("tags"))),
              " ".join(strings(entry.get("aliases"), 1000))]
    for original in (entry.get("variants") or [])[:64]:
        values.extend((text(original.get("id")), text(original.get("title")),
                       text(original.get("description"), 6000), text(original.get("sourceName")),
                       text(original.get("license")), " ".join(strings(original.get("tags")))))
    values.extend((" ".join(strings(analysis.get("properties"), 120)),
                   " ".join(strings(analysis.get("techniques"))),
                   " ".join(strings(evidence.get("signals"), 120))))
    if review:
        values.extend(text((review.get("evidence") or {}).get(key), 6000)
                      for key in ("summaryKO", "summaryEN"))
    return " ".join(values)


def reference_preview_domain(preview, by_id):
    """Use the same motion test as the browser's complete reference preview."""
    if preview.get("mode") == "related-asset":
        asset = by_id.get(preview.get("assetId"))
        domain = asset.get("analysis", {}).get("domain") if asset else None
        if not asset or asset.get("kind") == "reference" or domain not in ("motion", "design"):
            raise ValueError("A browser reference preview has no classified local asset")
        return domain
    code = preview.get("code") or ""
    pattern = (r"<(?:animate|animateTransform|set)\b" if preview.get("language") == "svg"
               else r"@keyframes\b|(?:animation|transition)(?:-[a-z-]+)?\s*:")
    return "motion" if re.search(pattern, code) else "design"


def browse_entry(entry, shard, by_id):
    fields = ("id", "title", "category", "sourceUrl", "sourceName", "license", "kind", "language")
    item = {key: entry[key] for key in fields}
    analysis = entry["analysis"]
    item["domain"] = analysis["domain"]
    item["analysis"] = {key: analysis[key] for key in
                        ("domain", "assetType", "effects", "components", "useCases", "techniques")}
    item["analysis"]["evidence"] = {key: analysis["evidence"][key] for key in ("basis", "confidence")}
    if entry.get("referenceReview"):
        review = entry["referenceReview"]
        item["referenceReview"] = {key: review[key] for key in
                                   ("targetDomain", "resourceType", "assetType", "effects", "components", "useCases")}
        item["referenceReview"]["evidence"] = {key: review["evidence"][key]
                                               for key in ("basis", "confidence")}
        item["referenceReview"]["preview"] = {key: value for key, value in review["preview"].items()
                                              if key in ("mode", "assetId")}
        item["referenceReview"]["preview"]["domain"] = reference_preview_domain(review["preview"], by_id)
    if entry.get("variants"):
        item["aliases"] = entry["aliases"]
        item["variantCount"] = entry["consolidation"]["variantCount"]
    item["searchText"] = searchable_text(entry)
    item["detailShard"] = shard
    return item


def browse_documents(catalog):
    """Content-address each complete source body; never discard source fields."""
    items, shards, manifest = [], {}, []
    by_id = {entry["id"]: entry for entry in catalog["items"]}
    batch, batch_bytes = [], len(b'{"version":1,"items":[]}\n')

    def flush():
        nonlocal batch, batch_bytes
        if not batch:
            return
        body = b'{"version":1,"items":[' + b",".join(body for _, body in batch) + b"]}\n"
        digest = hashlib.sha256(body).hexdigest()
        path = "catalog-details/" + digest + ".json"
        shards[path] = body
        manifest.append({"path": path, "sha256": digest, "bytes": len(body), "count": len(batch)})
        items.extend(browse_entry(entry, path, by_id) for entry, _ in batch)
        batch, batch_bytes = [], len(b'{"version":1,"items":[]}\n')

    for entry in catalog["items"]:
        body = json_bytes(entry).rstrip(b"\n")
        if len(body) + len(b'{"version":1,"items":[]}\n') > MAX_DETAIL_BYTES:
            raise ValueError("A source record exceeds the browser detail size limit: " + entry["id"])
        required = len(body) + bool(batch)
        if batch and (len(batch) >= MAX_DETAIL_ITEMS or batch_bytes + required > MAX_DETAIL_BYTES):
            flush()
        batch_bytes += len(body) + bool(batch)
        batch.append((entry, body))
    flush()
    browse = {"version": catalog["version"], "browseVersion": 1, "updatedAt": catalog["updatedAt"],
              "stats": catalog["stats"], "sources": catalog["sources"],
              "aliases": catalog.get("aliases", {}), "items": items, "detailShards": manifest,
              "detailMaxBytes": MAX_DETAIL_BYTES, "detailMaxItems": MAX_DETAIL_ITEMS}
    browse_body = json_bytes(browse)
    if len(browse_body) > MAX_BROWSE_BYTES:
        raise ValueError("The browser discovery index exceeds its size limit")
    transition = next((entry for entry in catalog["items"] if entry["id"] == HOME_TRANSITION_ID), None)
    return browse_body, shards, json_bytes({"version": 1, "item": transition})


def detail_files(root):
    """Only generated, ordinary content-addressed files can be replaced or removed."""
    root = Path(root).absolute()
    directory = root / "dist/catalog-details"
    info = checked_path(directory, root, missing=True)
    if info is None:
        return {}
    if not stat.S_ISDIR(info.st_mode):
        raise ValueError("Browser detail output must be an ordinary directory")
    files = {}
    for path in directory.iterdir():
        info = checked_path(path, root)
        if not DETAIL_NAME.fullmatch(path.name) or not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise ValueError("Browser detail output contains an unexpected or linked file")
        files[path.relative_to(root / "dist").as_posix()] = path
    return files


def write_bytes(root, path, body):
    checked_path(path.parent, root)
    info = checked_path(path, root, missing=True)
    if info is not None and (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1):
        raise ValueError("Browser export must be an ordinary file without links")
    if info is not None and path.read_bytes() == body:
        return
    handle, temporary = tempfile.mkstemp(prefix=".motionlab-browse-", suffix=".json", dir=path.parent)
    try:
        with os.fdopen(handle, "wb") as stream:
            stream.write(body)
        checked_path(path, root, missing=True)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def write_browse_exports(root, catalog):
    root = Path(root).absolute()
    existing = detail_files(root)
    browse, shards, transition = browse_documents(catalog)
    distribution = root / "dist"
    checked_path(distribution, root)
    directory = distribution / "catalog-details"
    directory.mkdir(exist_ok=True)
    checked_path(directory, root)
    for path, body in shards.items():
        write_bytes(root, distribution / path, body)
    write_bytes(root, distribution / "home-transition.json", transition)
    write_bytes(root, distribution / "catalog-browse.json", browse)
    # Content hashes change with source edits. Keep only this build's exact shards.
    for name in existing.keys() - shards.keys():
        path = existing[name]
        info = checked_path(path, root)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise ValueError("Browser detail output changed during cleanup")
        path.unlink()


def verify_browse_exports(root, catalog):
    root = Path(root).absolute()
    browse, shards, transition = browse_documents(catalog)
    distribution = root / "dist"
    for name, expected in (("catalog-browse.json", browse), ("home-transition.json", transition)):
        path = distribution / name
        info = checked_path(path, root)
        maximum = MAX_BROWSE_BYTES if name == "catalog-browse.json" else MAX_DETAIL_BYTES
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > maximum:
            raise ValueError("Invalid or oversized browser export")
        if path.read_bytes() != expected:
            raise ValueError("Browser search, facets, source routing or homepage source differs from the full catalog")
    files = detail_files(root)
    if files.keys() != shards.keys():
        raise ValueError("Browser source shards are missing or stale")
    for name, expected in shards.items():
        info = checked_path(files[name], root)
        if info.st_size > MAX_DETAIL_BYTES or files[name].read_bytes() != expected:
            raise ValueError("Browser source shard changed code, previews, variants, evidence or license notices")
    return {"browseBytes": len(browse), "detailBytes": sum(map(len, shards.values())),
            "detailShards": len(shards), "maximumDetailBytes": max(map(len, shards.values()), default=0),
            "homeTransitionBytes": len(transition)}
