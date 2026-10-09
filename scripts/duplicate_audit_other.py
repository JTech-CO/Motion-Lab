"""Offline GLSL and reference identity audit. Never fetch or execute imports."""

from collections import Counter, defaultdict
from difflib import SequenceMatcher
import hashlib
import itertools
import json
from pathlib import Path
import re
from urllib.parse import urlsplit, urlunsplit

ROOT = Path(__file__).resolve().parents[1]
MAX_CODE = 1_000_000
TOKEN = re.compile(r'[A-Za-z_]\w*|(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?[uUfF]?|\+\+|--|==|!=|<=|>=|&&|\|\||<<|>>|[^\s]')
NUMBER = re.compile(r'(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?[uUfF]?\Z')
TYPES = frozenset('void bool int uint float double vec2 vec3 vec4 ivec2 ivec3 ivec4 bvec2 bvec3 bvec4 uvec2 uvec3 uvec4 mat2 mat3 mat4 sampler2D samplerCube'.split())
RESERVED = TYPES | frozenset('uniform const varying attribute in out inout precision highp mediump lowp if else for while do break continue return discard true false struct layout flat smooth centroid invariant'.split())
BUILTINS = frozenset('transition main progress ratio getFromColor getToColor texture texture2D textureCube radians degrees sin cos tan asin acos atan sinh cosh tanh pow exp log exp2 log2 sqrt inversesqrt abs sign floor trunc round roundEven ceil fract mod modf min max clamp mix step smoothstep isnan isinf length distance dot cross normalize faceforward reflect refract matrixCompMult outerProduct transpose determinant inverse lessThan lessThanEqual greaterThan greaterThanEqual equal notEqual any all not dFdx dFdy fwidth'.split())


def strip_comments(code):
    # GLSL has no string literals. Preprocessor lines remain in the token stream.
    return re.sub(r'/\*[\s\S]*?\*/|//[^\n]*', ' ', code)


def uniform_defaults(code, names):
    """Mirror preview.js's explicit source-comment defaults; names alone are not identity."""
    pattern = re.compile(r'uniform\s+(float|int|bool|vec[234]|ivec[234]|sampler2D)\s+([a-zA-Z_]\w*)\s*(?:/\*\s*=\s*([^*]+)\*/)?\s*;[^\n]*')
    result = []
    for match in pattern.finditer(code):
        inline = re.search(r'//\s*=\s*([^\n]+)', match[0])
        comment = match[3] or (inline[1] if inline else '')
        if match[1] == 'bool':
            value = [1 if 'true' in comment else 0]
        else:
            cleaned = re.sub(r'(?:i?vec[234])\s*\(', '', comment)
            value = [float(n) for n in re.findall(r'-?(?:\d+\.?\d*|\.\d+)(?:e[+-]?\d+)?', cleaned, re.I)[:4]] or [0.5]
        result.append([match[1], names.get(match[2], match[2]), value])
    return result


def canonical_glsl(item):
    code = item.get('code')
    if not isinstance(code, str) or not code.strip() or len(code) > MAX_CODE:
        raise ValueError('Missing or oversized GLSL source')
    tokens = TOKEN.findall(strip_comments(code))
    declared = set()
    for index, token in enumerate(tokens[:-1]):
        if token in TYPES and re.fullmatch(r'[A-Za-z_]\w*', tokens[index + 1]):
            declared.add(tokens[index + 1])
    names = {}
    for token in tokens:
        if token in declared and token not in RESERVED and token not in BUILTINS:
            names.setdefault(token, 'v' + str(len(names)))
    canonical = tuple(names.get(token, token) for token in tokens)
    defaults = uniform_defaults(code, names)
    return {
        'id': item['id'], 'tokens': canonical, 'defaults': defaults,
        'exact': json.dumps([canonical, defaults], separators=(',', ':')),
        'skeleton': tuple('#number' if NUMBER.fullmatch(token) else token for token in canonical),
        'codeSha256': hashlib.sha256(code.encode('utf-8')).hexdigest(),
        'numericValues': [token for token in canonical if NUMBER.fullmatch(token)],
        'shingles': Counter(tuple(canonical[i:i + 5]) for i in range(max(0, len(canonical) - 4))),
    }


