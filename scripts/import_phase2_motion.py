"""Pinned motion source import. External source is read as data and never executed.

Default rebuild is offline. --fetch reads allowlisted HTTPS GitHub archives,
checks robots, bounds archive/member sizes and verifies selected Git blob hashes.
Only this importer-owned source cache and phase2-motion-items.json are written.
"""
from __future__ import annotations

import argparse
from collections import Counter
import copy
import gzip
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import sys
import tarfile
import time
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent.parent
LOCAL = ROOT / 'data/upstream/phase2-motion'
OUTPUT = ROOT / 'data/phase2-motion-items.json'
DATE = '2026-10-09'
BASELINE_CATALOG_SHA256 = '84051c3b655b44cf349525b9263015f5aff10d4add9a93c00f406604945fa2d6'
BASELINE_SNAPSHOT_SHA256 = 'eff3b82696e1c71c1b96a9da919d631edc72b4d1f0bc9ddb11d03004067fd3a8'
MAX_FILE = 2 * 1024 * 1024
MAX_ARCHIVE = 80 * 1024 * 1024
MAX_EXPANDED = 450 * 1024 * 1024
UA = 'MotionLab/1.0 (bounded licensed code research; no source execution)'
SOURCES = {
    'css-loaders': {'repo': 'vineethtrv/css-loader', 'commit': 'e9078959e48c39b97613f333c14aac1c3d765c1f', 'name': 'CSS Loaders / Vineeth TR', 'license': 'MIT'},
    'meteocons': {'repo': 'basmilius/meteocons', 'commit': '0ccc40fcff96ac10e325b53d138fed27c4d18afa', 'name': 'Meteocons / Bas Milius', 'license': 'MIT'},
    'paper-shaders': {'repo': 'paper-design/shaders', 'commit': '43cd68db79fa0b1759f72ffc941b3238e2a3954c', 'name': 'Paper Shaders', 'license': 'Apache-2.0'},
    'p5-shaders': {'repo': 'aferriss/p5jsShaderExamples', 'commit': '8034c3771f5d0cd16916a0977593a5b2bf14c308', 'name': 'p5 Shader Examples / Adam Ferriss', 'license': 'MIT'},
}
# These judgments apply only to the fixed CSS Loaders commit above, whose bytes
# are revalidated against the immutable Git tree before every offline rebuild.
CSS_REVIEW = {
    'circle05': ('circle04', 'Same polygon reveal/rotation and two ring layers; the additional inner inset is a ring-size variant.'),
    'circle08': ('circle07', 'Same complete rotating ring and orbit arc; only pseudo-element ring diameter changes.'),
    'circle09': ('circle07', 'Same rotating double-ring footprint and choreography; extra opposite arc is a minor border-paint configuration.'),
    'circle10': ('circle07', 'Same rotating double-ring footprint and choreography with alternate radius/border-paint configuration.'),
    'circle56': ('circle55', 'Same stepped quarter-sector fill; source differs only in paint, fixed 45-degree orientation and duration.'),
    'line08': ('line07', 'Same three staggered expanding bars and width trajectory; expansion anchor/alignment is a close positioning variant rather than a new asset.'),
}


def sha(body):
    return hashlib.sha256(body if isinstance(body, bytes) else body.encode('utf-8')).hexdigest()


def blob_sha(body):
    return hashlib.sha1(b'blob ' + str(len(body)).encode('ascii') + b'\0' + body).hexdigest()


def save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')


def safe_path(value):
    if not isinstance(value, str) or len(value) > 240 or '\\' in value:
        raise ValueError('Invalid source path')
    path = PurePosixPath(value)
    if path.is_absolute() or len(path.parts) > 12 or any(not re.fullmatch(r'[A-Za-z0-9_.-]+', p) or p in ('.', '..') for p in path.parts):
        raise ValueError('Source path outside allowed boundary')
    return path


