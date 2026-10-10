"""Recreate reviewed Promptfilm excerpts and independent illustrations, offline."""

import hashlib
import json
import math
from pathlib import Path
import random
import re
import stat
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from motionlab.source_review import validate_source_review  # noqa: E402
from scripts.build import validate_item, write_json  # noqa: E402
from scripts.expansion import asset_fingerprint  # noqa: E402
from scripts.package import checked_path  # noqa: E402

REPOSITORY = "https://github.com/Seokwoooo/promptfilm"
REVISION = "d39f4d327b24ae0e3da2c23adccb237c368530e4"
PREVIEW_NOTICE = "Independently authored Motion Lab concept illustration. Dedicated to the public domain under CC0 1.0 Universal. This dedication covers only this CSS/SVG illustration, not the upstream JavaScript source or its dependencies."
PREVIEW_LIMITS = ["Independent 2D concept illustration; original JavaScript is not executed.",
                  "The diagram isolates a mechanism and does not reproduce the complete Three.js film, lighting or source data."]


def circle(x, y, radius, fill="#61dfeb", opacity=1):
    return f'<circle cx="{x:.2f}" cy="{y:.2f}" r="{radius:.2f}" fill="{fill}" opacity="{opacity}"/>'


def rect(x, y, width, height, fill="#17353c", radius=3, stroke="#61dfeb"):
    return f'<rect x="{x:.2f}" y="{y:.2f}" width="{width:.2f}" height="{height:.2f}" rx="{radius}" fill="{fill}" stroke="{stroke}" stroke-width="1"/>'


def line(x1, y1, x2, y2, color="#61dfeb", width=1, opacity=1):
    return f'<line x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}" stroke="{color}" stroke-width="{width}" opacity="{opacity}"/>'


def path(points, color="#61dfeb", width=2, fill="none"):
    return f'<path d="{points}" fill="{fill}" stroke="{color}" stroke-width="{width}" stroke-linecap="round" stroke-linejoin="round"/>'


def moving(content, values, *, kind="translate", duration=5):
    return '<g>' + content + f'<animateTransform attributeName="transform" type="{kind}" values="{values}" dur="{duration}s" repeatCount="indefinite"/></g>'


def illustration(concept, domain):
    """A closed set of authored diagrams, never source-code evaluation."""
    rng = random.Random(int.from_bytes(hashlib.sha256(concept.encode()).digest()[:8], "big"))
    body = draw_concept(concept, domain, rng)
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 320 200">'
            '<defs><radialGradient id="surface" cx="30%" cy="25%"><stop offset="0" stop-color="#dfedf0"/>'
            '<stop offset="0.5" stop-color="#48808c"/><stop offset="1" stop-color="#10212c"/></radialGradient>'
            '<linearGradient id="metal"><stop offset="0" stop-color="#18232e"/><stop offset="0.45" stop-color="#a0c2cc"/>'
            '<stop offset="0.55" stop-color="#e6eff2"/><stop offset="1" stop-color="#293f4c"/></linearGradient>'
            '<radialGradient id="glow"><stop offset="0" stop-color="#eaffff"/><stop offset="0.22" stop-color="#65ddeb"/>'
            '<stop offset="1" stop-color="#071018" stop-opacity="0"/></radialGradient></defs>'
            '<rect width="320" height="200" fill="#071018"/>' + body + '</svg>')