def group_equal(records, field, reason):
    buckets = defaultdict(list)
    for record in records:
        buckets[record[field]].append(record)
    return [{'ids': sorted(r['id'] for r in group), 'reason': reason,
             'confidence': 'high', 'evidence': {'signatureSha256': hashlib.sha256(key.encode('utf-8')).hexdigest(),
                 'codeSha256': {r['id']: r['codeSha256'] for r in group}}}
            for key, group in sorted(buckets.items()) if len(group) > 1]


def audit_glsl(items):
    selected = sorted((x for x in items if x.get('language') == 'glsl' and x.get('kind') == 'code'), key=lambda x: x['id'])
    records, errors = [], []
    for item in selected:
        try:
            records.append(canonical_glsl(item))
        except (TypeError, ValueError) as error:
            errors.append({'id': item['id'], 'error': str(error)})
    exact = group_equal(records, 'exact', 'Same GLSL tokens after consistent declared-identifier renaming, with equal host uniform defaults.')
    candidates, families = [], []
    for left, right in itertools.combinations(records, 2):
        if left['exact'] == right['exact']:
            continue
        ids = [left['id'], right['id']]
        if left['skeleton'] == right['skeleton']:
            families.append({'ids': ids, 'reason': 'Same algorithm token structure with numeric parameters/defaults changed.',
                'confidence': 'medium', 'differences': {
                    'numericValues': {r['id']: r['numericValues'] for r in (left, right)},
                    'uniformDefaults': {r['id']: r['defaults'] for r in (left, right)}},
                'evidence': {'tokenCount': len(left['tokens'])},
                'recommendation': 'Keep as algorithm variants until output direction, geometry and parameters are reviewed.'})
            continue
        size_ratio = min(len(left['tokens']), len(right['tokens'])) / max(len(left['tokens']), len(right['tokens']), 1)
        if size_ratio < 0.8:
            continue
        total = sum(left['shingles'].values()) + sum(right['shingles'].values())
        shared = sum((left['shingles'] & right['shingles']).values())
        dice = 2 * shared / max(total, 1)
        if dice < 0.8:
            continue
        matcher = SequenceMatcher(None, left['tokens'], right['tokens'], autojunk=False)
        ratio = matcher.ratio()
        if ratio < 0.85:
            continue
        changes = []
        for opcode, a0, a1, b0, b1 in matcher.get_opcodes():
            if opcode != 'equal':
                changes.append({'operation': opcode, left['id']: list(left['tokens'][a0:a1]), right['id']: list(right['tokens'][b0:b1])})
        candidates.append({'ids': ids, 'reason': 'High normalized token overlap; output equivalence needs review.',
            'confidence': 'candidate', 'evidence': {'tokenSequenceRatio': round(ratio, 6), 'fiveTokenShingleDice': round(dice, 6),
                'codeSha256': {r['id']: r['codeSha256'] for r in (left, right)}},
            'differences': {'tokenChanges': changes, 'uniformDefaults': {r['id']: r['defaults'] for r in (left, right)}},
            'recommendation': 'Review the changed operators, axes and samples; shared algorithm text does not prove near-identical output.'})
    return {
        'methodology': {'scope': 'Stored GLSL programs and current host uniform defaults.',
            'exact': 'Comments/whitespace removed; consistently rename declared nonbuiltin identifiers; preserve operators, axes, numeric literal types, calls and default values.',
            'candidate': 'All pairs inspected; numeric-only skeleton matches are families; otherwise length ratio >=0.8, five-token shingle Dice >=0.8 and token sequence ratio >=0.85.',
            'limitations': ['No shader execution or image/pixel equivalence is claimed.', 'Identifier renaming is conservative lexical normalization, not algebraic symbolic proof.', 'Numeric changes can reverse direction or materially change geometry, so they are not automatically near duplicates.']},
        'coverage': {'itemCount': len(selected), 'pairUniverse': len(selected) * (len(selected) - 1) // 2,
            'comparedPairs': len(records) * (len(records) - 1) // 2, 'parsedItems': len(records)},
        'items': [{'id': r['id'], 'codeSha256': r['codeSha256'],
                   'canonicalSha256': hashlib.sha256(r['exact'].encode('utf-8')).hexdigest(),
                   'tokenCount': len(r['tokens']), 'uniformDefaults': r['defaults']} for r in records],
        'exactGroups': exact, 'nearGroups': [], 'candidatePairs': candidates, 'familyGroups': families, 'errors': errors,
    }


def normalized_url(value):
    if not isinstance(value, str) or len(value) > 4096:
        raise ValueError('Invalid source URL')
    parts = urlsplit(value)
    if parts.scheme.lower() not in ('http', 'https') or not parts.hostname or parts.username or parts.password:
        raise ValueError('Unsupported source URL')
    # Preserve paths, queries and fragments: they can distinguish actual source targets.
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path or '/', parts.query, parts.fragment))