def selected(slug, path):
    try:
        safe_path(path)
    except ValueError:
        return False
    if path in ('LICENSE', 'NOTICE', 'README.md'):
        return True
    if slug == 'css-loaders':
        return bool(re.fullmatch(r'src/loaders/[a-z]+/[a-z]+\d+\.module\.css', path)) or path in ('src/components/Tile/Tile.tsx', 'src/util/parseLoaderContent.ts', 'src/components/ViewCode/SettingsPanel.tsx', 'src/App.tsx')
    if slug == 'meteocons':
        return bool(re.fullmatch(r'production/line/svg/[a-z0-9-]+\.svg', path))
    if slug == 'paper-shaders':
        return path.startswith('packages/shaders/src/') and path.endswith('.ts') or path.startswith('packages/shaders-react/src/') and path.endswith('.tsx')
    if slug == 'p5-shaders':
        return path.endswith(('.frag', '.vert', '/sketch.js'))
    return False


def source_url(slug, path):
    safe_path(path)
    s = SOURCES[slug]
    return f"https://github.com/{s['repo']}/blob/{s['commit']}/{path}"


def entries(slug):
    directory = LOCAL / slug
    pin = json.loads((directory / 'git-pin.json').read_text(encoding='utf-8'))
    tree = json.loads((directory / 'git-tree.json').read_text(encoding='utf-8'))
    if pin['commit'] != SOURCES[slug]['commit'] or tree['sha'] != pin['commit'] or tree.get('truncated'):
        raise ValueError('Pinned complete tree required')
    return {e['path']: e for e in tree['tree'] if e.get('type') == 'blob' and selected(slug, e['path'])}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *_args, **_kwargs):
        return None


class Collector:
    def __init__(self):
        self.opener = urllib.request.build_opener(NoRedirect())
        self.next_request = 0.0
        self.interval = 1.25
        self.rules = None
        self.stopped = False
        self.log = []

    def request(self, url, maximum):
        p = urllib.parse.urlsplit(url)
        if p.scheme != 'https' or p.hostname != 'codeload.github.com' or p.port not in (None, 443) or p.username or p.password or p.query or p.fragment:
            raise ValueError('Unregistered HTTPS source')
        if p.path != '/robots.txt' and not any(p.path == f"/{s['repo']}/tar.gz/{s['commit']}" for s in SOURCES.values()):
            raise ValueError('Archive URL is not registered and pinned')
        if self.stopped:
            raise ValueError('Collection stopped after rate/access block')
        if p.path != '/robots.txt':
            if self.rules is None or self.rules.get('status') == 'unavailable':
                raise ValueError('robots not reviewed')
            if self.rules.get('parser') and not self.rules['parser'].can_fetch(UA, url):
                raise ValueError('robots disallows collection')
        time.sleep(max(0.0, self.next_request - time.monotonic()))
        self.next_request = time.monotonic() + self.interval
        try:
            with self.opener.open(urllib.request.Request(url, headers={'User-Agent': UA}), timeout=45) as response:
                body = response.read(maximum + 1)
                if len(body) > maximum:
                    raise ValueError('Source response exceeds byte bound')
                self.log.append({'url': url, 'status': response.status, 'bytes': len(body), 'sha256': sha(body)})
                return body
        except urllib.error.HTTPError as error:
            self.log.append({'url': url, 'status': error.code})
            if error.code in (401, 403, 429):
                self.stopped = True
            raise

    def robots(self):
        url = 'https://codeload.github.com/robots.txt'
        try:
            body = self.request(url, 65536)
            (LOCAL / 'robots-codeload.github.com.txt').write_bytes(body)
            parser = urllib.robotparser.RobotFileParser(url)
            parser.parse(body.decode('utf-8', 'replace').splitlines())
            delay = parser.crawl_delay(UA) or parser.crawl_delay('*')
            rate = parser.request_rate(UA) or parser.request_rate('*')
            if delay:
                self.interval = max(self.interval, float(delay))
            if rate and rate.requests:
                self.interval = max(self.interval, rate.seconds / rate.requests)
            self.rules = {'status': 'reviewed', 'url': url, 'sha256': sha(body), 'parser': parser}
        except urllib.error.HTTPError as error:
            self.rules = {'status': 'absent' if error.code in (404, 410) else 'unavailable', 'url': url, 'httpStatus': error.code}
            if self.rules['status'] == 'unavailable':
                raise ValueError('robots unavailable') from error