def draw_concept(concept, domain, rng):
    # Keys are approved independently of source code in the pinned import plan.
    if concept == "log-hermite-camera":
        grid = ''.join(rect(160-w/2, 100-w*.28, w, w*.56, 'none', 0, '#23444e') for w in (270, 180, 100, 40))
        subject = circle(160, 100, 19, 'url(#surface)')
        return grid + moving(subject + rect(125, 65, 70, 70, 'none'), '0 0;25 12;0 0;-25 -12;0 0')
    if concept == "beat-speed-warp":
        blocks = ''.join(rect(25+i*46, 135-h, 34, h, '#17404a') for i, h in enumerate((55, 25, 80, 30, 70, 40)))
        return blocks + line(25, 153, 296, 153) + '<circle cy="60" r="6" fill="#f4fafb"><animate attributeName="cx" values="25;71;117;163;209;255;296;25" keyTimes="0;0.18;0.26;0.52;0.60;0.83;0.94;1" dur="6s" repeatCount="indefinite"/></circle>'
    if concept == "pinned-labels":
        body = circle(160, 108, 33, 'url(#surface)') + path('M170 90 L225 50 L277 50') + rect(222, 33, 55, 11, '#ccedf0')
        body += path('M140 123 L87 151 L37 151') + rect(37, 159, 48, 8)
        return moving(body, '0 0;18 -10;0 0;-18 10;0 0')
    if concept == "ratio-callouts":
        small = circle(83, 118, 12, 'url(#surface)')
        large = '<circle cx="218" cy="98" r="38" fill="url(#surface)"><animate attributeName="r" values="30;42;30" dur="5s" repeatCount="indefinite"/></circle>'
        return small + large + path('M100 115 L157 82 L176 82') + line(135, 52, 154, 71, width=3) + line(154, 52, 135, 71, width=3) + rect(162, 49, 16, 27, '#71d5e3') + rect(186, 49, 8, 27)
    if concept == "small-subject-leaders":
        target = circle(220, 123, 3, '#f4fafb') + '<circle cx="220" cy="123" r="11" fill="none" stroke="#61dfeb"/>'
        return moving(target + path('M212 116 L174 62 L63 62') + rect(63, 43, 70, 10), '0 0;12 9;0 0;-12 -9;0 0')
    if concept == "camera-radial-blur":
        rays = ''.join(line(160+30*math.cos(a), 100+30*math.sin(a), 160+95*math.cos(a), 100+65*math.sin(a), opacity=.2+i*.025) for i in range(18) for a in (i*math.tau/18,))
        return rays + moving(circle(160, 100, 25, 'url(#surface)'), '0 0;22 0;0 0;-22 0;0 0', duration=3)
    if concept == "product-orbit-loop":
        product = rect(132, 50, 56, 102, 'url(#metal)', 15) + '<ellipse cx="160" cy="50" rx="28" ry="9" fill="#c5edf0"/>'
        orbit = '<ellipse cx="160" cy="110" rx="106" ry="35" fill="none" stroke="#204650" stroke-dasharray="4 5"/>'
        return orbit + product + moving(rect(245, 101, 18, 13, '#61dfeb') + path('M245 104 L236 99 L236 116 L245 113'), '0 160 110;360 160 110', kind='rotate', duration=8)
    if concept == "staged-product-explosion":
        result = line(160, 20, 160, 175, '#234c55')
        for i, (y, travel) in enumerate(((58, -32), (83, -14), (106, 10), (127, 27), (148, 39))):
            layer = f'<ellipse cx="160" cy="{y}" rx="44" ry="10" fill="url(#metal)" stroke="#7ee3ec"/>'
            result += moving(layer, f'0 0;0 0;0 {travel};0 {travel};0 0;0 0', duration=6+i*.2)
        return result
    if concept == "luminous-ring":
        return '<ellipse cx="160" cy="105" rx="80" ry="49" fill="none" stroke="#1b3c48" stroke-width="12"/><ellipse cx="160" cy="105" rx="80" ry="49" fill="none" stroke="#7eeafa" stroke-width="6" stroke-dasharray="85 335"><animate attributeName="stroke-dashoffset" values="0;-420" dur="4s" repeatCount="indefinite"/></ellipse>'
    if concept == "jersey-knit":
        return ''.join(path(f'M{x-6} {y-10} Q{x-9} {y+2} {x} {y+7} Q{x+9} {y+2} {x+6} {y-10}', '#78abb6' if (x+y)%3 else '#426977', 3) for x in range(37, 296, 19) for y in range(27, 191, 20))
    if concept == "concentric-brushed-metal":
        return circle(160, 100, 78, 'url(#metal)') + ''.join(f'<circle cx="160" cy="100" r="{r}" fill="none" stroke="#537681" stroke-width="0.8" opacity="{.2+rng.random()*.3:.2f}"/>' for r in range(12, 78, 2)) + circle(160, 100, 9, '#071018')
    if concept == "pressed-paper":
        return rect(28, 24, 264, 152, '#25323b', 0, '#425e68') + ''.join(line(rng.uniform(30, 285), rng.uniform(27, 173), rng.uniform(30, 285), rng.uniform(27, 173), '#718087', .65, .1) for _ in range(70))
    if concept == "softbox-studio":
        return rect(35, 32, 32, 100, '#d7e6eb', 1) + rect(254, 48, 16, 100, '#aac6d2', 1) + path('M71 66 L121 86 M244 99 L200 111', '#467581') + circle(161, 111, 44, 'url(#surface)') + '<ellipse cx="160" cy="162" rx="63" ry="7" fill="#112c37"/>'
    if concept == "contact-shadow-stage":
        return path('M22 141 L160 178 L298 141 L160 111 Z', '#24404b', 1, '#10202a') + '<ellipse cx="161" cy="142" rx="64" ry="14" fill="#02070c"/>' + rect(137, 47, 48, 99, 'url(#metal)', 12) + '<ellipse cx="161" cy="47" rx="24" ry="7" fill="#8fbbc6"/>'
    if concept == "rounded-speaker-shell":
        body = rect(117, 33, 86, 129, '#263c48', 25) + '<ellipse cx="160" cy="34" rx="38" ry="12" fill="url(#metal)"/>'
        body += ''.join(line(124, y, 196, y, '#446570', 1, .5) for y in range(61, 151, 5))
        return body + line(204, 57, 204, 147, '#88c6d1')
    if concept == "woofer-assembly":
        return ''.join(circle(160, 100, r, fill) for r, fill in ((75, '#3b5b67'), (65, '#111f2c'), (56, 'url(#metal)'), (46, '#243d4a'), (26, 'url(#surface)'))) + ''.join(circle(160+66*math.cos(i*math.tau/8), 100+66*math.sin(i*math.tau/8), 3, '#789ba4') for i in range(8))
    if concept == "tweeter-waveguides":
        return ''.join(circle(x, 100, 30, '#284f5b') + circle(x, 100, 22, '#0c1b28') + circle(x, 100, 13, 'url(#surface)') + path(f'M{x-28} 148 Q{x} 171 {x+28} 148', '#356473') for x in (64, 160, 256))
    if concept == "electronics-board":
        result = rect(44, 35, 232, 131, '#113633', 4, '#477c6e')
        for i in range(7):
            result += path(f'M{57+i*27} 49 V{72+i*9} H{252-i*15} V149', '#489785', 1)
        for x, y, w, h in ((117, 70, 60, 49), (65, 102, 23, 35), (204, 50, 26, 23), (216, 124, 39, 13)):
            result += rect(x, y, w, h, '#192b34', 1, '#83aba7')
        return result
    if concept == "printed-battery-pack":
        return rect(63, 68, 185, 63, '#324651', 9) + rect(70, 74, 135, 51, '#c3d7dc', 2) + rect(248, 87, 10, 25) + ''.join(rect(83+i*3, 103, 1+(i%3), 13, '#243941', 0, 'none') for i in range(30)) + line(84, 86, 167, 86, '#526f78', 3)
    if concept == "comparison-framing":
        result = rect(26, 28, 268, 144, 'none', 0, '#284854') + circle(98, 100, 22, 'url(#surface)') + circle(218, 100, 47, 'url(#surface)')
        return result + moving(path('M50 64 H40 V54 M280 64 H290 V54 M40 146 V136 H50 M280 136 H290 V146', '#79e4f0'), '0 0;0 -6;0 0;0 6;0 0')
    if concept == "procedural-planet-spin":
        sphere = circle(160, 100, 66, 'url(#surface)')
        stripes = ''.join(path(f'M{160-r} 100 Q160 {100-r*.7} {160+r} 100 Q160 {100+r*.7} {160-r} 100', '#376776', 2) for r in (25, 44, 59))
        return sphere + moving(stripes, '0 160 100;360 160 100', kind='rotate', duration=12)
    if concept == "looping-sun-surface":
        disk = circle(160, 100, 65, '#785c32')
        granules = ''.join(circle(160+r*math.cos(a), 100+r*math.sin(a), rng.uniform(1.5, 4), '#d7bc6c', .65) for _ in range(90) for r, a in ((rng.uniform(0, 59), rng.uniform(0, math.tau)),))
        return disk + moving(granules, '0 160 100;12 160 100;0 160 100', kind='rotate', duration=6)
    if concept == "pcb-routing-texture":
        result = rect(27, 22, 266, 156, '#112f2d', 0, 'none')
        for i in range(15):
            x, y = 36+i*17, 35+(i%6)*23
            result += path(f'M{x} 25 V{y} H{x+17} V175', '#5a9b84', 1.5) + circle(x+17, y, 2.5, '#a2cdbc')
        return result
    if concept == "perforated-metal":
        return rect(28, 22, 264, 156, 'url(#metal)', 4, '#466672') + ''.join(circle(x, y, 5, '#091521') for y in range(35, 174, 17) for x in range(41+(8 if y%2 else 0), 282, 18))
    if concept == "fresnel-sheen-sweep":
        return rect(55, 65, 210, 70, '#112635', 6) + moving(path('M60 121 Q155 50 255 82', '#80e8f3', 4), '0 0;0 -12;0 0;0 12;0 0', duration=4) + path('M61 129 H257', '#2d6474')
    if concept == "electron-microscope-look":
        return ''.join(rect(50+i*47, 78-(i%2)*22, 32, 78, '#71858d', 0, '#cfdbdf') for i in range(5)) + ''.join(circle(rng.uniform(25, 295), rng.uniform(30, 178), .7, '#cfdae0', .35) for _ in range(75))
    if concept == "magnification-relief-crossfade":
        flat = rect(35, 51, 250, 98, '#1a4d52', 3) + ''.join(line(40, y, 278, y, '#469d9e') for y in range(60, 143, 11))
        raised = ''.join(path(f'M{x} 65 L{x+23} 54 L{x+23} 133 L{x} 144 Z', '#89e2df', 1, '#245e67') for x in range(51, 260, 40))
        return flat + '<g>' + raised + '<animate attributeName="opacity" values="0;0;1;1;0" dur="6s" repeatCount="indefinite"/></g>'
    if concept == "electron-channel-flow":
        track = path('M38 129 H92 Q114 129 114 104 V94 Q114 71 139 71 H280', '#386774', 13)
        points = ''.join(f'<circle cx="42" cy="129" r="4" fill="#a0f4ee"><animate attributeName="cx" values="42;105;126;279;42" dur="4s" begin="{i*.55}s" repeatCount="indefinite"/><animate attributeName="cy" values="129;129;71;71;129" dur="4s" begin="{i*.55}s" repeatCount="indefinite"/></circle>' for i in range(6))
        return track + points + rect(128, 57, 115, 28, 'none', 3, '#9bc3c5')
    if concept == "hierarchical-chip-explosion":
        board = rect(63, 112, 194, 45, '#133c35')
        blocks = ''.join(rect(82+i*36, 91, 27, 30, '#32818a') for i in range(4))
        inner = ''.join(rect(85+i*23, 65, 14, 13, '#c6eaeb') for i in range(7))
        return board + moving(blocks, '0 18;0 -18;0 -18;0 18', duration=5) + moving(inner, '0 35;0 -16;0 -16;0 35', duration=5)
    if concept == "silicon-diamond-lattice":
        points = [(70+ix*55+iy*18, 48+iz*43+iy*13) for ix in range(3) for iy in range(2) for iz in range(3)]
        bonds = ''.join(line(x1, y1, x2, y2, '#557c89', 1) for i, (x1, y1) in enumerate(points) for x2, y2 in points[i+1:] if 25<math.hypot(x1-x2, y1-y2)<58)
        return bonds + ''.join(circle(x, y, 5, '#a5dbe2') for x, y in points)
    if concept == "transistor-cutaway":
        base = rect(36, 132, 248, 36, '#355a75', 0)
        return base + rect(39, 106, 83, 26, '#386779', 0) + rect(199, 106, 82, 26, '#386779', 0) + rect(133, 72, 56, 60, '#bbcbcf', 0) + rect(133, 125, 56, 7, '#b89a65', 0) + path('M42 117 H99 M224 117 H276', '#88d8e9', 3)
    if concept == "depth-window-point-cloud":
        return ''.join(circle(x, y, r, '#a0d5e4', .25+r*.15) for _ in range(105) for x, y, r in ((rng.uniform(27, 293), rng.uniform(28, 172), rng.uniform(.6, 2.8)),)) + path('M58 155 L115 53 L219 40 L264 140 Z', '#305566', 1)
    if concept == "deformed-limb-shell":
        points = [(160+(61+6*math.sin(a*7))*math.cos(a), 100+(61+6*math.sin(a*7))*math.sin(a)) for i in range(80) for a in (i*math.tau/80,)]
        outline = 'M' + ' L'.join(f'{x:.2f} {y:.2f}' for x, y in points) + ' Z'
        return path(outline, '#75d4e6', 2, '#20394d') + circle(146, 89, 24, '#29485d')
    if concept == "attractor-streamlines":
        result = ''
        for j in range(12):
            points = [(160+(45+j*2.3)*math.sin(t), 100+(58+j*.8)*math.sin(t)*math.cos(t)) for i in range(100) for t in (i*math.tau/99,)]
            result += path('M' + ' L'.join(f'{x:.2f} {y:.2f}' for x, y in points), '#4a8eaa', .8)
        return result
    if concept == "periodic-cosmic-web":
        nodes = [(45+i*54+rng.uniform(-18, 18), 40+j*41+rng.uniform(-12, 12)) for i in range(5) for j in range(4)]
        result = ''.join(line(x1, y1, x2, y2, '#3b6880', .8, .65) for i, (x1, y1) in enumerate(nodes) for x2, y2 in nodes[i+1:] if math.hypot(x1-x2, y1-y2)<72)
        return result + ''.join(circle(x, y, rng.uniform(1, 3), '#86c4db') for x, y in nodes)
    if concept == "galaxy-volume-raymarch":
        arms = ''.join(path('M' + ' L'.join(f'{160+(8+i*.75)*math.cos(i*.13+offset):.2f} {100+(3+i*.31)*math.sin(i*.13+offset):.2f}' for i in range(110)), '#4b82a4', 2.8) for offset in (0, math.pi))
        return circle(160, 100, 43, 'url(#glow)') + moving(arms, '0 160 100;360 160 100', kind='rotate', duration=20)
    if concept == "density-sampled-galaxy-field":
        centers = ((92, 70), (210, 121), (218, 58))
        return ''.join(circle(max(24, min(296, rng.gauss(x, 30))), max(24, min(176, rng.gauss(y, 18))), rng.uniform(.6, 2), '#8ac8df', .75) for _ in range(150) for x, y in (centers[rng.randrange(3)],))
    if concept == "planetary-ring-bands":
        back = ''.join(f'<ellipse cx="160" cy="104" rx="{r}" ry="{r*.24:.2f}" fill="none" stroke="{color}" stroke-width="2"/>' for r, color in ((104, '#acbaa4'), (96, '#576c74'), (86, '#bcc8b5'), (75, '#5b7581')))
        return back + circle(160, 92, 44, 'url(#surface)') + path('M61 113 Q160 144 259 113', '#a2bdbf', 4)
    if concept == "luminosity-and-oblate-halos":
        return '<ellipse cx="161" cy="104" rx="97" ry="68" fill="url(#glow)"/><ellipse cx="161" cy="104" rx="55" ry="38" fill="url(#surface)"/>' + line(106, 104, 216, 104, '#7fb0be', 1, .5)
    if concept == "solar-spicule-corona":
        strands = ''.join(path(f'M{160+52*math.cos(a):.2f} {100+52*math.sin(a):.2f} Q{160+64*math.cos(a+.07):.2f} {100+64*math.sin(a+.07):.2f} {160+78*math.cos(a):.2f} {100+78*math.sin(a):.2f}', '#bfaa65', 1) for i in range(65) for a in (i*math.tau/65,))
        return circle(160, 100, 50, '#bc994b') + moving(strands, '0 160 100;10 160 100;0 160 100', kind='rotate', duration=7)
    raise ValueError("A reviewed component needs its own concept illustration: " + concept)


