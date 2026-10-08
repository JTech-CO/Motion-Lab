"""Bounded GL Transitions importer: explicit per-file MIT, immutable sources, no execution."""

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser

ROOT = Path(__file__).resolve().parent.parent
LOCAL = ROOT / "data" / "upstream" / "gl-transitions"
REPOSITORY = "gl-transitions/gl-transitions"
ALLOWED_HOSTS = {"api.github.com", "raw.githubusercontent.com"}
USER_AGENT = "MotionLab/1.0 (public motion research; licensed GLSL only; no video)"
MAX_BYTES = 128 * 1024
MAX_FILES = 200
REQUEST_INTERVAL = 1.25  # Maximum 48 requests/minute across both workers.
VERIFIED_DATE = "2026-10-08"
HOST_DESCRIPTION_KO = "GL Transitions의 원본 GLSL 전환 함수입니다. 두 텍스처(from/to)를 progress 값으로 전환합니다. Motion Lab 미리보기는 로컬에서 만든 테스트 이미지 A/B에 원본 셰이더를 적용합니다. 원작품의 이미지나 영상은 포함하지 않으며, 다른 프로젝트에서는 WebGL 호스트의 함수·uniform 연결이 필요합니다."
HOST_PREVIEW_NOTE = "Actual GLSL preview uses locally generated test images A/B; original artwork images are not included. Collection and analysis do not execute shaders."


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *_args, **_kwargs):
        return None


class Collector:
    def __init__(self):
        self.robots = {}
        self.requests = []
        self.lock = threading.Lock()
        self.next_request = 0.0
        self.interval = REQUEST_INTERVAL
        self.stopped = threading.Event()
        self.opener = urllib.request.build_opener(NoRedirect())

    def request(self, url, *, robots_request=False):
        if self.stopped.is_set():
            raise ValueError("Collection stopped after an upstream access/rate block")
        parts = urllib.parse.urlsplit(url)
        if (parts.scheme != "https" or parts.hostname not in ALLOWED_HOSTS or parts.port not in (None, 443)
                or parts.username or parts.password):
            raise ValueError("Source URL is outside registered HTTPS hosts")
        if not robots_request:
            policy = self.robots.get(parts.hostname)
            if not policy or policy["status"] == "unavailable":
                raise ValueError("robots.txt unavailable: automatic collection stops")
            if policy.get("parser") and not policy["parser"].can_fetch(USER_AGENT, url):
                raise ValueError("robots.txt disallows this source: automatic collection stops")
            if parts.hostname == "raw.githubusercontent.com" and not parts.path.startswith("/" + REPOSITORY + "/"):
                raise ValueError("Raw path is outside registered repository")
            if parts.hostname == "api.github.com" and not parts.path.startswith("/repos/" + REPOSITORY + "/git/"):
                raise ValueError("API path is outside registered repository")
        with self.lock:
            delay = max(0.0, self.next_request - time.monotonic())
            self.next_request = time.monotonic() + delay + self.interval
        if delay:
            time.sleep(delay)
        if self.stopped.is_set():
            raise ValueError("Collection stopped after an upstream access/rate block")
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT,
                                         "Accept": "application/json,text/plain;q=0.9"})
        try:
            with self.opener.open(request, timeout=25) as response:
                body = response.read(MAX_BYTES + 1)
                if len(body) > MAX_BYTES:
                    raise ValueError("Source exceeds the 128 KiB request limit")
                record = {"url": url, "status": response.status, "bytes": len(body),
                          "sha256": hashlib.sha256(body).hexdigest()}
                with self.lock:
                    self.requests.append(record)
                return body
        except urllib.error.HTTPError as error:
            if error.code in (401, 403, 429):
                self.stopped.set()
            with self.lock:
                self.requests.append({"url": url, "status": error.code, "error": "HTTPError"})
            raise
        except (OSError, ValueError) as error:
            with self.lock:
                self.requests.append({"url": url, "status": "failed", "error": str(error)[:300]})
            raise

    def check_robots(self, host):
        url = "https://" + host + "/robots.txt"
        try:
            body = self.request(url, robots_request=True)
            (LOCAL / ("robots-" + host + ".txt")).write_bytes(body)
            parser = urllib.robotparser.RobotFileParser(url)
            parser.parse(body.decode("utf-8", errors="replace").splitlines())
            crawl_delay = parser.crawl_delay(USER_AGENT) or parser.crawl_delay("*")
            request_rate = parser.request_rate(USER_AGENT) or parser.request_rate("*")
            if crawl_delay:
                self.interval = max(self.interval, float(crawl_delay))
            if request_rate and request_rate.requests > 0:
                self.interval = max(self.interval, request_rate.seconds / request_rate.requests)
            self.robots[host] = {"status": "reviewed", "url": url, "parser": parser,
                                 "sha256": hashlib.sha256(body).hexdigest(), "minimumRequestInterval": self.interval}
        except urllib.error.HTTPError as error:
            # RFC 9309: absent robots is different from a crawler block.
            self.robots[host] = {"status": "absent" if error.code in (404, 410) else "unavailable",
                                 "url": url, "httpStatus": error.code}
        except (OSError, ValueError) as error:
            self.robots[host] = {"status": "unavailable", "url": url, "error": str(error)[:300]}


