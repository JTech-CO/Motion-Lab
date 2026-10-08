"""Import exact, stored upstream palette arrays; never invent palette variants.

All downloads use registered public GitHub repositories, robots checks, pinned
commits, bounded HTTPS responses, byte hashes and complete source notices.
Discovery does not execute downloaded R/Python/JavaScript.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import gzip
import io
import json
from pathlib import Path
import re
import struct
import sys
import unicodedata
import time
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser

ROOT = Path(__file__).resolve().parents[1]
UPSTREAM = ROOT / 'data' / 'upstream' / 'color-wave'
UA = 'MotionLab/1.0 (public palette research; bounded read-only source retrieval)'
HOSTS = {'api.github.com', 'raw.githubusercontent.com', 'github.com', 'creativecommons.org'}
MAX_BYTES = 8_000_000
BASELINE_SHA256 = 'f2ebd6f8bc587dd935638fdce56e21fd85d5cf0686417cceb0595245ca2d6214'
REPOSITORIES = {
    'paletteer': 'EmilHvitfeldt/paletteer',
    'pypalettes': 'y-sunflower/pypalettes',
    'colorbrewer': 'axismaps/colorbrewer',
    'cartocolor': 'CartoDB/CartoColor',
    'palettetown': 'timcdlucas/palettetown',
    'beyonce': 'dill/beyonce',
    'nbapalettes': 'murrayjw/nbapalettes',
    'lisa': 'tylerlittlefield/lisa',
    'colRoz': 'jacintak/colRoz',
    'MetBrewer': 'BlakeRMills/MetBrewer',
    'PrettyCols': 'nrennie/PrettyCols',
    'poisonfrogs': 'laurenoconnelllab/poisonfrogs',
    'radix-colors': 'radix-ui/colors',
    'tailwindcss': 'tailwindlabs/tailwindcss',
}
FETCH_PATHS = {
    'paletteer': ['DESCRIPTION', 'LICENSE.note', 'README.md', 'data-raw/palettes_d.json',
                  'data-raw/palettes_d.R', 'data-raw/palettes_d_names.csv',
                  'data-raw/paletteer_packages.csv', 'data-raw/palettes_dynamic.json'],
    'pypalettes': ['LICENSE.note', 'README.md', 'pypalettes/palettes.csv'],
    'colorbrewer': ['export/LICENSE.txt', 'export/colorbrewer.json', 'README.md'],
    'palettetown': ['DESCRIPTION', 'LICENSE', 'README.md', 'R/palettetown.R', 'R/sysdata.rda', 'R/extraPals.R'],
    'beyonce': ['DESCRIPTION', 'README.md', 'R/beyonce.R', 'data/beyonce_palettes.RData'],
    'nbapalettes': ['DESCRIPTION', 'LICENSE', 'LICENSE.md', 'README.md', 'R/nbapalette.R', 'R/colors.R'],
    'cartocolor': ['README.md', 'package.json', 'src/carto.ts'],
    'lisa': ['DESCRIPTION', 'LICENSE', 'LICENSE.md', 'README.md', 'inst/extdata/palettes.yml'],
    'colRoz': ['DESCRIPTION', 'LICENSE.txt', 'README.md', 'R/oz_palettes.R'],
    'MetBrewer': ['DESCRIPTION', 'LICENSE.md', 'README.md', 'R/PaletteCode.R', 'Python/met_brewer/palettes.py'],
    'PrettyCols': ['DESCRIPTION', 'LICENSE.md', 'README.md', 'R/prettycols.R', 'R/PrettyColsPalettes.R'],
    'poisonfrogs': ['DESCRIPTION', 'LICENSE', 'LICENSE.md', 'README.md', 'R/poison_frog_palettes.R'],
    'radix-colors': ['LICENSE', 'README.md', 'src/light.ts', 'src/dark.ts'],
    'tailwindcss': ['LICENSE', 'packages/tailwindcss/theme.css'],
}
ROBOTS = {}
REQUESTS = []
ARTIFACTS = []
VERIFIED_CACHE = {}


def verified_bytes(key, path):
    """Read only audited source bytes, with bounds and no path escape."""
    target = (UPSTREAM / key / path).resolve()
    if not target.is_relative_to(UPSTREAM.resolve()) or not target.is_file():
        raise ValueError('Source artifact is missing or outside the wave directory')
    relative = target.relative_to(ROOT).as_posix()
    if relative in VERIFIED_CACHE:
        return VERIFIED_CACHE[relative]
    audit_path = UPSTREAM / 'source-audit.json'
    if not audit_path.is_file() or audit_path.stat().st_size > MAX_BYTES:
        raise ValueError('Bounded source audit is required before offline extraction')
    audit = json.loads(audit_path.read_text(encoding='utf-8'))
    matches = [entry for entry in audit['artifacts'] if entry['path'] == relative]
    if len(matches) != 1 or target.stat().st_size > MAX_BYTES:
        raise ValueError('Source artifact audit is ambiguous or exceeds its byte bound')
    payload = target.read_bytes()
    entry = matches[0]
    if len(payload) != entry['bytes'] or hashlib.sha256(payload).hexdigest() != entry['sha256']:
        raise ValueError('Source artifact bytes differ from the immutable retrieval audit')
    VERIFIED_CACHE[relative] = payload
    return payload


def request(url, *, robots=True):
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != 'https' or parsed.hostname not in HOSTS or parsed.port not in (None, 443) or parsed.username or parsed.password:
        raise ValueError('Unregistered HTTPS source host')
    if robots:
        policy = ROBOTS.get(parsed.hostname)
        if not policy or policy['status'] == 'unavailable':
            raise ValueError('robots unavailable; automated source collection denied')
        if policy.get('parser') and not policy['parser'].can_fetch(UA, url):
            raise ValueError('robots disallow; automated source collection denied')
    req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept': 'application/json,text/plain;q=0.9'})
    started = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=25) as response:
            final = urllib.parse.urlsplit(response.geturl())
            if final.scheme != 'https' or final.hostname not in HOSTS or final.port not in (None, 443) or final.username or final.password:
                raise ValueError('Redirect outside registered source hosts')
            payload = response.read(MAX_BYTES + 1)
            if len(payload) > MAX_BYTES:
                raise ValueError('Response exceeds bounded size')
            REQUESTS.append({'url': url, 'status': response.status, 'bytes': len(payload),
                             'sha256': hashlib.sha256(payload).hexdigest(),
                             'retrievedAt': datetime.now(timezone.utc).isoformat(),
                             'seconds': round(time.monotonic() - started, 3)})
            return payload
    except urllib.error.HTTPError as error:
        REQUESTS.append({'url': url, 'status': error.code, 'error': type(error).__name__,
                         'retrievedAt': datetime.now(timezone.utc).isoformat()})
        raise


def save(path, payload, url, **metadata):
    target = UPSTREAM / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(payload)
    artifact = {'path': str(target.relative_to(ROOT)).replace('\\', '/'), 'url': url,
                'bytes': len(payload), 'sha256': hashlib.sha256(payload).hexdigest(), **metadata}
    ARTIFACTS.append(artifact)
    return artifact


def check_robots(host):
    url = f'https://{host}/robots.txt'
    try:
        payload = request(url, robots=False)
        save(f'robots-{host}.txt', payload, url)
        parser = urllib.robotparser.RobotFileParser(url)
        parser.parse(payload.decode('utf-8', errors='strict').splitlines())
        ROBOTS[host] = {'status': 'reviewed', 'url': url, 'parser': parser}
    except urllib.error.HTTPError as error:
        ROBOTS[host] = {'status': 'absent' if error.code in (404, 410) else 'unavailable',
                        'url': url, 'httpStatus': error.code}
    except (OSError, ValueError) as error:
        ROBOTS[host] = {'status': 'unavailable', 'url': url, 'error': str(error)}


def discover(keys):
    path = UPSTREAM / 'discovery.json'
    manifest = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {'verifiedAt': '2026-10-09', 'repositories': {}}
    previous_artifacts = manifest.get('artifacts', [])
    for key in keys:
        repository = REPOSITORIES[key]
        url = f'https://api.github.com/repos/{repository}/commits/HEAD'
        payload = request(url)
        commit = json.loads(payload)['sha']
        save(f'{key}/commit.json', payload, url, repository=repository, sourceCommit=commit)
        url = f'https://api.github.com/repos/{repository}/git/trees/{commit}?recursive=1'
        payload = request(url)
        tree = json.loads(payload)
        if tree.get('truncated'):
            raise ValueError('Source tree is truncated')
        save(f'{key}/tree.json', payload, url, repository=repository, sourceCommit=commit)
        paths = [entry['path'] for entry in tree['tree'] if entry['type'] == 'blob']
        manifest['repositories'][key] = {'repository': repository, 'sourceCommit': commit, 'paths': paths}
        print(key, commit, len(paths), 'files')
        print('\n'.join(path for path in paths if any(term in path.lower() for term in ('license', 'palette', 'description', 'cartocolor', 'colorbrewer')) and len(path.split('/')) < 4)[:9000])
        manifest['artifacts'] = previous_artifacts
        finish(manifest, 'discovery.json')
    manifest['artifacts'] = previous_artifacts
    finish(manifest, 'discovery.json')


def web_discover(keys):
    """Review allowed repository roots, not API/commit/tree disallowed routes."""
    path = UPSTREAM / 'discovery.json'
    manifest = json.loads(path.read_text(encoding='utf-8'))
    for key in keys:
        repository = REPOSITORIES[key]
        url = f'https://github.com/{repository}'
        payload = request(url)
        html = payload.decode('utf-8', errors='strict')
        found = re.search(r'"currentOid":"([0-9a-f]{40})"', html)
        if not found:
            raise ValueError('Repository root did not expose an immutable currentOid')
        commit = found.group(1)
        save(f'{key}/repository.html', payload, url, repository=repository, sourceCommit=commit)
        manifest['repositories'][key] = {'repository': repository, 'sourceCommit': commit,
                                          'paths': [], 'discovery': 'allowed-repository-root-currentOid'}
        print(key, commit)
    finish(manifest, 'discovery.json')


def fetch(keys):
    discovery = json.loads((UPSTREAM / 'discovery.json').read_text(encoding='utf-8'))
    for key in REPOSITORIES:
        tree_path = UPSTREAM / key / 'tree.json'
        commit_path = UPSTREAM / key / 'commit.json'
        if key not in discovery['repositories'] and tree_path.is_file() and commit_path.is_file():
            discovery['repositories'][key] = {
                'repository': REPOSITORIES[key],
                'sourceCommit': json.loads(commit_path.read_text())['sha'],
                'paths': [entry['path'] for entry in json.loads(tree_path.read_text())['tree'] if entry['type'] == 'blob']}
    manifest_path = UPSTREAM / 'fetch.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8')) if manifest_path.exists() else {'verifiedAt': '2026-10-09', 'repositories': {}}
    for key in keys:
        repository = discovery['repositories'][key]
        commit = repository['sourceCommit']
        manifest['repositories'][key] = {name: repository[name] for name in ('repository', 'sourceCommit')}
        for path in FETCH_PATHS[key]:
            if repository['paths'] and path not in repository['paths']:
                print('missing', key, path)
                continue
            url = f"https://raw.githubusercontent.com/{repository['repository']}/{commit}/{path}"
            existing = UPSTREAM / key / path
            if existing.is_file():
                print('cached', key, path, existing.stat().st_size, 'bytes')
                continue
            try:
                payload = request(url)
            except urllib.error.HTTPError as error:
                if error.code == 404:
                    print('missing', key, path)
                    continue
                finish(manifest, 'fetch.json')
                raise
            save(f'{key}/{path}', payload, url, repository=repository['repository'],
                 sourceCommit=commit, artifactPath=path)
            print(key, path, len(payload), 'bytes')
        finish(manifest, 'fetch.json')
    finish(manifest, 'fetch.json')


def finish(manifest, filename):
    manifest['robots'] = {host: {key: value for key, value in policy.items() if key != 'parser'}
                          for host, policy in ROBOTS.items()}
    manifest['requests'] = list({json.dumps(row, sort_keys=True): row for row in manifest.get('requests', []) + REQUESTS}.values())
    manifest['artifacts'] = list({(row['path'], row['url'], row['sha256']): row for row in manifest.get('artifacts', []) + ARTIFACTS}.values())
    UPSTREAM.mkdir(parents=True, exist_ok=True)
    (UPSTREAM / filename).write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')


class RDataReader:
    """Bounded non-executing reader for simple RDX2 palette data types only.

    Format reference: R Internals, section 1.8 Serialization Formats.
    Closures, environments, bytecode and unknown objects fail closed.
    """
    def __init__(self, payload):
        with gzip.GzipFile(fileobj=io.BytesIO(payload)) as compressed:
            data = compressed.read(MAX_BYTES + 1)
        if len(data) > MAX_BYTES or not data.startswith(b'RDX2\nX\n'):
            raise ValueError('Unsupported or oversized R data format')
        self.data, self.position, self.references, self.nodes = data, 7, [], 0
        if self.integer() != 2:
            raise ValueError('Only version-2 XDR data is supported')
        self.integer()
        self.integer()

    def take(self, length):
        if length < 0 or length > MAX_BYTES or self.position + length > len(self.data):
            raise ValueError('R data length outside bounds')
        value = self.data[self.position:self.position + length]
        self.position += length
        return value

    def integer(self):
        return struct.unpack('>i', self.take(4))[0]

    def read(self, depth=0):
        self.nodes += 1
        if depth > 64 or self.nodes > 100_000:
            raise ValueError('R object complexity exceeds bounds')
        flags = self.integer()
        kind = flags & 255
        if kind == 254:
            return None
        if kind == 255:
            reference = flags >> 8 or self.integer()
            if not 1 <= reference <= len(self.references):
                raise ValueError('Invalid R symbol reference')
            return self.references[reference - 1]
        result = {'type': kind, 'value': None, 'attributes': None}
        if kind == 1:
            result['value'] = self.read(depth + 1)['value']
            self.references.append(result)
            return result
        if kind == 2:
            if flags & 512:
                result['attributes'] = self.read(depth + 1)
            result['tag'] = self.read(depth + 1) if flags & 1024 else None
            result['value'] = self.read(depth + 1)
            result['next'] = self.read(depth + 1)
            return result
        if kind == 9:
            length = self.integer()
            result['value'] = None if length == -1 else self.take(length).decode('utf-8', errors='strict')
        elif kind in (10, 13, 14, 16, 19):
            length = self.integer()
            if not 0 <= length <= 100_000:
                raise ValueError('R vector length exceeds bounds')
            if kind in (16, 19):
                result['value'] = [self.read(depth + 1) for _ in range(length)]
            elif kind in (10, 13):
                result['value'] = [self.integer() for _ in range(length)]
            else:
                result['value'] = [struct.unpack('>d', self.take(8))[0] for _ in range(length)]
        else:
            raise ValueError(f'Unsupported R type {kind} at {self.position}')
        if flags & 512:
            result['attributes'] = self.read(depth + 1)
        return result


def r_named_list(node):
    if not node or node['type'] != 19:
        raise ValueError('Expected an R vector list')
    attributes = node['attributes']
    names = None
    while attributes:
        if attributes['tag'] and attributes['tag']['value'] == 'names':
            names = [entry['value'] for entry in attributes['value']['value']]
        attributes = attributes['next']
    if not names or len(names) != len(node['value']) or len(set(names)) != len(names):
        raise ValueError('R palette names do not align uniquely with values')
    return dict(zip(names, node['value']))


def palettetown_palettes():
    reader = RDataReader(verified_bytes('palettetown', 'R/sysdata.rda'))
    node = reader.read()
    if reader.position != len(reader.data):
        raise ValueError('Trailing unparsed R data')
    while node and node['tag']['value'] != 'pokeColours':
        node = node['next']
    if not node:
        raise ValueError('Original pokeColours data is missing')
    palettes = r_named_list(node['value'])
    if any(value['type'] != 16 for value in palettes.values()):
        raise ValueError('Palette data must contain only stored string vectors')
    return {name: [entry['value'] for entry in value['value']] for name, value in palettes.items()}


def text(key, path):
    return verified_bytes(key, path).decode('utf-8-sig', errors='strict')


def r_literal_palettes(source, nested=False):
    """Read only literal named c(HEX, ...) vectors; never eval R expressions."""
    pattern = r'([\w.]+)\s*=\s*' + (r'(?:list|rbind)\s*\(\s*' if nested else '') + r'c\s*\(([^()]*)\)'
    result = {}
    for match in re.finditer(pattern, source, re.S):
        values = re.findall(r'[\"\'](#[0-9a-fA-F]{3,8})[\"\']', match.group(2))
        remainder = re.sub(r'[\"\']#[0-9a-fA-F]{3,8}[\"\']|[\s,]', '', match.group(2))
        if values and not remainder:
            if match.group(1) in result:
                raise ValueError('Repeated original palette name')
            result[match.group(1)] = values
    return result


def lisa_palettes():
    result, current = {}, None
    for line in text('lisa', 'inst/extdata/palettes.yml').splitlines():
        if not line.strip():
            continue
        if re.fullmatch(r'[^:\n]+:', line):
            current = line[:-1]
            result[current] = []
        else:
            match = re.fullmatch(r"- '(#[0-9a-fA-F]{6})'", line)
            if not match or not current:
                raise ValueError('Unexpected Lisa YAML structure')
            result[current].append(match.group(1))
    return result


def colorbrewer_palettes():
    schemes = json.loads(text('colorbrewer', 'export/colorbrewer.json'))
    result = []
    for name, values in schemes.items():
        for size, colors in values.items():
            if not size.isdigit():
                continue
            if len(colors) != int(size):
                raise ValueError('Original Brewer size and vector length differ')
            exact = []
            for color in colors:
                match = re.fullmatch(r'rgb\((\d+),(\d+),(\d+)\)', color)
                if not match or any(int(n) > 255 for n in match.groups()):
                    raise ValueError('Unexpected original Brewer color')
                exact.append('#' + ''.join(f'{int(n):02x}' for n in match.groups()))
            result.append((f'{name}-{size}', exact, {'name': name, 'size': int(size),
                          'type': values['type'], 'originalColors': colors,
                          'conversion': 'Exact integer RGB to HEX notation only'}))
    return result


def carto_palettes():
    result = []
    for match in re.finditer(r'export const (\w+) = \{(.*?)\};', text('cartocolor', 'src/carto.ts'), re.S):
        for row in re.finditer(r'(\d+):\s*\[(.*?)\]', match.group(2), re.S):
            colors = re.findall(r'"(#[0-9a-fA-F]{3,8})"', row.group(2))
            if not colors:
                raise ValueError('Original CARTO stored palette is empty')
            result.append((f'{match.group(1)}-{row.group(1)}', colors,
                          {'name': match.group(1), 'variantKey': int(row.group(1)), 'size': len(colors),
                           'originalColors': colors, 'note': 'Variant key and actual stored array length are preserved separately; categorical schemes include their final neutral color.'}))
    return result


def radix_palettes():
    result = []
    for theme in ('light', 'dark'):
        for match in re.finditer(r'export const (\w+) = \{(.*?)\};', text('radix-colors', f'src/{theme}.ts'), re.S):
            values = re.findall(r'\w+:\s*"([^"\n]+)"', match.group(2))
            if not values or not all(re.fullmatch(r'#[0-9a-fA-F]{6}(?:[0-9a-fA-F]{2})?', value) for value in values):
                continue  # Display-P3 values are preserved upstream but not converted into lossy HEX.
            if len(values) != 12:
                raise ValueError('Original Radix scale does not have its declared 12 steps')
            result.append((f'{theme}-{match.group(1)}', values,
                          {'name': match.group(1), 'theme': theme, 'size': 12, 'originalColors': values,
                           'artifactPath': f'src/{theme}.ts'}))
    return result


def recovered_sources():
    discovery = json.loads((UPSTREAM / 'discovery.json').read_text(encoding='utf-8'))['repositories']
    for key in REPOSITORIES:
        commit_path = UPSTREAM / key / 'commit.json'
        if key not in discovery and commit_path.exists():
            discovery[key] = {'repository': REPOSITORIES[key], 'sourceCommit': json.loads(commit_path.read_text(encoding='utf-8'))['sha']}
    audit_path = UPSTREAM / 'source-audit.json'
    if audit_path.exists():
        if audit_path.stat().st_size > MAX_BYTES:
            raise ValueError('Source audit exceeds bounded size')
        audit = json.loads(audit_path.read_text(encoding='utf-8'))
        for artifact in audit['artifacts']:
            repository = artifact.get('repository')
            if not repository:
                continue
            matching = [entry for entry in discovery.values() if entry['repository'] == repository]
            if len(matching) != 1 or matching[0]['sourceCommit'] != artifact['sourceCommit']:
                raise ValueError('Source revision differs from the verified original artifact audit')
    return discovery


def audit_sources():
    """Match required original bytes to retrieval evidence; re-read missing records only."""
    sources = recovered_sources()
    required = {
        'palettetown': ['DESCRIPTION', 'LICENSE', 'R/sysdata.rda'],
        'nbapalettes': ['LICENSE.md', 'R/colors.R'],
        'lisa': ['LICENSE.md', 'inst/extdata/palettes.yml'],
        'colRoz': ['LICENSE.txt', 'R/oz_palettes.R'],
        'MetBrewer': ['LICENSE.md', 'R/PaletteCode.R'],
        'PrettyCols': ['LICENSE.md', 'R/PrettyColsPalettes.R'],
        'poisonfrogs': ['LICENSE.md', 'R/poison_frog_palettes.R'],
        'colorbrewer': ['export/LICENSE.txt', 'export/colorbrewer.json'],
        'cartocolor': ['README.md', 'package.json', 'src/carto.ts'],
        'radix-colors': ['LICENSE', 'src/light.ts', 'src/dark.ts'],
    }
    records = []
    for name in ('discovery.json', 'fetch.json', 'terms.json', 'source-audit.json'):
        file = UPSTREAM / name
        if file.exists():
            if file.stat().st_size > MAX_BYTES:
                raise ValueError('Retrieval manifest exceeds bounded size')
            manifest = json.loads(file.read_text(encoding='utf-8'))
            records.extend(manifest.get('artifacts', []))
            records.extend(manifest.get('requests', []))
    artifacts = []
    for key, paths in required.items():
        source = sources[key]
        if source['repository'] != REPOSITORIES[key] or not re.fullmatch(r'[0-9a-f]{40}', source['sourceCommit']):
            raise ValueError('Unregistered repository or invalid pinned source revision')
        for path in paths:
            file = UPSTREAM / key / path
            if not file.is_file() or file.stat().st_size > MAX_BYTES:
                raise ValueError('Required original source file is missing or oversized')
            payload = file.read_bytes()
            digest = hashlib.sha256(payload).hexdigest()
            url = f"https://raw.githubusercontent.com/{source['repository']}/{source['sourceCommit']}/{path}"
            matching = [row for row in records if row.get('url') == url
                        and row.get('sha256') == digest and row.get('bytes') == len(payload)]
            proof = 'original-retrieval-record-matched'
            if not matching:
                original = request(url)
                if original != payload:
                    raise ValueError('Saved source bytes do not match their pinned public original')
                proof = 'pinned-public-original-byte-match'
                time.sleep(0.35)
            artifacts.append({'path': file.relative_to(ROOT).as_posix(), 'url': url,
                              'repository': source['repository'], 'sourceCommit': source['sourceCommit'],
                              'artifactPath': path, 'bytes': len(payload), 'sha256': digest,
                              'verification': proof})
    cc_file = UPSTREAM / 'terms/CC-BY-4.0.txt'
    cc_payload = cc_file.read_bytes()
    cc_url = 'https://creativecommons.org/licenses/by/4.0/legalcode.txt'
    if not any(row.get('url') == cc_url and row.get('sha256') == hashlib.sha256(cc_payload).hexdigest()
               and row.get('bytes') == len(cc_payload) for row in records):
        raise ValueError('CC-BY full legal text has no matching original retrieval proof')
    artifacts.append({'path': cc_file.relative_to(ROOT).as_posix(), 'url': cc_url,
                      'bytes': len(cc_payload), 'sha256': hashlib.sha256(cc_payload).hexdigest(),
                      'verification': 'original-retrieval-record-matched'})
    apache = ROOT / 'data/upstream/css-wave/apache'
    apache_manifest = json.loads((apache / 'manifest.json').read_text(encoding='utf-8'))
    apache_payload = (apache / 'LICENSE-2.0.txt').read_bytes()
    if (apache_manifest['url'] != 'https://www.apache.org/licenses/LICENSE-2.0.txt'
            or apache_manifest['sha256'] != hashlib.sha256(apache_payload).hexdigest()
            or apache_manifest['bytes'] != len(apache_payload)):
        raise ValueError('Previously retrieved Apache full legal text audit does not match')
    apache_file = UPSTREAM / 'terms/Apache-2.0.txt'
    apache_file.write_bytes(apache_payload)
    artifacts.append({'path': apache_file.relative_to(ROOT).as_posix(), **apache_manifest,
                      'verification': 'identical-original-license-copy',
                      'retrievalAuditPath': 'data/upstream/css-wave/apache/manifest.json',
                      'robotsAuditPath': 'data/upstream/css-wave/apache/robots.txt'})
    manifest = {'verifiedAt': '2026-10-09', 'artifacts': artifacts, 'requests': REQUESTS,
                'robots': {host: {k: v for k, v in policy.items() if k != 'parser'} for host, policy in ROBOTS.items()},
                'scope': 'Only exact original code/data/license bytes required by offline extraction'}
    (UPSTREAM / 'source-audit.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps({'verifiedOriginalArtifacts': len(artifacts), 'publicOriginalRechecks': len(REQUESTS) - 1}))


def canonical_color(value):
    value = value.lower()
    if len(value) == 4:
        value = '#' + ''.join(c * 2 for c in value[1:])
    if len(value) == 9 and value.endswith('ff'):
        value = value[:-2]
    return value


def palette_signature(colors):
    # Equal swatch sets do not become extra assets because a collection changes order.
    return tuple(sorted(canonical_color(color) for color in colors))


def import_items():
    sources = recovered_sources()
    if 'License: MIT + file LICENSE' not in text('palettetown', 'DESCRIPTION'):
        raise ValueError('Original Palettetown MIT declaration is missing')
    mit_body = text('nbapalettes', 'LICENSE.md').split('Permission is hereby granted', 1)[1]
    mit_body = 'Permission is hereby granted' + mit_body
    poke_header = text('palettetown', 'LICENSE')
    poke_notice = ('Copyright (c) 2016 Tim Lucas\n\n' + mit_body + '\nOriginal R license file:\n' + poke_header
                   + '\nPokemon, pokedex and all pokemon names are trademarks of Nintendo.\n'
                   + 'Color data only; no Pokemon sprites or artwork are distributed.\n')
    carto_readme = text('cartocolor', 'README.md')
    if 'Creative Commons Attribution 4.0' not in carto_readme or json.loads(text('cartocolor', 'package.json'))['license'] != 'CC-BY-4.0':
        raise ValueError('CARTO source license was not verified')
    carto_notice = ('CARTOColors by CARTO\nSource: https://github.com/CartoDB/CartoColor\n'
                    'Exact named color arrays; no new sizes, colors or interpolations created.\n\n'
                    + carto_readme + '\n\n' + text('terms', 'CC-BY-4.0.txt'))
    brewer_notice = (text('colorbrewer', 'export/LICENSE.txt') + '\n\n'
                     + text('terms', 'Apache-2.0.txt'))
    definitions = [
        ('palettetown', 'Palettetown / Tim Lucas', 'R/sysdata.rda', 'MIT', 'LICENSE', poke_notice,
         [(name, colors, {'name': name, 'object': 'pokeColours'}) for name, colors in palettetown_palettes().items()]),
        ('nbapalettes', 'NBA Palettes / Josh Murray', 'R/colors.R', 'MIT', 'LICENSE.md', text('nbapalettes', 'LICENSE.md'),
         [(name, colors, {'name': name}) for name, colors in r_literal_palettes(text('nbapalettes', 'R/colors.R')).items()]),
        ('lisa', 'Color Lisa / lisa', 'inst/extdata/palettes.yml', 'MIT', 'LICENSE.md', text('lisa', 'LICENSE.md'),
         [(name, colors, {'name': name}) for name, colors in lisa_palettes().items()]),
        ('colRoz', 'colRoz / Jacinta Kong and Nicholas Wu', 'R/oz_palettes.R', 'MIT', 'LICENSE.txt', text('colRoz', 'LICENSE.txt'),
         [(name, colors, {'name': name}) for name, colors in r_literal_palettes(text('colRoz', 'R/oz_palettes.R'), True).items()]),
        ('MetBrewer', 'MetBrewer / Blake Robert Mills', 'R/PaletteCode.R', 'CC0-1.0', 'LICENSE.md', text('MetBrewer', 'LICENSE.md'),
         [(name, colors, {'name': name}) for name, colors in r_literal_palettes(text('MetBrewer', 'R/PaletteCode.R'), True).items()]),
        ('PrettyCols', 'PrettyCols / Nicola Rennie', 'R/PrettyColsPalettes.R', 'CC0-1.0', 'LICENSE.md', text('PrettyCols', 'LICENSE.md'),
         [(name, colors, {'name': name}) for name, colors in r_literal_palettes(text('PrettyCols', 'R/PrettyColsPalettes.R'), True).items()]),
        ('poisonfrogs', 'poisonfrogs / Camilo Rodriguez and Lauren OConnell', 'R/poison_frog_palettes.R', 'MIT', 'LICENSE.md', text('poisonfrogs', 'LICENSE.md'),
         [(name, colors, {'name': name}) for name, colors in r_literal_palettes(text('poisonfrogs', 'R/poison_frog_palettes.R')).items()]),
        ('colorbrewer', 'ColorBrewer / Cynthia Brewer and Mark Harrower', 'export/colorbrewer.json', 'Apache-2.0', 'export/LICENSE.txt', brewer_notice, colorbrewer_palettes()),
        ('cartocolor', 'CARTOColors / CARTO', 'src/carto.ts', 'CC-BY-4.0', 'README.md', carto_notice, carto_palettes()),
        ('radix-colors', 'Radix Colors', 'src/light.ts', 'MIT', 'LICENSE', text('radix-colors', 'LICENSE'), radix_palettes()),
    ]
    baseline_path = UPSTREAM / 'dedup-baseline.json'
    if not baseline_path.is_file() or baseline_path.stat().st_size > MAX_BYTES:
        raise ValueError('A frozen bounded dedup baseline is required')
    baseline_bytes = baseline_path.read_bytes()
    if hashlib.sha256(baseline_bytes).hexdigest() != BASELINE_SHA256:
        raise ValueError('Frozen pre-wave dedup baseline was altered')
    baseline = json.loads(baseline_bytes)
    if len(set(baseline['ids'])) != baseline['catalogItems'] or len(baseline['ids']) != baseline['catalogItems']:
        raise ValueError('Frozen catalog IDs are not unique or do not match the declared boundary')
    seen = {tuple(signature) for signature in baseline['signatures']}
    known_ids = set(baseline['ids'])
    items, counts, exclusions, artifacts = [], {}, [], {}
    for key, name, path, license_id, license_path, license_text, palettes in definitions:
        source = sources[key]
        marker = {'MIT': 'Permission is hereby granted', 'CC0-1.0': 'CC0 1.0 Universal',
                  'Apache-2.0': 'Licensed under the Apache License, Version 2.0',
                  'CC-BY-4.0': 'Creative Commons Attribution 4.0 International Public License'}[license_id]
        if marker not in license_text or not re.fullmatch(r'[0-9a-f]{40}', source['sourceCommit']):
            raise ValueError('Complete source notice or pinned commit is missing')
        counts[key] = {'storedDefinitions': len(palettes), 'imported': 0, 'duplicates': 0, 'invalidSize': 0}
        for palette_name, colors, evidence in palettes:
            if not 2 <= len(colors) <= 32:
                counts[key]['invalidSize'] += 1
                continue
            if not all(re.fullmatch(r'#[0-9a-fA-F]{3}|#[0-9a-fA-F]{6}|#[0-9a-fA-F]{8}', color) for color in colors):
                raise ValueError('Unexpected original palette color syntax')
            signature = palette_signature(colors)
            if signature in seen:
                counts[key]['duplicates'] += 1
                exclusions.append({'source': key, 'name': palette_name, 'reason': 'same exact swatch multiset already present'})
                continue
            seen.add(signature)
            actual_path = evidence.get('artifactPath', path)
            artifact = UPSTREAM / key / actual_path
            license_artifact = UPSTREAM / key / license_path
            source_url = f"https://github.com/{source['repository']}/blob/{source['sourceCommit']}/{actual_path}"
            license_url = f"https://github.com/{source['repository']}/blob/{source['sourceCommit']}/{license_path}"
            digest = hashlib.sha256(verified_bytes(key, actual_path)).hexdigest()
            slug = unicodedata.normalize('NFKD', palette_name).encode('ascii', errors='ignore').decode().lower()
            identifier = f"color-wave-{key.lower()}-{re.sub(r'[^a-z0-9]+', '-', slug).strip('-')}"
            if identifier in known_ids:
                raise ValueError('Asset ID collision')
            known_ids.add(identifier)
            description = f'원본 {name}에 이름 {palette_name}로 저장된 {len(colors)}색 배열입니다. 색상과 순서를 보존하며 배경과 모션 요소의 색상 설계에 사용할 수 있습니다.'
            item = {'id': identifier, 'title': f'{name} / {palette_name}', 'description': description,
                    'category': 'palette', 'tags': ['palette', 'color', '색상', '배경', key, palette_name],
                    'sourceUrl': source_url, 'sourceName': name, 'license': license_id, 'licenseUrl': license_url,
                    'licenseText': license_text, 'verifiedAt': '2026-10-09', 'verification': 'source-and-license-reviewed',
                    'kind': 'palette', 'preview': {'type': 'palette', 'variant': 'swatches'},
                    'code': json.dumps(colors, ensure_ascii=False), 'colors': colors, 'language': 'json', 'access': 'public',
                    'sourceCommit': source['sourceCommit'], 'upstreamCommit': source['sourceCommit'], 'upstreamSha256': digest,
                    'evidence': {'scope': 'individual-stored-palette', 'sourceUrls': [source_url, license_url],
                                 'sourceCommit': source['sourceCommit'], 'artifactPath': actual_path,
                                 'artifactBytes': artifact.stat().st_size, 'artifactSha256': digest,
                                 'licenseArtifactSha256': hashlib.sha256(verified_bytes(key, license_path)).hexdigest(),
                                 'licenseTextSha256': hashlib.sha256(license_text.encode('utf-8')).hexdigest(),
                                 'originalColors': evidence.get('originalColors', colors), 'definition': evidence,
                                 'extraction': 'Complete original named palette array; no interpolation, generated sizes, hue variants or subsampling'}}
            if key == 'colorbrewer':
                item['attribution'] = 'This product includes color specifications and designs developed by Cynthia Brewer (http://colorbrewer.org/).'
            if key == 'cartocolor':
                item['attribution'] = 'CARTOColors by CARTO, CC-BY-4.0, https://github.com/CartoDB/CartoColor. Color arrays unchanged.'
            items.append(item)
            counts[key]['imported'] += 1
            for artifact_path in (actual_path, license_path):
                file = UPSTREAM / key / artifact_path
                rel = str(file.relative_to(ROOT)).replace('\\', '/')
                artifacts[rel] = {'path': rel, 'sourceCommit': source['sourceCommit'], 'repository': source['repository'],
                                  'artifactPath': artifact_path, 'url': f"https://raw.githubusercontent.com/{source['repository']}/{source['sourceCommit']}/{artifact_path}",
                                  'bytes': file.stat().st_size, 'sha256': hashlib.sha256(verified_bytes(key, artifact_path)).hexdigest()}
    sys.path.insert(0, str(ROOT))
    from scripts.build import validate_item
    for entry in items:
        validate_item(entry)
        if json.loads(entry['code']) != entry['colors']:
            raise ValueError('Serialized palette code differs from colors')
    output = ROOT / 'data/color-wave-items.json'
    output.write_text(json.dumps(items, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
    manifest = {'verifiedAt': '2026-10-09', 'total': len(items), 'sourceCounts': counts,
                'deduplication': 'Exact RGB/RGBA swatch multiset, including length and repetitions; across existing catalog and wave',
                'exclusions': exclusions, 'artifacts': list(artifacts.values()),
                'outputBytes': output.stat().st_size, 'outputSha256': hashlib.sha256(output.read_bytes()).hexdigest(),
                'dedupBaselineSha256': hashlib.sha256(baseline_path.read_bytes()).hexdigest(),
                'sourceAuditSha256': hashlib.sha256((UPSTREAM / 'source-audit.json').read_bytes()).hexdigest(),
                'validation': {'schema': 'passed', 'uniqueIds': len(known_ids) == baseline['catalogItems'] + len(items),
                               'exactCodeColors': True, 'storedSizesOnly': True, 'noVideo': True}}
    (UPSTREAM / 'extraction.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps({'total': len(items), 'sourceCounts': counts, 'bytes': output.stat().st_size}, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--discover', nargs='+', choices=REPOSITORIES)
    parser.add_argument('--fetch', nargs='+', choices=FETCH_PATHS)
    parser.add_argument('--web-discover', nargs='+', choices=REPOSITORIES)
    parser.add_argument('--license-terms', action='store_true')
    parser.add_argument('--import-items', action='store_true')
    parser.add_argument('--audit-sources', action='store_true')
    args = parser.parse_args()
    if args.import_items:
        import_items()
        return
    if args.audit_sources:
        check_robots('raw.githubusercontent.com')
        audit_sources()
        return
    for host in sorted(HOSTS):
        check_robots(host)
    if args.discover:
        discover(args.discover)
    if args.fetch:
        fetch(args.fetch)
    if args.web_discover:
        web_discover(args.web_discover)
    if args.license_terms:
        url = 'https://creativecommons.org/licenses/by/4.0/legalcode.txt'
        save('terms/CC-BY-4.0.txt', request(url), url)
        finish({'verifiedAt': '2026-10-09'}, 'terms.json')


if __name__ == '__main__':
    main()
