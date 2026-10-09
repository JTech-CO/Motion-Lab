"""Import commit-pinned static design assets; source programs are never executed.

Only allowlisted archive members are read. SVG data is parsed without scripting,
external references or XML entities. All original bytes, licenses, SHA-256 hashes
and rejected candidate reasons are retained for an offline reproducible rebuild.
"""
from __future__ import annotations

import argparse
import ast
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
from html import escape
import io
import json
import math
from pathlib import Path, PurePosixPath
import re
import tarfile
import time
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
LOCAL = ROOT / "data/upstream/phase2-design"
OUTPUT = ROOT / "data/phase2-design-items.json"
MANIFEST = LOCAL / "manifest.json"
REPORT = LOCAL / "report.json"
MAX_FILE = 2 * 1024 * 1024
MAX_SVG = 128 * 1024
MAX_ARCHIVE = 160 * 1024 * 1024
MAX_EXPANDED = 800 * 1024 * 1024
MAX_ENTRIES = 80_000
MAX_ITEMS = 12_000
DATE = "2026-10-09"
UA = "MotionLab/1.0 (licensed static design collection; no source execution)"
CCBY_SHA = "9ba9550ad48438d0836ddab3da480b3b69ffa0aac7b7878b5a0039e7ab429411"
SOURCES = {
    "tabler": {"repo": "tabler/tabler-icons", "commit": "a4ce1404bc6d24d3c365afe7b258d6bf6f48d62d", "name": "Tabler Icons", "license": "MIT", "notice": "LICENSE", "expected": 5184},
    "lucide": {"repo": "lucide-icons/lucide", "commit": "a04f228cd01185e09c188b7227b9600c08c565ec", "name": "Lucide", "license": "ISC + MIT", "notice": "LICENSE", "expected": 1870},
    "phosphor": {"repo": "phosphor-icons/core", "commit": "2b75f3ad12b420c9504ef05df8d2564a28f8500e", "name": "Phosphor Icons", "license": "MIT", "notice": "LICENSE", "expected": 1512},
    "coolshapes": {"repo": "realvjy/coolshapes-react", "commit": "e1ed6806c439b327863bfb93822d7c2255432610", "name": "Coolshapes", "license": "MIT", "notice": "LICENSE"},
    "cmcrameri": {"repo": "callumrollo/cmcrameri", "commit": "78f02a088fa3c4fb4cb8aa92bd8e52389ab9d09a", "name": "Scientific Colour Maps", "license": "MIT", "notice": "LICENSE.txt"},
    "cmocean": {"repo": "matplotlib/cmocean", "commit": "59c35002c3aa5296b65d9646e52604c627441eb6", "name": "cmocean", "license": "MIT", "notice": "LICENSE.txt"},
    "colorcet": {"repo": "holoviz/colorcet", "commit": "9f23c9659e81a3bd9b23c7bf874d5c9323f07c16", "name": "Colorcet", "license": "CC BY 4.0", "notice": "LICENSE.txt"},
    "wesanderson": {"repo": "karthik/wesanderson", "commit": "02e4129c185e9d3c49b05b580717f35be2eef5c3", "name": "Wes Anderson", "license": "MIT", "notice": "LICENSE"},
    "heropatterns": {"name": "Hero Patterns", "license": "CC BY 4.0", "notice": "CC-BY-4.0.txt", "url": "https://heropatterns.com/js/app.js", "sha256": "74163aa77c7f8be88129334d3484d1d6457b097e097922422f8981472ae57b5b"},
}


def digest(body):
    return hashlib.sha256(body).hexdigest()


def save_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def safe_path(path):
    if not isinstance(path, str) or len(path) > 240 or "\\" in path:
        raise ValueError("Invalid registered source path")
    value = PurePosixPath(path)
    if value.is_absolute() or not value.parts or any(p in ("", ".", "..") or not re.fullmatch(r"[A-Za-z0-9_.-]+", p) for p in value.parts):
        raise ValueError("Source path escapes its registered boundary")
    return value


def target_path(path):
    target = (LOCAL / safe_path(path)).resolve()
    target.relative_to(LOCAL.resolve())
    return target


def selected(slug, path):
    source = SOURCES[slug]
    if path in (source["notice"], "README.md", "DESCRIPTION"):
        return True
    patterns = {
        "tabler": r"icons/outline/[a-z0-9-]+\.svg",
        "lucide": r"icons/[a-z0-9-]+\.(?:svg|json)",
        "phosphor": r"assets/regular/[a-z0-9-]+\.svg",
        "coolshapes": r"(?:scripts/shapeData\.ts|src/shapes/[a-z]+/[0-9]+\.tsx|src/components/ShapeBase\.tsx)",
        "cmcrameri": r"cmcrameri/cmaps/[A-Za-z0-9_]+\.txt",
        "cmocean": r"cmocean/rgb/[a-z]+-rgb\.txt",
        "colorcet": r"colorcet/__init__\.py",
        "wesanderson": r"R/colors\.R",
    }
    return bool(re.fullmatch(patterns.get(slug, r"(?!)"), path))


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *_args, **_kwargs):
        return None


class Collector:
    def __init__(self):
        self.opener = urllib.request.build_opener(NoRedirect())
        self.requests = []
        self.robots = {}
        self.next_request = 0.0
        self.blocked = False

    def allowed(self, url, policy=False):
        parsed = urllib.parse.urlsplit(url)
        if parsed.scheme != "https" or parsed.hostname not in {"raw.githubusercontent.com", "codeload.github.com", "heropatterns.com"} or parsed.port not in (None, 443) or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("Only registered HTTPS source URLs are allowed")
        if policy:
            return parsed.path == "/robots.txt"
        valid = {"https://heropatterns.com/js/app.js", "https://heropatterns.com/"}
        valid.update(f"https://codeload.github.com/{v['repo']}/tar.gz/{v['commit']}" for v in SOURCES.values() if "repo" in v)
        return url in valid

    def get(self, url, maximum=MAX_FILE, policy=False):
        if not self.allowed(url, policy) or self.blocked:
            raise ValueError("Unregistered URL or collection stopped after an access block")
        host = urllib.parse.urlsplit(url).hostname
        if not policy:
            rules = self.robots.get(host)
            if not rules or rules["status"] == "unavailable" or (rules.get("parser") and not rules["parser"].can_fetch(UA, url)):
                raise ValueError("Automatic collection stopped by robots policy")
        time.sleep(max(0.0, self.next_request-time.monotonic()))
        self.next_request = time.monotonic() + 1.25
        try:
            with self.opener.open(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=60) as response:
                length = response.headers.get("Content-Length")
                if length and int(length) > maximum:
                    raise ValueError("Registered response exceeds its byte bound")
                body = response.read(maximum+1)
                if len(body) > maximum:
                    raise ValueError("Registered response exceeds its byte bound")
                self.requests.append({"url": url, "status": response.status, "bytes": len(body), "sha256": digest(body)})
                return body
        except urllib.error.HTTPError as error:
            self.requests.append({"url": url, "status": error.code})
            if error.code in (401, 403, 429):
                self.blocked = True
            raise

    def check_robots(self, host):
        url = f"https://{host}/robots.txt"
        try:
            body = self.get(url, policy=True)
            target_path("robots-"+host+".txt").write_bytes(body)
            parser = urllib.robotparser.RobotFileParser(url)
            parser.parse(body.decode("utf-8").splitlines())
            self.robots[host] = {"url": url, "status": "reviewed", "sha256": digest(body), "parser": parser}
        except urllib.error.HTTPError as error:
            self.robots[host] = {"url": url, "status": "absent" if error.code in (404, 410) else "unavailable", "httpStatus": error.code}
            if error.code not in (404, 410):
                raise