def bounded_bytes(path, root, limit=2_000_000):
    info = checked_path(path, root)
    if not stat.S_ISREG(info.st_mode) or info.st_size > limit:
        raise ValueError("Promptfilm evidence must be a bounded regular file")
    return path.read_bytes()


def import_items(root=ROOT):
    root = Path(root).resolve()
    upstream = root / "data/upstream/expansion12-promptfilm"
    plan_path = upstream / "import-plan.json"
    plan = json.loads(bounded_bytes(plan_path, root))
    lock = json.loads(bounded_bytes(upstream / "source-lock.json", root))
    if not isinstance(plan, list) or not 1 <= len(plan) <= 1000:
        raise ValueError("Import plan must contain 1 to 1000 reviewed components")
    if lock["revision"] != REVISION or lock["repository"] != REPOSITORY:
        raise ValueError("Promptfilm source revision changed; inspect before importing")
    files = {entry["path"]: entry for entry in lock["files"]}
    notice_path = upstream / "LICENSE"
    notices = {}
    for name in ("LICENSE", "THIRD_PARTY_NOTICES.md"):
        target = upstream / name
        body = bounded_bytes(target, root)
        if hashlib.sha256(body).hexdigest() != files[name]["sha256"]:
            raise ValueError("Upstream license or notice changed")
        notices[name] = body
    notice = notices["LICENSE"]
    license_text = notice.decode("utf-8").strip() + "\n\nUpstream third-party context:\n\n" + notices["THIRD_PARTY_NOTICES.md"].decode("utf-8").strip()
    entries, fingerprints = [], set()
    for spec in plan:
        relative = spec["path"]
        if not isinstance(relative, str) or not re.fullmatch(r"[A-Za-z0-9._/-]{1,300}", relative) or any(part in ("", ".", "..") for part in relative.split("/")):
            raise ValueError("Invalid approved source path")
        if spec["path"] not in files:
            raise ValueError("An unpinned source file was requested")
        source = upstream / "source" / spec["path"]
        body = bounded_bytes(source, root)
        if hashlib.sha256(body).hexdigest() != files[spec["path"]]["sha256"]:
            raise ValueError("Promptfilm original bytes differ from the source lock")
        start, end = spec["startLine"], spec["endLine"]
        if type(start) is not int or type(end) is not int or not 1 <= start <= end <= 100000:
            raise ValueError("Invalid approved source range")
        lines = body.decode("utf-8").splitlines(keepends=True)
        if end > len(lines):
            raise ValueError("Source range exceeds its original file")
        code = "".join(lines[start - 1:end])
        digest = hashlib.sha256(code.encode()).hexdigest()
        if digest != spec["sourceSha256"]:
            raise ValueError("Approved component changed; review its source range")
        classification = {key: spec[key] for key in ("domain", "assetType", "effects", "components", "useCases", "techniques")}
        entry = {"id": "promptfilm-" + spec["id"], "title": spec["title"],
                 "category": spec["assetType"], "kind": "code", "domain": spec["domain"],
                 "language": "javascript", "sourceName": "Promptfilm / Seokwoooo",
                 "sourceUrl": REPOSITORY + "/blob/" + REVISION + "/" + spec["path"] + f"#L{start}-L{end}",
                 "license": "MIT", "licenseUrl": REPOSITORY + "/blob/" + REVISION + "/LICENSE",
                 "licenseText": license_text, "access": "public", "verifiedAt": "2026-10-11",
                 "verification": "source-and-license-reviewed", "description": spec["summaryKO"] + "\n\n" + spec["summaryEN"],
                 "tags": list(dict.fromkeys(["promptfilm", "threejs", "javascript", spec["previewConcept"], *spec["effects"], *spec["components"]])),
                 "colors": [], "code": code, "preview": {"type": "reference", "variant": "reviewed-javascript-source"},
                 "collectionEvidence": {"version": 1,
                     "original": {"path": source.relative_to(root).as_posix(), "sha256": files[spec["path"]]["sha256"]},
                     "notice": {"path": notice_path.relative_to(root).as_posix(), "sha256": hashlib.sha256(notice).hexdigest()},
                     "storedSha256": digest},
                 "sourceReview": {"version": 1, "sourceSha256": digest, "revision": REVISION,
                     "sourceRange": {"startLine": start, "endLine": end}, "classification": classification,
                     "evidence": {"basis": "reviewed-source", "confidence": "high", "summaryKO": spec["summaryKO"],
                         "summaryEN": spec["summaryEN"], "signals": ["pinned-source:" + spec["path"], f"exact-source-lines:{start}-{end}", "concept:" + spec["previewConcept"]]},
                     "dependencies": spec["dependencies"], "limitations": spec["limitations"],
                     "preview": {"mode": "illustration", "language": "svg", "code": illustration(spec["previewConcept"], spec["domain"]),
                         "license": "CC0-1.0", "notice": PREVIEW_NOTICE, "attribution": "Motion Lab", "limitations": PREVIEW_LIMITS}}}
        validate_item(entry)
        validate_source_review(entry, root=root)
        fingerprint = asset_fingerprint(entry)
        if fingerprint in fingerprints:
            raise ValueError("Repeated source component in approved import plan")
        fingerprints.add(fingerprint)
        entries.append(entry)
    write_json(root / "data/expansion12-promptfilm-items.json", entries)
    return entries


if __name__ == "__main__":
    items = import_items()
    print(json.dumps({"imported": len(items), "motion": sum(i["domain"] == "motion" for i in items),
                      "design": sum(i["domain"] == "design" for i in items), "revision": REVISION}))