def fetch_sources():
    collector = Collector(); collector.robots()
    try:
        for slug, spec in SOURCES.items():
            expected = entries(slug)
            if all((LOCAL / slug / path).is_file() for path in expected):
                continue
            url = f"https://codeload.github.com/{spec['repo']}/tar.gz/{spec['commit']}"
            archive = collector.request(url, MAX_ARCHIVE)
            found, expanded, count = set(), 0, 0
            with tarfile.open(fileobj=io.BytesIO(archive), mode='r|gz') as bundle:
                for member in bundle:
                    count += 1; expanded += member.size
                    if count > 20000 or expanded > MAX_EXPANDED:
                        raise ValueError('Archive exceeds member/uncompressed size bounds')
                    # Tar paths never control an extraction call; only registered regular files are written.
                    parts = PurePosixPath(member.name).parts
                    path = '/'.join(parts[1:])
                    if path not in expected:
                        continue
                    safe_path(path)
                    if not member.isfile() or member.size > MAX_FILE or member.size != expected[path]['size']:
                        raise ValueError('Selected artifact type/size differs from Git tree')
                    reader = bundle.extractfile(member)
                    body = reader.read(MAX_FILE + 1)
                    if blob_sha(body) != expected[path]['sha']:
                        raise ValueError('Artifact differs from pinned Git blob')
                    target = (LOCAL / slug / path).resolve(); target.relative_to(LOCAL.resolve())
                    target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(body); found.add(path)
            if found != set(expected):
                raise ValueError('Pinned archive missing selected artifacts')
            print(f'{slug}: downloaded {len(found)} code/notice artifacts', flush=True)
    finally:
        save_json(LOCAL / 'fetch-log.json', collector.log)
        save_json(LOCAL / 'robots-manifest.json', {k: v for k, v in collector.rules.items() if k != 'parser'})


def verify_sources():
    manifests = []
    for slug, spec in SOURCES.items():
        directory = LOCAL / slug; files = []
        for path, entry in entries(slug).items():
            target = (directory / path).resolve()
            target.relative_to(LOCAL.resolve())
            if target.stat().st_size > MAX_FILE:
                raise ValueError('Cached artifact exceeds size bound')
            body = target.read_bytes()
            if len(body) > MAX_FILE or blob_sha(body) != entry['sha']:
                raise ValueError('Cached immutable artifact mismatch: ' + slug + '/' + path)
            files.append({'path': path, 'sha256': sha(body), 'gitBlobSha1': entry['sha'], 'bytes': len(body), 'sourceUrl': source_url(slug, path)})
        notice = (directory / 'LICENSE').read_text(encoding='utf-8')
        if spec['license'] == 'MIT' and not all(s in notice for s in ('Permission is hereby granted', 'THE SOFTWARE IS PROVIDED', 'Copyright')):
            raise ValueError('Full MIT notice not present')
        if spec['license'] == 'Apache-2.0' and not all(s in notice for s in ('Apache License', 'Version 2.0', 'END OF TERMS AND CONDITIONS')):
            raise ValueError('Full Apache license not present')
        manifests.append({'source': slug, **spec, 'files': files})
    save_json(LOCAL / 'manifest.json', manifests)
    return manifests