def record_artifact(slug, path, body, url):
    relative = slug+"/"+path
    target = target_path(relative)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(body)
    return {"path": path, "relativePath": relative, "artifactPath": "data/upstream/phase2-design/"+relative,
            "url": url, "bytes": len(body), "sha256": digest(body)}


def archive_members(slug, body):
    records, expanded, count = [], 0, 0
    source = SOURCES[slug]
    prefix = source["repo"].split("/")[-1]+"-"+source["commit"]+"/"
    with tarfile.open(fileobj=io.BytesIO(body), mode="r:gz") as archive:
        for member in archive:
            count += 1
            expanded += member.size
            if count > MAX_ENTRIES or expanded > MAX_EXPANDED:
                raise ValueError("Archive exceeds its expanded member/byte bounds")
            if member.name == prefix[:-1] and member.isdir():
                continue
            if not member.name.startswith(prefix):
                raise ValueError("Archive root does not match the registered source revision")
            path = member.name[len(prefix):]
            if member.isdir() or not path:
                continue
            if member.issym() or member.islnk() or not member.isfile():
                raise ValueError("Archive contains a nonregular source member")
            if not selected(slug, path):
                continue
            safe_path(path)
            bound = MAX_SVG if path.endswith(".svg") else MAX_FILE
            if member.size > bound:
                raise ValueError("Selected source artifact exceeds its byte bound")
            with archive.extractfile(member) as handle:
                content = handle.read(bound+1)
            if len(content) != member.size:
                raise ValueError("Archive member is incomplete")
            url = f"https://raw.githubusercontent.com/{source['repo']}/{source['commit']}/{path}"
            records.append(record_artifact(slug, path, content, url))
    if not any(a["path"] == source["notice"] for a in records):
        raise ValueError("Full source license is missing")
    expected = source.get("expected")
    if expected and sum(a["path"].endswith(".svg") for a in records) != expected:
        raise ValueError("Pinned SVG inventory differs from the reviewed candidate count")
    return sorted(records, key=lambda x:x["path"])


def fetch():
    LOCAL.mkdir(parents=True, exist_ok=True)
    collector = Collector()
    collector.check_robots("codeload.github.com")
    sources = []
    existing = json.loads(MANIFEST.read_text(encoding="utf-8")) if MANIFEST.is_file() else {}
    old = {s["slug"]:s for s in existing.get("sources", [])}
    for slug, source in SOURCES.items():
        if slug == "heropatterns":
            continue
        if slug in old:
            verify_source(old[slug])
            sources.append(old[slug])
            continue
        url = f"https://codeload.github.com/{source['repo']}/tar.gz/{source['commit']}"
        body = collector.get(url, MAX_ARCHIVE)
        artifacts = archive_members(slug, body)
        sources.append({**source, "slug": slug, "archive": {"url": url, "bytes": len(body), "sha256": digest(body)}, "artifacts": artifacts})
        save_json(MANIFEST, {"version": 1, "sources": sources, "robots": [{k:v for k,v in p.items() if k!="parser"} for p in collector.robots.values()], "requests": collector.requests})
        print(slug, len(artifacts), "verified artifacts", flush=True)
    if "heropatterns" in old:
        verify_source(old["heropatterns"])
        sources.append(old["heropatterns"])
    else:
        collector.check_robots("heropatterns.com")
        source = SOURCES["heropatterns"]
        body = collector.get(source["url"])
        if digest(body) != source["sha256"]:
            raise ValueError("Hero Patterns live file differs from the reviewed content hash; stop for a fresh review")
        page = collector.get("https://heropatterns.com/")
        if b"creativecommons.org/licenses/by/4.0" not in page:
            raise ValueError("First-party Hero Patterns attribution license is missing")
        terms = (ROOT/"data/upstream/color-wave/terms/CC-BY-4.0.txt").read_bytes()
        if digest(terms) != CCBY_SHA:
            raise ValueError("CC BY 4.0 full legal text differs from the verified notice")
        artifacts = [record_artifact("heropatterns", "app.js", body, source["url"]), record_artifact("heropatterns", "index.html", page, "https://heropatterns.com/"), record_artifact("heropatterns", "CC-BY-4.0.txt", terms, "https://creativecommons.org/licenses/by/4.0/legalcode.txt")]
        sources.append({**source, "slug": "heropatterns", "artifacts": artifacts})
    manifest = {"version":1, "sources":sources, "robots":[{k:v for k,v in p.items() if k!="parser"} for p in collector.robots.values()], "requests":collector.requests,
                "bounds":{"maxArchiveBytes":MAX_ARCHIVE,"maxExpandedBytes":MAX_EXPANDED,"maxMembers":MAX_ENTRIES,"maxFileBytes":MAX_FILE,"maxSvgBytes":MAX_SVG,"requestsPerMinute":48,"workers":1}}
    save_json(MANIFEST, manifest)
    return manifest


def verified_bytes(source, path):
    matches = [a for a in source["artifacts"] if a["path"] == path]
    if len(matches) != 1:
        raise ValueError("Missing or ambiguous source artifact")
    record = matches[0]
    if record["relativePath"] != source["slug"]+"/"+path:
        raise ValueError("Manifest path differs from its source identity")
    target = target_path(record["relativePath"])
    if target.stat().st_size > (MAX_SVG if path.endswith(".svg") else MAX_FILE):
        raise ValueError("Source artifact exceeds its bound")
    body = target.read_bytes()
    if len(body) != record["bytes"] or digest(body) != record["sha256"]:
        raise ValueError("Source artifact differs from its immutable hash")
    return body