def save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def safe_glsl_path(value):
    if not isinstance(value, str) or not value.startswith("transitions/") or not value.endswith(".glsl"):
        raise ValueError("Unexpected upstream GLSL path")
    path = PurePosixPath(value)
    if len(path.parts) != 2 or path.name.startswith(".") or not re.fullmatch(r"[A-Za-z0-9_.-]+\.glsl", path.name):
        raise ValueError("Unsafe upstream GLSL filename")
    return path


def header_notice(code):
    """Preserve exact leading comment notices; never interpret or execute GLSL."""
    match = re.match(r"\A(?:\s+|//[^\n]*(?:\n|$)|/\*[\s\S]*?\*/)*", code)
    return match.group(0).strip() if match else ""


def make_item(path, code, sha, body_sha, repo_license):
    safe = safe_glsl_path(path)
    notice = header_notice(code)
    labels = re.findall(r"(?im)^\s*(?://\s*|\*\s*)?License\s*:\s*([^\r\n]+)", notice)
    if not labels or any(not re.fullmatch(r"MIT(?:\s+License)?\.?", label.strip(), re.I) for label in labels):
        return None, "missing-or-non-MIT-file-license"
    name = safe.stem
    words = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", name).replace("_", " ").replace("-", " ").split()
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    url = f"https://github.com/{REPOSITORY}/blob/{sha}/{path}"
    license_url = f"https://github.com/{REPOSITORY}/blob/{sha}/LICENSE"
    authors = re.findall(r"(?im)^\s*(?://\s*|\*\s*)?Author\s*:\s*([^\r\n]+)", notice)
    item = {"id": "gl-transitions-" + slug, "title": name,
            "description": HOST_DESCRIPTION_KO,
            "category": "transition", "tags": list(dict.fromkeys(["glsl", "webgl", "transition", "shader", "전환", "셰이더"] + [word.lower() for word in words])),
            "sourceUrl": url, "sourceName": "GL Transitions", "license": "MIT", "licenseUrl": url,
            "repositoryLicenseUrl": license_url, "licenseText": repo_license,
            "fileNotice": notice, "authors": authors,
            "licenseNote": "원본 파일의 MIT 선언과 저자/저작권 주석, 저장소 MIT 고지를 보존하세요. 파일별 라이선스 선언을 확인한 원본만 수록합니다.",
            "verifiedAt": VERIFIED_DATE, "verification": "source-and-license-reviewed", "kind": "code",
            "preview": {"type": "reference", "variant": "grid", "note": HOST_PREVIEW_NOTE},
            "code": code, "colors": [], "language": "glsl", "access": "public",
            "upstreamCommit": sha, "upstreamSha256": body_sha,
            "codePath": "data/upstream/gl-transitions/" + path}
    return item, None