def audit_references(items):
    selected = sorted((x for x in items if x.get('kind') == 'reference'), key=lambda x: x['id'])
    targets, shared_pages, errors = defaultdict(list), defaultdict(list), []
    for item in selected:
        try:
            url = normalized_url(item.get('sourceUrl'))
            card = item.get('sourceCardId')
            if card is not None and (not isinstance(card, str) or len(card) > 256):
                raise ValueError('Invalid sourceCardId')
            targets[(url, card)].append(item['id'])
            shared_pages[url].append(item)
        except (TypeError, ValueError) as error:
            errors.append({'id': item['id'], 'error': str(error)})
    exact = [{'ids': sorted(ids), 'reason': 'Same normalized reference target URL and same individual card identifier.',
              'confidence': 'high', 'evidence': {'sourceUrl': key[0], 'sourceCardId': key[1]}}
             for key, ids in sorted(targets.items(), key=lambda pair: str(pair[0])) if len(ids) > 1]
    families = [{'ids': sorted(item['id'] for item in values), 'reason': 'Different individually identified cards on one source page.',
                'confidence': 'metadata-only', 'evidence': {'sourceUrl': url, 'distinctCardIds': len({x.get('sourceCardId') for x in values})},
                'recommendation': 'Retain distinct card identities; a shared collection URL is not evidence of duplicate motion.'}
               for url, values in sorted(shared_pages.items()) if len(values) > 1 and len({x.get('sourceCardId') for x in values}) > 1]
    return {
        'methodology': {'scope': 'Reference metadata only; no local motion geometry, frames or colors exist.',
            'exact': 'Normalized source URL plus individual sourceCardId, preserving query/fragment/path.',
            'limitations': ['All reference identities are audited; visual/behavioral similarity of remote works is unassessed.', 'Shared page URLs and similar titles do not establish duplicate assets.']},
        'coverage': {'itemCount': len(selected), 'pairUniverse': len(selected) * (len(selected) - 1) // 2,
            'identityComparedPairs': len(selected) * (len(selected) - 1) // 2, 'visualComparedPairs': 0,
            'metadataOnlyItems': len(selected)},
        'items': [{'id': item['id'], 'sourceUrl': item.get('sourceUrl'), 'sourceCardId': item.get('sourceCardId'),
                   'inspection': 'metadata-only', 'visualStatus': 'unassessed'} for item in selected],
        'exactGroups': exact, 'nearGroups': [], 'candidatePairs': [], 'familyGroups': families, 'errors': errors,
    }


def main():
    raw = (ROOT / 'data/catalog.json').read_bytes()
    if len(raw) > 128 * 1024 * 1024:
        raise ValueError('Catalog exceeds 128 MiB audit bound')
    items = json.loads(raw)['items']
    target = ROOT / 'data/duplicate-audit'
    target.mkdir(exist_ok=True)
    for name, audit in (('glsl', audit_glsl), ('reference', audit_references)):
        report = audit(items)
        report['catalogSha256'] = hashlib.sha256(raw).hexdigest()
        temporary = target / (name + '.json.tmp')
        temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
        temporary.replace(target / (name + '.json'))
        print(f"{name}: {report['coverage']['itemCount']} entries; {len(report['exactGroups'])} exact groups, {len(report['candidatePairs'])} candidates, {len(report['familyGroups'])} families")


if __name__ == '__main__':
    main()