def verify_source(source):
    registered = SOURCES.get(source.get("slug"))
    if not registered or any(source.get(k) != registered.get(k) for k in ("repo","commit","name","notice","license")):
        raise ValueError("Manifest source is outside the pinned registry")
    if len(source.get("artifacts",[])) > 11_000 or len({a["path"] for a in source["artifacts"]}) != len(source["artifacts"]):
        raise ValueError("Invalid source artifact inventory")
    if registered.get("expected") and sum(a["path"].endswith(".svg") for a in source["artifacts"])!=registered["expected"]:
        raise ValueError("Offline source manifest is missing reviewed original SVGs")
    for artifact in source["artifacts"]:
        if source["slug"] != "heropatterns" and not selected(source["slug"], artifact["path"]):
            raise ValueError("Unregistered artifact in manifest")
        if "repo" in source:
            expected_url=f"https://raw.githubusercontent.com/{source['repo']}/{source['commit']}/{artifact['path']}"
        else:
            expected_url={"app.js":"https://heropatterns.com/js/app.js","index.html":"https://heropatterns.com/","CC-BY-4.0.txt":"https://creativecommons.org/licenses/by/4.0/legalcode.txt"}.get(artifact["path"])
        if artifact["url"]!=expected_url or artifact["artifactPath"]!="data/upstream/phase2-design/"+artifact["relativePath"]:
            raise ValueError("Offline artifact provenance differs from its registered identity")
        verified_bytes(source, artifact["path"])
    if source["slug"]=="heropatterns" and digest(verified_bytes(source,"app.js"))!=registered["sha256"]:
        raise ValueError("Hero Patterns content differs from the reviewed source hash")
    text = verified_bytes(source, source["notice"]).decode("utf-8")
    if source["license"] == "MIT" and source["slug"] != "wesanderson" and not all(x in text for x in ("Permission is hereby granted", "THE SOFTWARE IS PROVIDED", "Copyright")):
        raise ValueError("Full MIT notice is missing")
    if source["license"] == "ISC + MIT" and not all(x in text for x in ("Permission to use", "THE SOFTWARE IS PROVIDED", "Feather")):
        raise ValueError("Full ISC/MIT third-party notices are missing")
    if source["slug"] == "wesanderson":
        declaration = verified_bytes(source,"DESCRIPTION").decode("utf-8")
        if "MIT + file LICENSE" not in declaration or "COPYRIGHT HOLDER" not in text:
            raise ValueError("R package MIT declaration or copyright holder is missing")
    return text


def baseline_records():
    snapshot=LOCAL/"baseline-comparison.json"
    snapshot_manifest=LOCAL/"baseline-comparison-manifest.json"
    if snapshot.is_file() and snapshot_manifest.is_file():
        metadata=json.loads(snapshot_manifest.read_text(encoding="utf-8"))
        raw=snapshot.read_bytes()
        if len(raw)>64*1024*1024 or digest(raw)!=metadata["sha256"]:
            raise ValueError("Original baseline comparison snapshot integrity mismatch")
        return json.loads(raw),metadata["catalogSha256"]
    raw = (ROOT/"data/catalog.json").read_bytes()
    document = json.loads(raw)
    records, seen = [], set()
    def add(item):
        fingerprint = (item["id"],digest(str(item.get("code",item.get("colors",[]))).encode()))
        if fingerprint not in seen:
            records.append(item)
            seen.add(fingerprint)
    for item in document["items"]:
        add(item)
        for variant in item.get("variants",[]):
            add(variant)
        original = item.get("repair",{}).get("originalRecord")
        if original:
            add(original)
    fields=("id","title","kind","language","category","colors","sourceName","code")
    compact=[]
    for item in records:
        record={k:item[k] for k in fields if k in item}
        if item.get("evidence",{}).get("component"):
            record["evidence"]={"component":item["evidence"]["component"]}
        compact.append(record)
    save_json(snapshot,compact)
    save_json(snapshot_manifest,{"catalogSha256":digest(raw),"sha256":digest(snapshot.read_bytes()),"originalAndRepairedRecords":len(records),"scope":"Original canonical, every merged original variant and repaired original body; only comparison fields retained"})
    return compact, digest(raw)


DRAWABLE = {"path","circle","ellipse","rect","line","polyline","polygon"}
SAFE_TAGS = DRAWABLE | {"svg","g","defs","title","desc","metadata","clipPath","mask","linearGradient","radialGradient","stop","pattern","animate","animateTransform","animateMotion","set"}
GEOMETRY_KEYS = {"d","x","y","cx","cy","r","rx","ry","x1","y1","x2","y2","width","height","points","transform"}


def svg_root(code, *, allow_animation=False):
    if not isinstance(code,str) or len(code.encode()) > MAX_SVG or re.search(r"<!DOCTYPE|<!ENTITY",code,re.I):
        raise ValueError("SVG XML entities or code bounds invalid")
    root = ET.fromstring(code)
    nodes = list(root.iter())
    if root.tag.split("}")[-1] != "svg" or len(nodes)>700:
        raise ValueError("SVG root or node bound invalid")
    for node in nodes:
        tag = node.tag.split("}")[-1]
        if tag not in SAFE_TAGS or (not allow_animation and tag.startswith("animate")):
            raise ValueError("SVG contains unsupported or active nodes")
        for key,value in node.attrib.items():
            key = key.split("}")[-1]
            if key.lower().startswith("on") or key in ("href","src","style") or re.search(r"(?:https?:|javascript:|data:|@import)",value,re.I) or ("url(" in value.lower() and not re.fullmatch(r"url\(#[A-Za-z0-9_.-]+\)",value)):
                raise ValueError("SVG contains active or external attribute data")
    return root


def geometry_signature(root):
    parts = []
    def walk(node, transforms):
        tag = node.tag.split("}")[-1]
        transforms = transforms + ([node.attrib["transform"]] if "transform" in node.attrib else [])
        if tag in DRAWABLE:
            attributes = {k:re.sub(r"\s+"," ",v.strip()) for k,v in node.attrib.items() if k in GEOMETRY_KEYS and k!="transform"}
            parts.append([tag,attributes,transforms])
        for child in node:
            walk(child,transforms)
    walk(root,[])
    return digest(json.dumps([root.get("viewBox"),sorted(parts,key=lambda x:json.dumps(x,sort_keys=True))],sort_keys=True).encode())