def item_base(slug, path, code, language, category, title, preview, adaptations=None):
    spec = SOURCES[slug]
    body = (LOCAL / slug / path).read_bytes()
    notice = (LOCAL / slug / 'LICENSE').read_text(encoding='utf-8')
    relative = str((LOCAL / slug / path).relative_to(ROOT)).replace('\\', '/')
    stem = Path(path).stem.removesuffix('.module')
    item = {'id': 'phase2-motion-' + slug + '-' + stem, 'title': title,
        'description': '원본 모션의 전체 구성과 애니메이션 선언을 보존한 코드 에셋입니다. 실행 가능한 원본 스크립트 없이 CSS 또는 SVG를 표시합니다.',
        'category': category, 'domain': 'motion', 'kind': 'code', 'access': 'public', 'language': language,
        'tags': [language, 'motion', '모션'], 'colors': list(dict.fromkeys(re.findall(r'#[a-fA-F0-9]{6}\b|#[a-fA-F0-9]{3}\b', code)))[:32],
        'sourceUrl': source_url(slug, path), 'sourceName': spec['name'], 'license': spec['license'],
        'licenseUrl': source_url(slug, 'LICENSE'), 'licenseText': notice,
        'verifiedAt': DATE, 'verification': 'source-and-license-reviewed', 'upstreamCommit': spec['commit'],
        'sourceCommit': spec['commit'], 'upstreamSha256': sha(body), 'codePath': relative, 'code': code, 'preview': preview,
        'evidence': {'scope': 'individual-complete-composition', 'sourceCommit': spec['commit'],
            'artifactPath': relative, 'artifactSha256': sha(body), 'assetSourceSha256': sha(body), 'storedCodeSha256': sha(code),
            'sourceUrls': [source_url(slug, path), source_url(slug, 'LICENSE')], 'sourceExecution': False,
            'externalResources': False, 'adaptations': adaptations or 'No source animation or geometry values changed.',
            'rights': 'Pinned complete author copyright, permission and warranty notice retained.'}}
    return item


def css_items():
    from scripts.duplicate_audit_css import parse_rules, strip_comments, walk_rules
    slug = 'css-loaders'; directory = LOCAL / slug
    tile = (directory / 'src/components/Tile/Tile.tsx').read_text(encoding='utf-8')
    parser = (directory / 'src/util/parseLoaderContent.ts').read_text(encoding='utf-8')
    if '<span className={styleSheet.loader}>{content}</span>' not in tile or '@content' not in parser:
        raise ValueError('CSS source DOM or content parser changed')
    result = []
    for path in sorted(entries(slug)):
        if not path.endswith('.module.css'):
            continue
        raw = (directory / path).read_text(encoding='utf-8')
        clean = strip_comments(raw)
        if re.search(r'url\s*\(|@import|expression\s*\(|javascript:|behavior\s*:', clean, re.I):
            raise ValueError('External or active CSS excluded')
        rules = parse_rules(clean)
        frames = [re.fullmatch(r'@keyframes\s+([\w-]+)', r['header']).group(1) for r in walk_rules(rules) if re.fullmatch(r'@keyframes\s+([\w-]+)', r['header'])]
        if not frames or not re.search(r'animation(?:-name)?\s*:', clean):
            raise ValueError('No actual loader animation')
        content = re.search(r'/\*\s*@content:\s*"([^"]+)"\s*\*/', raw)
        dom = {'tag': 'span', 'className': 'loader'}
        if content:
            dom['text'] = content[1]
        family = PurePosixPath(path).parent.name
        words = {'bubble': 'Bubble', 'circle': 'Orbit', 'graph': 'Graph', 'line': 'Line', 'objects': 'Object', 'progress': 'Progress', 'rect': 'Bar', 'skeleton': 'Skeleton', 'text': 'Text'}
        name = Path(path).stem.removesuffix('.module')
        notice = (directory / 'LICENSE').read_text(encoding='utf-8')
        preview_css = raw
        adaptation = None
        if name == 'text04':
            literal = "'L \\00a0\\00a0 ading'"
            if raw.count(literal) != 1:
                raise ValueError('Pinned CSS literal decoding requires exact reviewed text04 source')
            # CSS consumes the one space after its second hex escape. Preserve
            # the displayed text exactly while keeping the runtime escape guard.
            preview_css = raw.replace(literal, "'L \u00a0\u00a0ading'")
            adaptation = 'Two source CSS \\00a0 content escapes decoded to literal nonbreaking-space characters with the CSS escape terminator consumed. Displayed text, geometry and choreography are unchanged; original raw CSS retained at codePath.'
        code = '/* ' + SOURCES[slug]['name'] + ' / MIT\n' + notice + '\nSource: ' + source_url(slug, path) + '\n*/\n' + preview_css
        item = item_base(slug, path, code, 'css', 'typography' if family == 'text' else 'loader',
            words[family] + ' Loader ' + re.search(r'\d+', name)[0],
            {'type': 'css', 'variant': name, 'dom': dom, 'adapted': bool(adaptation)}, adaptation)
        item['tags'] += [family, 'loader', '로더']
        item['evidence'].update({'originalDom': copy.deepcopy(dom), 'sourceDomPath': 'data/upstream/phase2-motion/css-loaders/src/components/Tile/Tile.tsx',
            'sourceDomSha256': sha(tile), 'sourceTextParserSha256': sha(parser), 'keyframes': frames,
            'fullDOMPreserved': True, 'fullCSSPreserved': raw in code,
            'cssLiteralEscapesDecoded': bool(adaptation), 'pseudoElementsPreserved': True})
        result.append(item)
    return result