def prepare(collector):
    for host in sorted(ALLOWED_HOSTS):
        collector.check_robots(host)
    if any(info["status"] == "unavailable" for info in collector.robots.values()):
        raise ValueError("An upstream robots policy could not be reviewed; stopping")
    reference = json.loads(collector.request(f"https://api.github.com/repos/{REPOSITORY}/git/refs/heads/master"))
    sha = reference["object"]["sha"]
    if not re.fullmatch(r"[a-f0-9]{40}", sha):
        raise ValueError("Invalid upstream commit SHA")
    tree = json.loads(collector.request(f"https://api.github.com/repos/{REPOSITORY}/git/trees/{sha}?recursive=1"))
    if tree.get("truncated"):
        raise ValueError("Git tree is truncated; cannot audit complete bounded file list")
    selected = [entry for entry in tree["tree"] if entry.get("type") == "blob" and entry.get("path", "").endswith(".glsl")]
    selected = sorted(selected, key=lambda entry: entry["path"])
    if len(selected) > MAX_FILES:
        raise ValueError("Repository exceeds the 200-file collection bound")
    for entry in selected:
        safe_glsl_path(entry["path"])
        if entry.get("size", MAX_BYTES + 1) > MAX_BYTES:
            raise ValueError("A shader exceeds the 128 KiB file bound")
    license_body = collector.request(f"https://raw.githubusercontent.com/{REPOSITORY}/{sha}/LICENSE")
    license_text = license_body.decode("utf-8")
    if "MIT License" not in license_text or "Permission is hereby granted, free of charge" not in license_text:
        raise ValueError("Repository MIT terms are not verified")
    manifest = {"repository": REPOSITORY, "commit": sha, "verifiedAt": VERIFIED_DATE,
                "licenseSha256": hashlib.sha256(license_body).hexdigest(), "treeFiles": selected, "files": []}
    save_json(LOCAL / "git-reference.json", reference)
    save_json(LOCAL / "git-tree.json", tree)
    (LOCAL / "LICENSE.txt").write_bytes(license_body)
    save_json(LOCAL / "manifest.json", manifest)
    return manifest, license_text