MODIFIERS = {"up","down","left","right","north","south","east","west","horizontal","vertical","filled","outline","twotone","loop","small","big","off","on","add","plus","minus","remove","delete","edit","check","x","question","exclamation","alert","in","out","alt","dashed","dotted","broken","double","triple","bold","thin","light","regular","duotone","fill"}
SYNONYMS = {"account":"user","person":"user","people":"users","users":"user","avatar":"user","envelope":"mail","email":"mail","e-mail":"mail","trash":"bin","trashcan":"bin","settings":"cog","gear":"cog","home":"house","search":"magnifier","zoom":"magnifier","chevron":"arrow","caret":"arrow","chevrons":"arrow","arrows":"arrow","refresh":"reload","rotate":"reload","refreshes":"reload","tick":"check","confirm":"check","close":"x","cross":"x","document":"file","folder-open":"folder","file-text":"file","chat":"message","speech":"message","comment":"message","speechbubble":"message","smartphone":"phone","mobile":"phone","laptop":"computer","monitor":"computer","desktop":"computer"}
SYNONYMS.update({"temperature":"thermometer","barometer":"gauge","bolt":"lightning","raindrop":"droplet","raindrops":"droplet","drop":"droplet","sunrise":"sun","sunset":"sun","moonrise":"moon","moonset":"moon","thumbs":"thumb"})
UMBRELLAS = {"arrow","calendar","clock","user","file","folder","mail","message","heart","shield","lock","unlock","phone","computer","battery","cloud","wifi","sun","moon","check","x","magnifier","cog","reload","bin","bell","bookmark","camera","video","volume","mic","microphone","eye","download","upload","play","pause","stop","database","chart","graph","circle","square","triangle","number","letter","currency","device","building","list","layout","table","border","grid","align","text","typography","sport","ball","medical","printer","keyboard","map","pin","location","flag","star","music","headphones","shopping","basket","cart","truck","car","bus","train","plane","airplane","aircraft","boat","ship","home","house","login","logout","door","arrowhead","fingerprint"}
UMBRELLAS.update({"thermometer","gauge","lightning","droplet","rainbow","wind","pollen","smoke","hail","dust","rain","fog","hurricane","windsock","umbrella","humidity","snowflake","sleet","compass","beanie","glove","pressure","uv"})


def icon_family(name):
    name = re.sub(r"([a-z0-9])([A-Z])",r"\1-\2",name)
    tokens = re.findall(r"[a-z]+|[0-9]+", name.lower())
    tokens = [SYNONYMS.get(t,t) for t in tokens if t not in MODIFIERS and not t.isdigit()]
    tokens = [t for t in tokens if t not in ("transition","to","svg","icon","brand","brands","logo","logotype")]
    if not tokens:
        return re.sub(r"[^a-z]+","",name.lower()) or "symbol"
    if tokens[0] in UMBRELLAS:
        return tokens[0]
    return "-".join(tokens)


def source_item(source, name, path, code, category="shape", extraction="Complete source-authored SVG, unmodified"):
    artifact = next(a for a in source["artifacts"] if a["path"]==path)
    notice = verified_bytes(source,source["notice"]).decode("utf-8")
    if source["slug"] == "wesanderson":
        mit = verified_bytes(next(s for s in CURRENT_MANIFEST["sources"] if s["slug"]=="tabler"),"LICENSE").decode("utf-8")
        notice += "\n\n"+mit[mit.index("Permission is hereby granted"):]
    if source["license"] == "CC BY 4.0" and source["slug"] != "heropatterns":
        terms = (ROOT/"data/upstream/color-wave/terms/CC-BY-4.0.txt").read_bytes()
        if digest(terms)!=CCBY_SHA:
            raise ValueError("Full CC BY legal text hash mismatch")
        notice += "\n\n"+terms.decode()
    attribution={"heropatterns":"Hero Patterns by Steve Schoger, https://heropatterns.com/", "colorcet":"Colorcet colormaps by Peter Kovesi, distributed by HoloViz, https://colorcet.holoviz.org/"}.get(source["slug"])
    if attribution:
        notice=attribution+". Licensed under CC BY 4.0.\n\n"+notice
    source_url = f"https://github.com/{source['repo']}/blob/{source['commit']}/{path}" if "repo" in source else "https://heropatterns.com/"
    license_url = f"https://github.com/{source['repo']}/blob/{source['commit']}/{source['notice']}" if "repo" in source else "https://creativecommons.org/licenses/by/4.0/"
    slug = re.sub(r"[^a-z0-9]+","-",name.lower()).strip("-")
    item = {"id":"design-"+source["slug"]+"-"+slug,"title":name.replace("-"," ").replace("_"," ").title(),"description":f"Static {category} design asset from {source['name']}. {extraction}.",
        "category":category,"domain":"design","kind":"code","language":"svg","tags":["svg","static-design",category],"colors":[],"code":code,"codePath":artifact["artifactPath"],
        "sourceUrl":source_url,"sourceName":source["name"],"license":source["license"],"licenseUrl":license_url,"licenseText":notice,
        "verifiedAt":DATE,"verification":"source-reviewed","access":"public","upstreamSha256":artifact["sha256"],
        "preview":{"type":"svg","variant":slug,"adapted":extraction!="Complete source-authored SVG, unmodified","limitations":[]},
        "evidence":{"scope":"individual-asset","artifactPath":artifact["artifactPath"],"artifactUrl":artifact["url"],"originalBytesSha256":artifact["sha256"],"storedCodeSha256":digest(code.encode()),"sourceUrls":[source_url,license_url],"extraction":extraction,"rights":"Full license/copyright notices are stored; source programs were parsed as data without execution","staticDesign":True}}
    if "commit" in source:
        item.update(sourceCommit=source["commit"],upstreamCommit=source["commit"])
        item["evidence"]["sourceCommit"]=source["commit"]
    if attribution:
        item["description"]+=" Attribution: "+attribution+"."
        item["evidence"]["attribution"]=attribution
    return item


CURRENT_MANIFEST = {}


def icon_name(item):
    component=item.get("evidence",{}).get("component")
    if isinstance(component,str):
        return component
    if str(item.get("sourceName","")).startswith("Meteocons"):
        return PurePosixPath(item.get("codePath",item["id"])).stem
    return item.get("title",item["id"])