def svg_items(skipped):
    from scripts.duplicate_audit_svg import _parse
    slug = 'meteocons'; result = []
    for path in sorted(entries(slug)):
        if not path.endswith('.svg'):
            continue
        raw = (LOCAL / slug / path).read_text(encoding='utf-8')
        if re.search(r'<!\s*(?:DOCTYPE|ENTITY)\b', raw, re.I):
            raise ValueError('SVG DTD/entity forbidden')
        root = ET.fromstring(raw)
        animations = [n for n in root.iter() if n.tag.split('}')[-1] in ('animate', 'animateTransform', 'animateMotion', 'set')]
        if not animations:
            skipped.append({'source': slug, 'path': path, 'reason': 'static-scene-no-animation'}); continue
        name = Path(path).stem
        notice = (LOCAL / slug / 'LICENSE').read_text(encoding='utf-8')
        if '--' in notice:
            raise ValueError('License incompatible with safe XML comment')
        code = '<!-- ' + SOURCES[slug]['name'] + ' / MIT\n' + notice + '\nSource: ' + source_url(slug, path) + '\n-->\n' + raw
        item = item_base(slug, path, code, 'svg', 'animation', ' '.join(word.capitalize() for word in name.split('-')) + ' Weather Motion',
            {'type': 'svg', 'variant': name, 'adapted': False, 'limitations': ['Single line style; other styles and static formats are not additional entries.']})
        item['tags'] += ['weather', 'SMIL', '날씨']
        item['evidence'].update({'fullDOMPreserved': True, 'animationElements': len(animations), 'styleVariant': 'line',
            'originalSvgSha256': sha(raw), 'localSymbolReferencesOnly': True})
        try:
            _parse(item)
        except (ValueError, ET.ParseError) as exc:
            skipped.append({'source': slug, 'path': path, 'reason': 'unsafe-or-ambiguous-source-SVG', 'detail': str(exc)})
            continue
        result.append(item)
    return result


def original_baseline(catalog):
    """Include current repaired composition AND every preserved original code body."""
    result, keys = [], set()
    for current in catalog['items']:
        candidates = [current, *current.get('variants', [])]
        if current.get('repair', {}).get('originalRecord'):
            candidates.append(current['repair']['originalRecord'])
        for item in candidates:
            key = (item['id'], sha(item.get('code') or ''))
            if key in keys:
                continue
            keys.add(key)
            value = copy.deepcopy(item)
            value['id'] = 'baseline-' + str(len(result)) + '-' + item['id']
            value['baselineOriginalId'] = item['id']
            result.append(value)
    return result