def report_for(manifest, collector, items, skipped, status):
    policy = [{key: value for key, value in info.items() if key != "parser"} for info in collector.robots.values()]
    sha = manifest["commit"]
    return {"collectedAt": datetime.now(timezone.utc).isoformat(), "verifiedAt": VERIFIED_DATE,
            "status": status, "repository": REPOSITORY, "commit": sha,
            "candidates": len(manifest["treeFiles"]), "imported": len(items), "skipped": skipped,
            "robots": policy, "requests": collector.requests,
            "bounds": {"maxFiles": MAX_FILES, "maxRequestBytes": MAX_BYTES, "workers": 2, "requestsPerMinute": 48},
            "sources": [{"id": "gl-transitions", "title": "GL Transitions", "repository": REPOSITORY,
                         "commit": sha, "sourceUrl": f"https://github.com/{REPOSITORY}", "license": "MIT",
                         "licenseUrl": f"https://github.com/{REPOSITORY}/blob/{sha}/LICENSE",
                         "licenseSha256": manifest["licenseSha256"], "verifiedAt": VERIFIED_DATE,
                         "method": "robots-reviewed-pinned-file-explicit-MIT", "items": len(items)}]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inspect", action="store_true", help="Read robots, commit, tree and repository terms only")
    parser.add_argument("--offline", action="store_true", help="Rebuild imported records from hash-verified local MIT snapshots")
    options = parser.parse_args()
    if options.inspect and options.offline:
        parser.error("--inspect and --offline cannot be combined")
    LOCAL.mkdir(parents=True, exist_ok=True)
    collector = Collector()
    if options.offline:
        manifest = json.loads((LOCAL / "manifest.json").read_text(encoding="utf-8"))
        license_body = (LOCAL / "LICENSE.txt").read_bytes()
        if hashlib.sha256(license_body).hexdigest() != manifest["licenseSha256"]:
            raise ValueError("Repository license snapshot hash mismatch")
        license_text = license_body.decode("utf-8")
        prior_report = json.loads((ROOT / "data" / "glsl-report.json").read_text(encoding="utf-8"))
        collector.requests = prior_report.get("requests", [])
        collector.robots = {urllib.parse.urlsplit(entry["url"]).hostname: entry for entry in prior_report.get("robots", [])}
    else:
        manifest, license_text = prepare(collector)
    items = []
    skipped = prior_report.get("skipped", []) if options.offline else []
    if options.inspect:
        report = report_for(manifest, collector, items, skipped, "inspected")
        save_json(ROOT / "data" / "glsl-report.json", report)
        print(json.dumps({"commit": manifest["commit"], "candidates": len(manifest["treeFiles"]), "robots": report["robots"]}, ensure_ascii=False), flush=True)
        return
    sha = manifest["commit"]

    def fetch(entry):
        path = entry["path"]
        safe_glsl_path(path)
        if options.offline:
            cached = (LOCAL / path).resolve()
            cached.relative_to(LOCAL.resolve())
            if cached.stat().st_size > MAX_BYTES:
                raise ValueError("Cached shader exceeds the 128 KiB file bound")
            body = cached.read_bytes()
            if hashlib.sha256(body).hexdigest() != entry["sha256"]:
                raise ValueError("Cached shader snapshot hash mismatch")
        else:
            body = collector.request(f"https://raw.githubusercontent.com/{REPOSITORY}/{sha}/{path}")
        body_sha = hashlib.sha256(body).hexdigest()
        code = body.decode("utf-8-sig")
        record, reason = make_item(path, code, sha, body_sha, license_text)
        if record is not None:
            local_path = LOCAL / path
            local_path.parent.mkdir(parents=True, exist_ok=True)
            if not options.offline:
                local_path.write_bytes(body)
            return record, {"path": path, "sha256": body_sha, "bytes": len(body)}, None
        declared = re.findall(r"(?im)^\s*(?://\s*|\*\s*)?License\s*:\s*([^\r\n]+)", code[:8192])
        return None, None, {"path": path, "reason": reason, "sha256": body_sha,
                            "declaredLicense": [label.strip()[:120] for label in declared],
                            "sourceUrl": f"https://github.com/{REPOSITORY}/blob/{sha}/{path}"}

    entries = manifest["files"] if options.offline else manifest["treeFiles"]
    successful = []
    with ThreadPoolExecutor(max_workers=2) as pool:
        pending = {pool.submit(fetch, entry): entry for entry in entries}
        for index, future in enumerate(as_completed(pending), 1):
            entry = pending[future]
            try:
                record, file_record, rejection = future.result()
                if record:
                    items.append(record)
                    successful.append(file_record)
                if rejection:
                    skipped.append(rejection)
            except (OSError, ValueError) as error:
                skipped.append({"path": entry["path"], "reason": str(error)[:300]})
            if index % 25 == 0 or index == len(entries):
                print(f"GLSL reviewed {index}/{len(entries)}; MIT imports {len(items)}; skipped {len(skipped)}", flush=True)
    items.sort(key=lambda entry: entry["id"])
    manifest["files"] = sorted(successful, key=lambda entry: entry["path"])
    save_json(LOCAL / "manifest.json", manifest)
    save_json(ROOT / "data" / "glsl-items.json", items)
    report = report_for(manifest, collector, items, skipped, "offline-rebuilt" if options.offline else "collected")
    if options.offline:
        report["collectedAt"] = prior_report["collectedAt"]
        report["rebuiltAt"] = datetime.now(timezone.utc).isoformat()
    save_json(ROOT / "data" / "glsl-report.json", report)
    notices = ["GL Transitions pinned MIT source notices", f"Repository: {REPOSITORY}", f"Commit: {sha}", "", license_text]
    for entry in items:
        notices.extend(["", "---", entry["title"], entry["sourceUrl"], "", entry["fileNotice"]])
    (ROOT / "dist" / "licenses").mkdir(parents=True, exist_ok=True)
    (ROOT / "dist" / "licenses" / "gl-transitions.txt").write_text("\n".join(notices), encoding="utf-8", newline="\n")
    print(json.dumps({"imported": len(items), "skipped": len(skipped), "commit": sha}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError) as error:
        print(f"GLSL import stopped: {error}", file=sys.stderr)
        sys.exit(1)