def motion_comparison_records():
    snapshot=LOCAL/"motion-comparison.json";notice=LOCAL/"motion-comparison-manifest.json"
    if snapshot.is_file() and notice.is_file():
        metadata=json.loads(notice.read_text(encoding="utf-8"));raw=snapshot.read_bytes()
        if len(raw)>64*1024*1024 or digest(raw)!=metadata["sha256"]:
            raise ValueError("Cross-wave motion comparison snapshot integrity mismatch")
        records=json.loads(raw)
        original=ROOT/"data/phase2-motion-items.json"
        if original.is_file():
            if original.stat().st_size>64*1024*1024:
                raise ValueError("Cross-wave motion source input exceeds its byte bound")
            latest=original.read_bytes()
            if digest(latest)!=metadata["inputSha256"]:
                items=json.loads(latest)
                fields=("id","title","kind","language","category","colors","sourceName","code","codePath")
                current=[{k:item[k] for k in fields if k in item} for item in items if item.get("language")=="svg"]
                if current!=records:
                    raise ValueError("Cross-wave animated SVGs changed; a fresh comparison review is required")
                # A corrected CSS-only input does not change any SVG comparison.
                # Retain the immutable SVG snapshot and refresh only input counts.
                metadata.update(inputSha256=digest(latest),inputCount=len(items),comparisonRecords=len(records),inputRevisionNote="Motion input changed only outside the preserved SVG comparison fields; every compared SVG record is exactly unchanged")
                save_json(notice,metadata)
        return records,metadata
    original=ROOT/"data/phase2-motion-items.json"
    if not original.is_file():
        return [],{"inputCount":0,"comparisonRecords":0,"status":"not-yet-collected"}
    if original.stat().st_size>64*1024*1024:
        raise ValueError("Cross-wave motion source input exceeds its byte bound")
    raw=original.read_bytes();items=json.loads(raw)
    if not isinstance(items,list) or len(items)>12_000:
        raise ValueError("Cross-wave motion asset count invalid")
    fields=("id","title","kind","language","category","colors","sourceName","code","codePath")
    records=[{k:item[k] for k in fields if k in item} for item in items if item.get("language")=="svg"]
    save_json(snapshot,records)
    metadata={"inputPath":"data/phase2-motion-items.json","inputSha256":digest(raw),"inputCount":len(items),"comparisonRecords":len(records),"sha256":digest(snapshot.read_bytes()),"scope":"All new animated SVG concepts take priority over static design concepts; immutable cross-wave comparison snapshot"}
    save_json(notice,metadata)
    return records,metadata