def fixed_baseline():
    """Offline rebuild must never compare an imported item against itself."""
    path = LOCAL / 'baseline-code.json.gz'
    body = path.read_bytes()
    if len(body) > 8 * 1024 * 1024 or sha(body) != BASELINE_SNAPSHOT_SHA256:
        raise ValueError('Fixed pre-expansion baseline snapshot hash mismatch')
    with gzip.open(path, 'rb') as reader:
        raw = reader.read(100 * 1024 * 1024 + 1)
    if len(raw) > 100 * 1024 * 1024:
        raise ValueError('Baseline snapshot exceeds bound')
    document = json.loads(raw)
    if document['catalogSha256'] != BASELINE_CATALOG_SHA256 or document['canonicalCount'] != 6074:
        raise ValueError('Unexpected pre-expansion catalog baseline')
    return document


def paintless_css(item):
    value = copy.deepcopy(item)
    code = value['code']
    code = re.sub(r'#[0-9a-fA-F]{3,8}\b|\b(?:rgba?|hsla?)\([^()]*\)|\b(?:white|black|red|blue|green|yellow|orange|cyan|magenta|transparent|currentColor)\b', 'ml-paint', code)
    value['code'] = code
    return value


def paintless_svg(item):
    value = copy.deepcopy(item)
    root = ET.fromstring(value['code'])
    for node in root.iter():
        for key in ('fill', 'stroke', 'stop-color'):
            if key in node.attrib and node.attrib[key] not in ('none',) and not node.attrib[key].startswith('url('):
                node.attrib[key] = 'currentColor'
    value['code'] = ET.tostring(root, encoding='unicode')
    return value


def filter_duplicates(items, baseline):
    from scripts.duplicate_audit_css import record
    from scripts.duplicate_audit_svg import _parse, _geometry_pair
    indexes = {'css': {}, 'svg': {}}
    geometry = {}
    old_errors, removed, kept = [], [], []

    def identities(item):
        if item['language'] == 'css':
            r = record(item); p = record(paintless_css(item))
            return r, [('exact', r['exact']), ('timing-only', r['timeless']), ('paint-or-timing-only', p['shapeTimeless'])]
        r = _parse(item); p = _parse(paintless_svg(item))
        return r, [('exact', r['exact']), ('timing-only', r['timing']), ('paint-or-timing-only', p['timing'])]

    for item in baseline:
        if item.get('kind') != 'code' or item.get('language') not in indexes:
            continue
        try:
            record_value, keys = identities(item)
            for kind, key in keys:
                indexes[item['language']].setdefault((kind, key), item)
            if item['language'] == 'svg':
                geometry.setdefault(record_value['skeleton'], []).append((item, record_value))
        except (ValueError, TypeError, KeyError, ET.ParseError) as exc:
            old_errors.append({'id': item['baselineOriginalId'], 'language': item['language'], 'reason': str(exc)})
    for item in sorted(items, key=lambda x: x['id']):
        r, keys = identities(item)
        duplicate = next(((kind, indexes[item['language']][(kind, key)]) for kind, key in keys if (kind, key) in indexes[item['language']]), None)
        if not duplicate and item['language'] == 'svg':
            for other, other_record in geometry.get(r['skeleton'], []):
                if _geometry_pair(r, other_record):
                    duplicate = ('small-geometry-near-conservatively-held', other); break
        if duplicate:
            reason, retained = duplicate
            removed.append({'id': item['id'], 'reason': reason, 'retainedId': retained.get('baselineOriginalId', retained['id']),
                'sourceUrl': item['sourceUrl'], 'codeSha256': sha(item['code']), 'retainedCodeSha256': sha(retained['code'])})
            continue
        kept.append(item)
        for kind, key in keys:
            indexes[item['language']][(kind, key)] = item
        if item['language'] == 'svg':
            geometry.setdefault(r['skeleton'], []).append((item, r))
    return kept, removed, old_errors