def polygon_paths(root):
    """Flatten bounded SVG geometry only. No browser, JavaScript, CSS or I/O."""
    from fontTools.pens.basePen import BasePen
    from fontTools.svgLib.path import parse_path
    contours=[]
    class Pen(BasePen):
        def __init__(self):
            super().__init__(None)
            self.contour=[]
            self.position=None
        def finish(self,closed=False):
            if self.contour:
                contours.append((self.contour,closed))
                self.contour=[]
        def _moveTo(self,p):
            self.finish()
            self.contour=[p]
            self.position=p
        def _lineTo(self,p):
            if not self.contour and self.position is not None:
                self.contour=[self.position]
            self.contour.append(p)
            self.position=p
        def _curveToOne(self,p1,p2,p3):
            p0=self._getCurrentPoint() or self.position
            if p0 is None:
                raise ValueError("Curve has no preceding coordinate")
            if not self.contour:
                self.contour=[p0]
            for i in range(1,17):
                t=i/16; u=1-t
                self.contour.append(tuple(u**3*p0[k]+3*u*u*t*p1[k]+3*u*t*t*p2[k]+t**3*p3[k] for k in (0,1)))
            self.position=p3
        def _qCurveToOne(self,p1,p2):
            p0=self._getCurrentPoint() or self.position
            if p0 is None:
                raise ValueError("Curve has no preceding coordinate")
            if not self.contour:
                self.contour=[p0]
            for i in range(1,17):
                t=i/16; u=1-t
                self.contour.append(tuple(u*u*p0[k]+2*u*t*p1[k]+t*t*p2[k] for k in (0,1)))
            self.position=p2
        def _closePath(self):
            if self.contour:
                self.position=self.contour[0]
                self.contour.append(self.contour[0])
            self.finish(True)
        def _endPath(self):
            self.finish()
    pen=Pen()
    number=lambda n,key,default="0":float(n.get(key,default))
    for node in root.iter():
        tag=node.tag.split("}")[-1]
        # Defs/masks/complex transforms are not approximated for acceptance.
        if node.get("transform") or tag in {"mask","clipPath","use","pattern"}:
            raise ValueError("Complex geometry requires a dedicated visual review")
        if tag=="path":
            data=node.get("d","")
            if len(re.findall(r"[A-Za-z]",data))>5000:
                raise ValueError("Path command bound exceeded")
            parse_path(data,pen)
            pen.finish()
        elif tag in {"circle","ellipse"}:
            cx,cy=number(node,"cx"),number(node,"cy")
            rx=number(node,"r") if tag=="circle" else number(node,"rx")
            ry=number(node,"r") if tag=="circle" else number(node,"ry")
            contours.append(([(cx+rx*math.cos(i*math.pi/32),cy+ry*math.sin(i*math.pi/32)) for i in range(65)],True))
        elif tag=="rect":
            x,y,w,h=(number(node,k) for k in ("x","y","width","height"))
            rx,ry=number(node,"rx"),number(node,"ry")
            if not rx and not ry:
                contours.append(([(x,y),(x+w,y),(x+w,y+h),(x,y+h),(x,y)],True))
            else:
                rx=min(rx or ry,w/2);ry=min(ry or rx,h/2)
                points=[]
                for cx,cy,begin in ((x+w-rx,y+ry,-math.pi/2),(x+w-rx,y+h-ry,0),(x+rx,y+h-ry,math.pi/2),(x+rx,y+ry,math.pi)):
                    points.extend((cx+rx*math.cos(begin+i*math.pi/16),cy+ry*math.sin(begin+i*math.pi/16)) for i in range(9))
                points.append(points[0]);contours.append((points,True))
        elif tag=="line":
            contours.append(([(number(node,"x1"),number(node,"y1")),(number(node,"x2"),number(node,"y2"))],False))
        elif tag in {"polyline","polygon"}:
            values=[float(v) for v in re.findall(r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?",node.get("points",""))]
            if len(values)%2:
                raise ValueError("Invalid polygon coordinate count")
            points=list(zip(values[::2],values[1::2]))
            if tag=="polygon" and points:
                points.append(points[0])
            contours.append((points,tag=="polygon"))
    if sum(len(p) for p,_ in contours)>100_000 or any(not math.isfinite(v) or abs(v)>100_000 for points,_ in contours for p in points for v in p):
        raise ValueError("Geometry coordinates exceed their finite bound")
    return contours


def geometry_rasters(root):
    """Return orientation-normalized 64x64 centerline masks for near exclusion.

    This conservative mask compares underlying geometry without paint or stroke
    weight. Curves use 16 samples and ellipses 64 samples; it is not a browser
    rendering or a guarantee of perceptual uniqueness.
    """
    from PIL import Image,ImageDraw
    polygons=polygon_paths(root)
    view=[float(v) for v in root.get("viewBox","0 0 24 24").split()]
    if len(view)!=4 or view[2]<=0 or view[3]<=0:
        raise ValueError("SVG requires a finite positive viewBox")
    scale=56/max(view[2:]);image=Image.new("1",(64,64),0);draw=ImageDraw.Draw(image)
    for points,_closed in polygons:
        transformed=[((p[0]-view[0]-view[2]/2)*scale+32,(p[1]-view[1]-view[3]/2)*scale+32) for p in points]
        if len(transformed)>1:
            draw.line(transformed,fill=1,width=3)
    if not image.getbbox():
        raise ValueError("SVG has no visible geometric contour")
    rotations=[]
    for mode in (None,Image.Transpose.FLIP_LEFT_RIGHT):
        framed=image if mode is None else image.transpose(mode)
        for k in range(4):
            rotated=framed.rotate(k*90)
            value=int.from_bytes(rotated.tobytes(),"big")
            rotations.append(value)
    return tuple(sorted(set(rotations)))


def raster_near(left,right):
    # D4 is a closed group: fixing one orientation of the left mask and testing
    # all orientations of the right mask covers the same relative transforms.
    for a in left[:1]:
        ac=a.bit_count()
        for b in right:
            bc=b.bit_count()
            if min(ac,bc)<max(ac,bc)*0.88:
                continue
            union=(a|b).bit_count()
            if union and (a&b).bit_count()/union>=0.90:
                return True
    return False


def baseline_color_arrays(records):
    from duplicate_audit_palette import canonical_color
    arrays=[]
    for item in records:
        colors=item.get("colors",[])
        if item.get("kind") not in ("palette","code") or (item.get("kind")=="code" and item.get("category")!="gradient") or not colors:
            continue
        try:
            arrays.append((item["id"],tuple(canonical_color(c) for c in colors)))
        except ValueError:
            continue
    return arrays


def rgba_rgb(color):
    return tuple(int(color[pos:pos+2],16)/255 for pos in (1,3,5))


def rgba_values(color):
    return tuple(int(color[pos:pos+2],16)/255 for pos in (1,3,5,7))


def resample(colors,size=64):
    if len(colors)<2 or len(colors)>2048:
        raise ValueError("Original color map length exceeds the supported bound")
    vectors=[]
    from duplicate_audit_palette import _oklab
    for i in range(size):
        pos=i*(len(colors)-1)/(size-1);lower=int(pos);upper=min(lower+1,len(colors)-1);mix=pos-lower
        rgb=tuple(colors[lower][j]*(1-mix)+colors[upper][j]*mix for j in range(3))
        alpha=(colors[lower][3]*(1-mix)+colors[upper][3]*mix) if len(colors[lower])==4 else 1.0
        black=_oklab(tuple(c*alpha for c in rgb))
        white=_oklab(tuple(c*alpha+1-alpha for c in rgb))
        vectors.append(black+white)
    return vectors


def continuous_near(left,right):
    for values in (right,list(reversed(right))):
        total=0.0
        for x,y in zip(left,values):
            distance=max(math.sqrt(sum((x[j]-y[j])**2 for j in range(offset,offset+3))) for offset in (0,3))
            # One sample above the maximum proves this orientation cannot pass;
            # early rejection preserves the exact full-path acceptance rule.
            if distance>2 or total+distance>len(left):
                break
            total+=distance
        else:
            return True
    return False


def gradient_code(values):
    if not 2<=len(values)<=2048:
        raise ValueError("Invalid authored color map size")
    stops=[]
    for i,rgb in enumerate(values):
        if len(rgb)!=3 or any(not math.isfinite(v) or not 0<=v<=1 for v in rgb):
            raise ValueError("Color map RGB values outside [0,1]")
        color="rgb("+" ".join(format(v*100,".12g")+"%" for v in rgb)+")"
        stops.append(f'<stop offset="{format(i/(len(values)-1),".12g")}" stop-color="{color}"/>')
    return '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 64" width="256" height="64"><defs><linearGradient id="authored-map" x1="0" y1="0" x2="1" y2="0">'+"".join(stops)+'</linearGradient></defs><rect width="256" height="64" fill="url(#authored-map)"/></svg>'


def categorical_code(values):
    if not 2<=len(values)<=2048:
        raise ValueError("Invalid authored categorical palette size")
    columns=16 if len(values)>32 else len(values)
    rows=math.ceil(len(values)/columns)
    rectangles=[]
    for i,rgb in enumerate(values):
        if len(rgb)!=3 or any(not math.isfinite(v) or not 0<=v<=1 for v in rgb):
            raise ValueError("Categorical palette RGB values outside [0,1]")
        color="rgb("+" ".join(format(v*100,".12g")+"%" for v in rgb)+")"
        rectangles.append(f'<rect x="{i%columns}" y="{i//columns}" width="1" height="1" fill="{color}"/>')
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {columns} {rows}" width="256" height="{256 if rows>1 else 64}">'+"".join(rectangles)+'</svg>'


def palette_candidates(source):
    slug=source["slug"]
    if slug in ("cmcrameri","cmocean"):
        for a in source["artifacts"]:
            if a["path"].endswith(".txt") and "/" in a["path"]:
                name=PurePosixPath(a["path"]).stem.replace("-rgb","")
                if slug=="cmcrameri" and name.endswith("S"):
                    continue
                rows=[]
                for line in verified_bytes(source,a["path"]).decode().splitlines():
                    parts=line.split()
                    if len(parts)==3:
                        rows.append(tuple(float(v) for v in parts))
                yield name,a["path"],rows,None
    elif slug=="colorcet":
        tree=ast.parse(verified_bytes(source,"colorcet/__init__.py").decode())
        for node in tree.body:
            if not isinstance(node,ast.Assign) or len(node.targets)!=1 or not isinstance(node.targets[0],ast.Name) or not isinstance(node.value,ast.List):
                continue
            name=node.targets[0].id
            if name.endswith("_s25"):
                continue
            try:
                values=ast.literal_eval(node.value)
            except (ValueError,TypeError):
                continue
            if len(values)==256 and all(isinstance(row,list) and len(row)==3 and all(isinstance(v,(int,float)) for v in row) for row in values):
                yield name,"colorcet/__init__.py",values,None
    elif slug=="wesanderson":
        text=verified_bytes(source,"R/colors.R").decode()
        from duplicate_audit_palette import canonical_color
        for name,body in re.findall(r"\b([A-Za-z][A-Za-z0-9_]*)\s*=\s*c\(([^)]*)\)",text):
            colors=re.findall(r'"(#[0-9a-fA-F]{6})"',body)
            if 2<=len(colors)<=32:
                colors=tuple(canonical_color(c) for c in colors)
                yield name,"R/colors.R",[rgba_rgb(c) for c in colors],colors


def discrete_near(colors,existing):
    from duplicate_audit_palette import color_vector,minimum_assignment,_metrics,_close
    if len(colors)!=len(existing):
        return False
    a=[color_vector(c) for c in colors];b=[color_vector(c) for c in existing]
    costs=[[sum((v-w)**2 for v,w in zip(x,y)) for y in b] for x in a]
    return _close(_metrics(a,b,minimum_assignment(costs)))


def rebuild(manifest):
    sources={s["slug"]:s for s in manifest["sources"]}
    baseline,baseline_hash=baseline_records()
    cross_motion,cross_metadata=motion_comparison_records()
    rejected=[];items=[];candidate_count=0
    def reject(source,name,reason,existing=None):
        row={"source":source,"name":name,"reason":reason}
        if existing:
            row["matches"]=existing
        rejected.append(row)
    families={};geometries={};rasters=[]
    for item in baseline:
        if item.get("kind")!="code" or item.get("language")!="svg":
            continue
        if item.get("sourceName")=="Material Line Icons":
            families.setdefault(icon_family(icon_name(item)),item["id"])
        try:
            root=svg_root(item["code"],allow_animation=True)
            geometries.setdefault(geometry_signature(root),item["id"])
            rasters.append((geometry_rasters(root),item["id"]))
        except (ValueError,ET.ParseError,KeyError):
            pass
    baseline_families=len(families);baseline_geometry=len(geometries);baseline_rasters=len(rasters)
    cross_geometry_count=0;cross_raster_count=0;cross_uncompared=[]
    for item in cross_motion:
        family=icon_family(icon_name(item));families.setdefault(family,item["id"])
        try:
            root=svg_root(item["code"],allow_animation=True)
            geometries.setdefault(geometry_signature(root),item["id"]);cross_geometry_count+=1
            rasters.append((geometry_rasters(root),item["id"]));cross_raster_count+=1
        except (ValueError,ET.ParseError,KeyError) as error:
            cross_uncompared.append({"id":item["id"],"reason":str(error),"semanticComparison":family})
    # Prefer one original Tabler outline per semantic concept. Other libraries
    # contribute only concepts absent from the current and new accepted pool.
    for slug in ("tabler","lucide","phosphor"):
        source=sources[slug]
        files=[a for a in source["artifacts"] if a["path"].endswith(".svg")]
        # Base names precede qualified names; this prevents a tiny toggle variant
        # from becoming the representative of an otherwise plain concept.
        files.sort(key=lambda a:(len(PurePosixPath(a["path"]).stem.split("-")),len(a["path"]),a["path"]))
        for index,artifact in enumerate(files):
            candidate_count+=1;name=PurePosixPath(artifact["path"]).stem;family=icon_family(name)
            if family in families:
                reject(slug,name,"semantic-concept-or-style-direction-toggle-family",families[family]);continue
            code=verified_bytes(source,artifact["path"]).decode()
            try:
                root=svg_root(code);signature=geometry_signature(root)
                if signature in geometries:
                    reject(slug,name,"exact-static-geometry",geometries[signature]);continue
                raster=geometry_rasters(root)
                match=next((old_id for old,old_id in rasters if raster_near(raster,old)),None)
                if match:
                    reject(slug,name,"near-contour-with-rotation-reflection-style-normalization",match);continue
            except (ValueError,ET.ParseError) as error:
                reject(slug,name,"unsupported-geometry-review-required: "+str(error));continue
            item=source_item(source,name,artifact["path"],code)
            item["evidence"].update(semanticFamily=family,geometrySha256=signature,comparison="All original baseline variants and accepted new SVG contour/family candidates; paint, weight, direction and tiny toggles conservatively excluded")
            items.append(item);families[family]=item["id"];geometries[signature]=item["id"];rasters.append((raster,item["id"]))
            if index%500==0:
                print(slug,index,"candidate SVGs reviewed",len(items),"accepted",flush=True)
    # Hero Patterns are exact embedded first-party SVG strings, with original
    # attribution license and source bundle retained. Trivial texture concepts
    # already represented by the stored CSS-pattern library are excluded.
    source=sources["heropatterns"];text=verified_bytes(source,"app.js").decode()
    pairs=re.findall(r"name:\s*'([^']+)'\s*,\s*image:\s*'((?:\\.|[^'\\])*)'",text)
    if len(pairs)!=87:
        raise ValueError("Hero Patterns bundle no longer contains the 87 reviewed individual SVGs")
    trivial={"diagonal-stripes","diagonal-lines","stripes","tiny-checkers","pixel-dots","polka-dots","graph-paper","squares","zig-zag","hexagons","brick-wall","overlapping-circles","overlapping-diamonds","overlapping-hexagons"}
    for name,body in pairs:
        candidate_count+=1;slugname=re.sub(r"[^a-z0-9]+","-",name.lower()).strip("-")
        if slugname in trivial:
            reject("heropatterns",name,"generic-pattern-concept-already-represented-by-CSS-Pattern");continue
        code=body.replace("\\'","'").replace('\\"','"').replace("\\/","/")
        try:
            root=svg_root(code);signature=geometry_signature(root);raster=geometry_rasters(root)
            match=next((old_id for old,old_id in rasters if raster_near(raster,old)),None)
            if signature in geometries or match:
                reject("heropatterns",name,"existing-or-new-static-geometry-near",geometries.get(signature,match));continue
        except (ValueError,ET.ParseError) as error:
            reject("heropatterns",name,"unsupported-pattern-review-required: "+str(error));continue
        item=source_item(source,name,"app.js",code,"pattern","Exact individual SVG literal extracted from the first-party bundle; no JavaScript executed")
        item["evidence"].update(attribution="Steve Schoger / Hero Patterns",sourceBundleSha256=source["sha256"],geometrySha256=signature)
        items.append(item);geometries[signature]=item["id"];rasters.append((raster,item["id"]))
    source=sources["coolshapes"]
    for artifact in source["artifacts"]:
        if not re.fullmatch(r"src/shapes/[a-z]+/[0-9]+\.tsx",artifact["path"]):
            continue
        candidate_count+=1;parts=PurePosixPath(artifact["path"]);name=parts.parts[-2]+"-"+parts.stem
        text=verified_bytes(source,artifact["path"]).decode()
        match=re.search(r'\bshape:\s*("(?:\\.|[^"\\])*"|`[^`]*`)',text)
        if not match:
            reject("coolshapes",name,"nonliteral-shape-data");continue
        literal=match[1]
        shape=json.loads(literal) if literal.startswith('"') else literal[1:-1]
        if "${" in shape:
            reject("coolshapes",name,"dynamic-template");continue
        if "<" in shape:
            shape=shape.replace("<>","").replace("</>","").replace("fillRule","fill-rule").replace("clipRule","clip-rule").replace("fillOpacity","fill-opacity")
        else:
            shape='<path d="'+escape(shape,quote=True)+'"/>'
        code='<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200" width="200" height="200" fill="currentColor">'+shape+'</svg>'
        try:
            root=svg_root(code);signature=geometry_signature(root);raster=geometry_rasters(root)
            near=next((old_id for old,old_id in rasters if raster_near(raster,old)),None)
            if signature in geometries or near:
                reject("coolshapes",name,"existing-or-new-static-geometry-near",geometries.get(signature,near));continue
        except (ValueError,ET.ParseError) as error:
            reject("coolshapes",name,"unsupported-shape-review-required: "+str(error));continue
        item=source_item(source,name,artifact["path"],code,"shape","Original literal silhouette geometry in a standalone SVG host; source gradients/noise are separate optional treatments")
        item["preview"]["limitations"]=["Geometry-only extraction. Optional upstream grain, gradient and React runtime are not part of this static silhouette asset."]
        item["evidence"].update(geometrySha256=signature,sourceComponent=name,sourceLiteral=shape)
        items.append(item);geometries[signature]=item["id"];rasters.append((raster,item["id"]))
    arrays=baseline_color_arrays(baseline);map_vectors=[]
    for ident,colors in arrays:
        map_vectors.append((resample([rgba_values(c) for c in colors]),ident))
    scientific_families={};accepted_palette=[]
    for slug in ("wesanderson","cmcrameri","cmocean","colorcet"):
        source=sources[slug]
        for name,path,values,hexcolors in palette_candidates(source):
            candidate_count+=1
            if slug=="wesanderson" and name in ("Rushmore1","Zissou1Continuous"):
                reject(slug,name,"author-palette-alias-or-continuous-family");continue
            family=(re.sub(r"(?:[KWO])$","",name) if slug=="cmcrameri" else "glasbey" if slug=="colorcet" and name.startswith("glasbey") else re.sub(r"_[0-9].*$","",name) if slug=="colorcet" else name)
            if slug in ("cmcrameri","colorcet") and (slug,family) in scientific_families:
                reject(slug,name,"contrast-chroma-or-cyclic-family-variant",scientific_families[(slug,family)]);continue
            vector=resample(values)
            duplicate=None
            if hexcolors:
                duplicate=next((ident for ident,old in arrays+accepted_palette if discrete_near(hexcolors,old)),None)
            if not duplicate:
                duplicate=next((ident for old,ident in map_vectors if continuous_near(vector,old)),None)
            if duplicate:
                reject(slug,name,"exact-or-near-original-full-palette-resampled-comparison",duplicate);continue
            categorical=slug=="wesanderson" or name.startswith("glasbey")
            category="palette" if categorical else "gradient"
            code=categorical_code(values) if categorical else gradient_code(values)
            extraction="Every original RGB swatch preserved in one standalone SVG palette; source data/program is stored verbatim and never executed" if categorical else "All original RGB samples represented as one SVG gradient; the source data/program is stored verbatim and never executed"
            item=source_item(source,name,path,code,category,extraction)
            item["evidence"].update(fullColorCount=len(values),fullOriginalRgbValues=values,continuousColorMap=not categorical,comparison="Complete baseline palette/original variant arrays plus accepted new arrays. Original sizes preserved; ordered/reversed 64-sample RGB(A) interpolation over both black and white, Euclidean OKLab mean<=1 and max<=2; discrete same-size palette Hungarian comparison")
            item["tags"]=["svg",category,"scientific-colormap" if slug!="wesanderson" else "authored-palette","static-design"]
            items.append(item);map_vectors.append((vector,item["id"]));scientific_families[(slug,family)]=item["id"]
            if hexcolors:
                accepted_palette.append((item["id"],hexcolors))
    if len(items)>MAX_ITEMS or len({i["id"] for i in items})!=len(items):
        raise ValueError("Design output exceeds its asset bound or contains duplicate IDs")
    items.sort(key=lambda x:x["id"])
    save_json(OUTPUT,items)
    report={"verifiedAt":DATE,"rebuiltAt":datetime.now(timezone.utc).isoformat(),"baselineCatalogSha256":baseline_hash,"baselineComparisons":{"allOriginalAndRepairedRecords":len(baseline),"semanticFamilies":baseline_families,"geometrySignatures":baseline_geometry,"contourRasters":baseline_rasters,"paletteArrays":len(arrays)},"newMotionComparisons":{**cross_metadata,"geometryParsed":cross_geometry_count,"contourRasters":cross_raster_count,"complexGeometryDeferred":cross_uncompared},
        "candidateCount":candidate_count,"accepted":len(items),"bySource":dict(Counter(i["sourceName"] for i in items)),"byCategory":dict(Counter(i["category"] for i in items)),"rejectedCount":len(rejected),"rejections":rejected,"rejectionReasons":dict(Counter(r["reason"] for r in rejected)),
        "methodology":{"semantic":"One icon concept, conservative synonym/umbrella grouping and removal of style, direction, tiny toggle, numeric variants; baseline animated concepts preferred.","geometry":"Exact original drawable geometry, paint-independent contour masks at 64x64, 16-step Bezier/64-step ellipse sampling, eight 90-degree rotation/reflection orientations; Jaccard>=0.90 is excluded rather than asserted novel.","palettes":"Full original maps preserved as single gradients. Existing original/merged arrays and new maps compared after 64-sample RGB(A) interpolation over both black and white, with reverse order, Euclidean OKLab mean<=1 and max<=2; same-size discrete arrays also Hungarian matched.","limitations":["A structural/semantic gate is not proof of universal perceptual uniqueness.","No external program or source JavaScript/TypeScript/R/Python was executed.","Complex transforms/masks needing a dedicated visual review are rejected.","Static design assets do not count as new motion mechanisms."]},"network":manifest.get("requests",[]),"robots":manifest.get("robots",[]),"bounds":manifest.get("bounds",{})}
    save_json(REPORT,report)
    print(json.dumps({k:report[k] for k in ("candidateCount","accepted","bySource","byCategory","rejectedCount")}),flush=True)


def main():
    global CURRENT_MANIFEST
    parser=argparse.ArgumentParser(description=__doc__)
    mode=parser.add_mutually_exclusive_group()
    mode.add_argument("--fetch",action="store_true")
    mode.add_argument("--offline",action="store_true")
    args=parser.parse_args()
    CURRENT_MANIFEST=fetch() if args.fetch else json.loads(MANIFEST.read_text(encoding="utf-8"))
    if {s["slug"] for s in CURRENT_MANIFEST["sources"]} != set(SOURCES):
        raise ValueError("Source manifest is incomplete")
    for source in CURRENT_MANIFEST["sources"]:
        verify_source(source)
    rebuild(CURRENT_MANIFEST)


if __name__=="__main__":
    try:
        main()
    except (OSError,ValueError,KeyError,ET.ParseError) as error:
        raise SystemExit("Static design import stopped: "+str(error)) from error