def make_items():
    sys.path.insert(0, str(ROOT))
    from scripts.build import validate_item
    from scripts.analyze import analyze_items
    fixed = fixed_baseline()
    baseline = fixed['codeBodies']
    skipped = []
    candidates = css_items() + svg_items(skipped)
    for item in candidates:
        validate_item(item)
    result, duplicates, baseline_errors = filter_duplicates(candidates, baseline)
    by_id = {item['id']: item for item in candidates}
    reviewed_excluded = set()
    for rejected, (retained, reason) in CSS_REVIEW.items():
        rejected_id = 'phase2-motion-css-loaders-' + rejected
        retained_id = 'phase2-motion-css-loaders-' + retained
        a, b = by_id[rejected_id], by_id[retained_id]
        reviewed_excluded.add(rejected_id)
        duplicates.append({'id': rejected_id, 'retainedId': retained_id, 'reason': 'reviewed-source-composition-variant',
            'reviewBasis': reason, 'sourceCommit': SOURCES['css-loaders']['commit'], 'sourceUrl': a['sourceUrl'],
            'codeSha256': sha(a['code']), 'retainedCodeSha256': sha(b['code']), 'browserFramesCompared': False})
    result = [item for item in result if item['id'] not in reviewed_excluded]
    result = analyze_items(result)
    for item in result:
        validate_item(item)
        if sha(item['code']) != item['evidence']['storedCodeSha256'] or item['licenseText'].strip() not in item['code']:
            raise ValueError('Stored code/license integrity mismatch')
    report = {'date': DATE, 'catalogSha256': BASELINE_CATALOG_SHA256, 'baselineCanonicalCount': fixed['canonicalCount'],
        'baselineSnapshotSha256': BASELINE_SNAPSHOT_SHA256,
        'baselineOriginalAndRepairedBodies': fixed['originalAndRepairedCount'], 'baselineComparedCSSAndSVG': len(baseline),
        'candidateCount': len(candidates), 'retainedCount': len(result),
        'sources': dict(Counter(item['sourceName'] for item in result)), 'languages': dict(Counter(item['language'] for item in result)),
        'duplicatesExcluded': duplicates, 'skipped': skipped, 'baselineParseErrors': baseline_errors,
        'reviewedDistinctCandidates': [
            {'ids': ['circle13', 'circle18'], 'basis': 'Circular orbiting ball versus a long radial clock-hand geometry.'},
            {'ids': ['bubble21', 'rect20'], 'basis': 'Same spin choreography but circular balls versus square boxes are materially different design shapes.'},
            {'ids': ['skeleton07', 'skeleton08'], 'basis': 'Circular avatar footprint versus rectangular thumbnail footprint in a shimmer skeleton.'}],
        'validation': {'pinnedGitBlobVerified': True, 'fullLicenseNotices': True, 'fullSourceDOM': True,
            'allCanonicalVariantsAndRepairOriginalRecordsCompared': True, 'sourceExecution': False, 'browserFramesCompared': False},
        'heldSources': [
            {'source': 'Paper Shaders', 'count': 30, 'reason': 'WebGL2 vertex sizing, sampled randomizer textures and uniform arrays need an exact renderer adapter; no generic stand-in preview or TS execution used.'},
            {'source': 'p5 Shader Examples', 'count': 40, 'reason': 'Most are static filters, teaching variants, webcam feedback or vertex/geometry examples. No p5 runtime or camera/media source is executed; raw source kept for later renderer review.'}],
        'limits': ['Static exact/timing/paint/numeric-geometry comparison does not prove perceptual uniqueness across arbitrary equivalent CSS/geometry formulations.',
            'Framework ports, static SVG weather versions and alternative styles are excluded from new motion counts.',
            'Animation geometry and values are original; SVG symbol/use support in the site sanitizer is required.']}
    save_json(OUTPUT, result); save_json(LOCAL / 'report.json', report)
    print(json.dumps({k: report[k] for k in ('candidateCount', 'retainedCount', 'sources', 'languages')}, ensure_ascii=True), flush=True)
    print('duplicates=' + str(len(duplicates)) + ' static=' + str(len(skipped)) + ' baselineParseErrors=' + str(len(baseline_errors)), flush=True)
    return result, report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fetch', action='store_true')
    parser.add_argument('--sources-only', action='store_true')
    options = parser.parse_args()
    LOCAL.mkdir(parents=True, exist_ok=True)
    if options.fetch:
        fetch_sources()
    verify_sources()
    if not options.sources_only:
        make_items()


if __name__ == '__main__':
    main()
