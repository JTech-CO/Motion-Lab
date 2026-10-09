"""Build an inspectable full-catalog duplicate review without changing assets.

Run the type-specific audits first, or use this command's default refresh.
This report never removes records or rewrites the catalog/database/site.
"""

import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'data/duplicate-audit'
DOMAINS = ('css', 'svg', 'glsl', 'palette', 'reference')
FINDINGS = ('exactGroups', 'nearGroups', 'candidatePairs', 'familyGroups')
MAX_JSON = 128 * 1024 * 1024


def load_json(path):
    raw = path.read_bytes()
    if len(raw) > MAX_JSON:
        raise ValueError(f'Audit JSON exceeds 128 MiB: {path.name}')
    return json.loads(raw), raw


def atomic_text(path, value, encoding='utf-8'):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.tmp')
    temporary.write_text(value, encoding=encoding, newline='\n')
    temporary.replace(path)


def domain_for(item):
    if item.get('kind') in ('palette', 'reference'):
        return item['kind']
    if item.get('kind') == 'code' and item.get('language') in ('css', 'svg', 'glsl'):
        return item['language']
    raise ValueError('Uncovered catalog asset type: ' + str(item.get('id')))


def validate_reports(items, reports, catalog_sha):
    by_id = {item['id']: item for item in items}
    if len(by_id) != len(items):
        raise ValueError('Duplicate catalog IDs')
    for domain in DOMAINS:
        report = reports[domain]
        fingerprint = report.get('catalogSha256') or report.get('input', {}).get('catalogSha256') or report.get('methodology', {}).get('catalogSha256')
        if fingerprint != catalog_sha:
            raise ValueError('Stale catalog fingerprint in ' + domain)
        expected = {item['id'] for item in items if domain_for(item) == domain}
        manifest = report.get('items', report.get('inspectionManifest', []))
        inspected = [record['id'] for record in manifest]
        if len(inspected) != len(set(inspected)) or set(inspected) != expected:
            raise ValueError('Incomplete or repeated per-item coverage in ' + domain)
        if report.get('errors'):
            raise ValueError('Unresolved parser/validation errors in ' + domain)
        if report['coverage']['itemCount'] != len(expected):
            raise ValueError('Coverage count mismatch in ' + domain)
        if report['coverage']['pairUniverse'] != len(expected) * (len(expected) - 1) // 2:
            raise ValueError('Pair universe mismatch in ' + domain)
        for record in manifest:
            if domain == 'reference':
                continue
            stored_hash = record.get('codeSha256') or record.get('storedCodeSha256')
            actual_hash = hashlib.sha256((by_id[record['id']].get('code') or '').encode('utf-8')).hexdigest()
            if stored_hash != actual_hash:
                raise ValueError('Per-item code fingerprint mismatch in ' + domain + ': ' + record['id'])
        for section in FINDINGS:
            for group in report.get(section, []):
                ids = group.get('ids')
                if not isinstance(ids, list) or len(ids) < 2 or len(set(ids)) != len(ids) or not set(ids) <= expected:
                    raise ValueError('Invalid finding membership in ' + domain)
    return by_id


def load_decisions(by_id, catalog_sha):
    decisions = {}
    for name in ('review-decisions.json', 'css-review.json'):
        path = OUTPUT / name
        if not path.exists():
            continue
        document, _ = load_json(path)
        if document.get('catalogSha256') != catalog_sha:
            raise ValueError('Review decisions belong to a different catalog')
        for entry in document.get('decisions', []):
            ids = entry.get('ids', [])
            if len(ids) < 2 or len(ids) != len(set(ids)) or not set(ids) <= by_id.keys():
                raise ValueError('Invalid review decision membership')
            if entry.get('domain') not in DOMAINS or not all(domain_for(by_id[x]) == entry['domain'] for x in ids):
                raise ValueError('Invalid review decision domain')
            if set(entry.get('codeSha256', {})) != set(ids):
                raise ValueError('Review decisions require all original code fingerprints')
            for identifier, expected in entry['codeSha256'].items():
                if hashlib.sha256((by_id[identifier].get('code') or '').encode('utf-8')).hexdigest() != expected:
                    raise ValueError('Review decision code fingerprint mismatch')
            key = (entry['domain'], tuple(sorted(ids)))
            if key in decisions:
                raise ValueError('Repeated review decision')
            decisions[key] = entry
    return decisions


def load_quality_notes(by_id, catalog_sha):
    path = OUTPUT / 'css-review.json'
    if not path.exists():
        return []
    document, _ = load_json(path)
    if document.get('catalogSha256') != catalog_sha:
        raise ValueError('Stale source quality review')
    result = []
    for index, original in enumerate(document.get('qualityNotes', []), 1):
        if not set(original.get('ids', [])) <= by_id.keys():
            raise ValueError('Unknown source quality note member')
        source = (ROOT / original['sourcePath']).resolve()
        if not source.is_relative_to((ROOT / 'data/upstream').resolve()):
            raise ValueError('Source quality evidence must stay inside data/upstream')
        if hashlib.sha256(source.read_bytes()).hexdigest() != original['sourceSha256']:
            raise ValueError('Source quality evidence hash mismatch')
        result.append({**original, 'qualityNoteId': f'css-source-quality-{index:04d}'})
    return result


def safe_cell(value):
    """Do not expose spreadsheet formulas through metadata exported as CSV."""
    value = str(value)
    if value.lstrip().startswith(('=', '+', '-', '@')) or value.startswith(('\t', '\r', '\n')):
        return "'" + value
    return value


def csv_text(headers, rows):
    stream = io.StringIO(newline='')
    writer = csv.writer(stream, lineterminator='\n')
    writer.writerow(headers)
    for row in rows:
        writer.writerow([safe_cell(value) for value in row])
    return stream.getvalue()


def merge_exact_components(groups, order):
    """Equivalence groups only; never transitively merge near-similarity pairs."""
    parent = {}
    def find(value):
        parent.setdefault(value, value)
        if parent[value] != value:
            parent[value] = find(parent[value])
        return parent[value]
    for group in groups:
        root = find(group['ids'][0])
        for identifier in group['ids'][1:]:
            parent[find(identifier)] = root
    components = defaultdict(list)
    for identifier in parent:
        components[find(identifier)].append(identifier)
    return [sorted(ids, key=order.get) for ids in sorted(components.values(), key=lambda values: min(order[x] for x in values))]


def summarize(items, reports, decisions, quality_notes=()):
    order = {item['id']: index for index, item in enumerate(items)}
    findings, membership = [], defaultdict(list)
    for domain in DOMAINS:
        for section in FINDINGS:
            for index, original in enumerate(reports[domain].get(section, []), 1):
                finding = {**original, 'findingId': f'{domain}-{section}-{index:04d}', 'domain': domain, 'section': section}
                decision = decisions.get((domain, tuple(sorted(finding['ids']))))
                if decision:
                    finding['reviewDecision'] = decision
                findings.append(finding)
                for identifier in finding['ids']:
                    membership[identifier].append(finding)
    exact_components = merge_exact_components([group for group in findings if group['section'] == 'exactGroups'], order)
    exact_ids = {identifier for group in exact_components for identifier in group}
    near_ids = {identifier for group in findings if group['section'] == 'nearGroups' for identifier in group['ids']}
    pending = [group for group in findings if group['section'] == 'candidatePairs' and not group.get('reviewDecision', {}).get('classification', '').startswith('keep-')]
    family = [group for group in findings if group['section'] == 'familyGroups' or group.get('reviewDecision', {}).get('classification', '').startswith('keep-')]
    statuses = Counter()
    ledger = []
    for item in items:
        groups = membership[item['id']]
        quality = [note['qualityNoteId'] for note in quality_notes if item['id'] in note['ids']]
        if item['kind'] == 'reference':
            status = 'metadata-only-visual-unassessed'
        elif quality:
            status = 'source-extraction-needs-repair'
        elif item['id'] in exact_ids:
            status = 'exact-canonical-duplicate'
        elif item['id'] in near_ids:
            status = 'near-by-stated-static-method'
        elif any(group in pending for group in groups):
            status = 'candidate-needs-review'
        elif groups:
            status = 'related-variant-family'
        else:
            status = 'no-match-under-current-methods'
        statuses[status] += 1
        ledger.append({'id': item['id'], 'kind': item['kind'], 'language': item.get('language'),
            'sourceName': item.get('sourceName'), 'title': item.get('title'), 'status': status,
            'findingIds': [group['findingId'] for group in groups],
            'qualityNoteIds': quality,
            'codeSha256': hashlib.sha256((item.get('code') or '').encode('utf-8')).hexdigest() if item.get('code') is not None else None})
    stats = {
        'catalogItems': len(items), 'storedAssetItems': sum(item['kind'] != 'reference' for item in items),
        'metadataOnlyReferenceItems': sum(item['kind'] == 'reference' for item in items),
        'exactGroupCount': len(exact_components), 'exactGroupItemCount': len(exact_ids),
        'exactSurplusCount': sum(len(group) - 1 for group in exact_components),
        'nearRelationCount': sum(group['section'] == 'nearGroups' for group in findings),
        'nearAffectedItemCount': len(near_ids), 'pendingCandidateRelationCount': len(pending),
        'relatedFamilyRelationCount': len(family), 'sourceReviewedDecisionCount': len(decisions),
        'extractionQualityAffectedItemCount': len({x for note in quality_notes for x in note['ids']}),
        'exactGroupsNeedingSourceRepair': sum(any(set(ids) <= set(note['ids']) for note in quality_notes) for ids in exact_components),
        'exactMergeCandidateSurplus': sum(len(ids) - 1 for ids in exact_components if not any(set(ids) <= set(note['ids']) for note in quality_notes)),
        'itemStatusCounts': dict(statuses),
        'countsNote': 'Group/relation and affected-item counts overlap. Near pairs are not equivalence classes and cannot be subtracted from the catalog count.',
    }
    return stats, findings, ledger, exact_components


def markdown(report, reports):
    stats = report['summary']
    lines = [
        '# Motion Lab 중복·유사성 검토', '',
        '검사일: 2026-10-09 (Asia/Seoul). 카탈로그와 원본 코드·색상·라이선스는 변경하지 않았습니다.', '',
        f"총 **{stats['catalogItems']:,}개**의 항목 식별 정보를 확인하고, 저장된 에셋 **{stats['storedAssetItems']:,}개**의 코드·벡터·색상을 전수 비교했습니다. 참고 링크 **{stats['metadataOnlyReferenceItems']:,}개**는 메타데이터 검사이며 원격 작품의 시각적 유사성은 판단하지 않았습니다.", '',
        f"정규화 기준 같은 저장 코드는 **{stats['exactGroupCount']:,}개 그룹 / {stats['exactGroupItemCount']:,}개 항목**입니다. 그룹당 하나를 대표로 잡을 때 나머지는 **{stats['exactSurplusCount']:,}개**입니다. 이 중 **{stats['exactGroupsNeedingSourceRepair']:,}개 그룹**은 원본 추출 복원부터 필요한 사례이며, 이를 제외한 통합 검토 대상은 **{stats['exactMergeCandidateSurplus']:,}개**입니다. 자료를 삭제하지 않았습니다.", '',
        f"같은 구조의 타이밍 차이 또는 엄격한 색상 거리로 찾은 유사 관계는 **{stats['nearRelationCount']:,}건**, 해당 항목은 **{stats['nearAffectedItemCount']:,}개**입니다. 관계가 겹치므로 이 수를 카탈로그에서 빼면 안 됩니다.", '',
        '| 종류 | 항목 | 비교 조합 | 같은 저장 코드 그룹 | 유사 관계 | 자동 후보 | 재검토 후 미확정 |',
        '| --- | ---: | ---: | ---: | ---: | ---: | ---: |',
    ]
    for domain in DOMAINS:
        r = reports[domain]
        pending = sum(entry['domain'] == domain and entry['section'] == 'candidatePairs' and not entry.get('reviewDecision', {}).get('classification', '').startswith('keep-') for entry in report['findings'])
        lines.append(f"| {domain} | {r['coverage']['itemCount']:,} | {r['coverage']['pairUniverse']:,} | {len(r.get('exactGroups', [])):,} | {len(r.get('nearGroups', [])):,} | {len(r.get('candidatePairs', [])):,} | {pending:,} |")
    lines += ['', '표의 비교 조합은 종류별 전체 조합입니다. 같은 종류의 모든 항목을 식별·서명 기준으로 검사하며, 구조가 맞지 않는 조합은 안전한 조건으로 제외한 뒤 상세 차이를 비교합니다. 참고 자료 조합은 링크 식별 비교입니다.', '',
        '## 판정 기준', '',
        '- 같은 저장 코드: 현재 저장된 코드와 구성 정보의 정규화 결과가 같습니다. 클래스·키프레임·로컬 ID 이름, 주석, 서식 차이를 제거합니다. 단일 키프레임 샘플의 일치가 원본 전체 작품의 일치를 뜻하지는 않습니다.',
        '- 유사: 각 검사기가 명시한 타이밍 정규화 또는 색상 거리 기준에 들어옵니다. 속도·초기 상태·적용 대상·원작자의 용도에 따라 유지할 수 있습니다.',
        '- 계열: 방향·축·반복·색 개수·채움 등 의미 있는 변형이나 같은 모션 원리를 공유합니다. 중복 개수에 더하지 않습니다.',
        '- 미발견: 현재 검사 기준에서 관계가 발견되지 않았다는 뜻입니다. 독창성이나 픽셀 단위 차이를 보증하지 않습니다.', '',
        '## 완전 중복 대표 후보', '',
    ]
    if report['exactComponents']:
        for index, ids in enumerate(report['exactComponents'], 1):
            needs_repair = any(set(ids) <= set(note['ids']) for note in report.get('sourceQualityNotes', []))
            label = '추출 복원 우선' if needs_repair else '대표 후보'
            lines.append(f"{index}. {label} `{ids[0]}`: " + ', '.join('`' + identifier + '`' for identifier in ids[1:]))
    else:
        lines.append('없음.')
    lines += ['', '대표 후보는 기존 카탈로그 순서를 우선한 임시 선택입니다. 실제 통합 시 모든 출처·저작권·라이선스 고지를 유지해야 합니다.', '',
        '## 구체적인 유사 사례', '',
        '| 대상 | 확인된 차이 | 판단 |',
        '| --- | --- | --- |',
        '| SDS Scroll Stagger Grid / Scroll Wave Rise | 같은 자식 구성·상승 키프레임·시차, 재생 시간 0.6초 / 0.7초 | 하나의 모션에 시간 옵션으로 묶을 수 있음 |',
        '| SVG Pulse 3 / Pulse Multiple | 시차 0.4·0.8초 / 0.2·0.4초, 마지막 시작 / 종료에 따른 재시작 | 같은 효과의 리듬 변형으로 보존 |',
        '| SVG Pulse Rings 3 / Pulse Rings Multiple | 원·윤곽·값은 같고 시차·재시작 이벤트가 다름 | 같은 효과의 리듬 변형으로 보존 |',
        '| CARTO TealRose-2 / Temps-2 | 첫 색 동일, 둘째 색 `#d0587e` / `#cf597e`, 평균 OKLab 거리 0.1233 | 매우 가까운 색상 변형 |',
        '| Nice Palette 0141 / 0494 | 5색의 순서 유지, 평균 OKLab 거리 0.9846 | 유사 팔레트로 묶어 검토 |',
        '| Nice Palette 0192 / 0378 | 순서를 뒤집으면 평균 OKLab 거리 0.1545 | 역순 의미를 보존하는 추가 후보 |',
        '| Radix 중성색 23쌍 | 회색·올리브·세이지·샌드·슬레이트 등의 미세한 색조·알파 차이 | 테마 색상 변형으로 보존 |', '',
        '색상 거리는 검정·흰색 배경 합성 결과 모두에서 검사한 Euclidean OKLab × 100입니다. DeltaE2000 수치가 아니며, 평균 1.0 이하·최대 2.0 이하라는 엄격한 기준입니다.', '',
        '## 추출 품질 문제', '',
        'SpinKit Chase와 Swing은 현재 저장된 `rotate(360deg)` 단일 샘플이 같습니다. 그러나 보존된 원본은 Chase 6개 자식과 Swing 2개 자식, 각기 다른 크기·시차·부속 키프레임을 사용합니다. 원작을 합치기 전에 전체 구성 추출을 복원해야 합니다.', '',
        'Three Dots의 Falling / Before / After도 원본에서는 0px / -15px / +15px 위치와 다른 시차를 가진 한 로더의 구성 요소입니다. 저장된 단독 샘플에는 원본의 `left:-9999px` 문맥이 빠져 있습니다. 코드의 큰 좌표에서 작은 차이라는 이유로 중복 처리하면 다른 점을 잃게 됩니다.', '',
        f"이 두 추출 품질 메모는 **{stats['extractionQualityAffectedItemCount']}개 항목**에 연결되어 있으며, 원본 파일 해시도 검증했습니다. 복원 작업은 이번 검토에서 수행하지 않았습니다.", '',
        '## 유지할 변형과 추가 검토', '',
        '- CSS 추가 후보 20쌍은 실제 선언을 재검토했습니다. 19쌍은 회전축·마스크 방향·밀도·도형 등 의미 있는 차이, 1쌍은 원본 로더의 다른 구성 요소여서 유지합니다.',
        '- GLSL 후보 11쌍은 실제 연산자를 다시 읽어 모두 방향·축 변형으로 유지합니다. 원문과 코드 해시에 연결된 판단은 `review-decisions.json`에 기록합니다.',
        '- Radix의 중성색 유사 조합은 실제 색 값이 다른 테마 변형입니다. 색조의 쓰임을 보존해야 하므로 자동 삭제 대상으로 분류하지 않습니다.',
        '- 역순 팔레트는 순서가 반대이며 그라디언트에 쓰면 방향 의미가 달라집니다. 가까운 색 집합이라고 같은 팔레트로 자동 통합하지 않습니다.',
        '- CSS 그라디언트와 팔레트의 색 배열 관계는 보충 보고서에서 구분합니다. 그라디언트 방향·중지점과 스와치 표현의 차이를 보존합니다.', '',
        '## 파일과 재현', '',
        f"- [{stats['catalogItems']:,}개 전량 판정표](../data/duplicate-audit/items.csv): 항목별 코드 해시, 상태, 관련 finding ID와 추출 품질 메모.",
        '- [전체 관계표](../data/duplicate-audit/findings.csv): 모든 그룹·쌍과 이유, 수치 근거, 보존 판단.',
        '- [통합 JSON](../data/duplicate-audit/report.json): 요약·전체 관계·항목별 판정·검사 범위.',
        '- [CSS 근거](../data/duplicate-audit/css.json), [SVG 근거](../data/duplicate-audit/svg.json), [GLSL 근거](../data/duplicate-audit/glsl.json), [팔레트 근거](../data/duplicate-audit/palette.json), [참고 링크 근거](../data/duplicate-audit/reference.json).',
        '- [색상 표현 보충 비교](../data/duplicate-audit/color-representations.json), [GLSL·색상 원문 검토 판단](../data/duplicate-audit/review-decisions.json), [CSS 원문 검토·추출 품질](../data/duplicate-audit/css-review.json).', '',
        '```sh', 'python scripts/audit_duplicates.py', '# 이미 생성된 검사 결과의 해시와 전량 커버리지 확인 후 보고서만 재생성', 'python scripts/audit_duplicates.py --reuse', '```', '',
        f"카탈로그 SHA-256: `{report['catalogSha256']}`", '',
        '## 한계', '',
        '이번 검사는 정적 분석입니다. 브라우저 연결이 sandbox 초기화 오류로 실패하여 모든 프레임의 픽셀·동영상 비교는 수행하지 못했습니다. CSS와 SVG처럼 구현 방식이 다른 모션의 시각적 동등성, 수학적으로 다른 셰이더가 같은 결과를 내는 경우, 저장되지 않은 참고 작품의 유사성은 미확정입니다. 새로 발견된 후보를 시각적으로 확인한 뒤 통합 대상을 정하는 것이 다음 단계입니다.', '',
        '오프라인 검사기는 내려받은 코드·스크립트·URL을 실행하거나 요청하지 않습니다. XML 엔티티와 과도한 입력을 거부하며 CSV 메타데이터의 수식 실행을 차단합니다. 기존 읽기 전용 API·바인딩 SQL·출력 이스케이프·권한 경계는 변경하지 않았습니다.', '',
    ]
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reuse', action='store_true', help='Validate and combine current existing type reports.')
    args = parser.parse_args()
    catalog, raw = load_json(ROOT / 'data/catalog.json')
    catalog_sha = hashlib.sha256(raw).hexdigest()
    items = catalog['items']
    if not args.reuse:
        for script in ('duplicate_audit_css.py', 'duplicate_audit_svg.py', 'duplicate_audit_palette.py', 'duplicate_audit_other.py'):
            options = ['--include-gradients'] if script == 'duplicate_audit_palette.py' else []
            subprocess.run([sys.executable, str(ROOT / 'scripts' / script), *options], cwd=ROOT, check=True)
    reports = {domain: load_json(OUTPUT / (domain + '.json'))[0] for domain in DOMAINS}
    by_id = validate_reports(items, reports, catalog_sha)
    decisions = load_decisions(by_id, catalog_sha)
    quality_notes = load_quality_notes(by_id, catalog_sha)
    stats, findings, ledger, exact_components = summarize(items, reports, decisions, quality_notes)
    supplemental_path = OUTPUT / 'color-representations.json'
    supplemental = load_json(supplemental_path)[0] if supplemental_path.exists() else None
    if supplemental is not None and supplemental.get('catalogSha256') != catalog_sha:
        raise ValueError('Stale supplemental color representation report')
    report = {'version': 1, 'auditedAt': '2026-10-09', 'timezone': 'Asia/Seoul', 'catalogSha256': catalog_sha,
        'summary': stats, 'coverage': {domain: reports[domain]['coverage'] for domain in DOMAINS},
        'methodology': {domain: reports[domain]['methodology'] for domain in DOMAINS},
        'exactComponents': exact_components, 'findings': findings, 'items': ledger,
        'sourceQualityNotes': quality_notes,
        'supplementalColorRepresentationCoverage': supplemental.get('coverage') if supplemental else None,
        'limitations': ['Static source comparison, not exhaustive rendered frame/pixel comparison.',
            '288 reference entries have no locally stored assets for visual comparison.',
            'Cross-renderer visual equivalence and algebraic GLSL equivalence are not established.',
            'Near relations overlap and are never transitively collapsed into duplicate counts.']}
    atomic_text(OUTPUT / 'report.json', json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    atomic_text(OUTPUT / 'items.csv', csv_text(('id', 'kind', 'language', 'sourceName', 'title', 'status', 'findingIds', 'qualityNoteIds', 'codeSha256'),
        ((entry['id'], entry['kind'], entry['language'], entry['sourceName'], entry['title'], entry['status'], ';'.join(entry['findingIds']), ';'.join(entry['qualityNoteIds']), entry['codeSha256'] or '') for entry in ledger)), encoding='utf-8-sig')
    atomic_text(OUTPUT / 'findings.csv', csv_text(('findingId', 'domain', 'section', 'ids', 'reason', 'confidence', 'evidence', 'differences', 'reviewClassification', 'reviewReason'),
        ((entry['findingId'], entry['domain'], entry['section'], ';'.join(entry['ids']), entry.get('reason', ''), entry.get('confidence', ''),
          json.dumps(entry.get('evidence', {}), ensure_ascii=False), json.dumps(entry.get('differences', {}), ensure_ascii=False),
          entry.get('reviewDecision', {}).get('classification', ''), entry.get('reviewDecision', {}).get('reasonKO') or entry.get('reviewDecision', {}).get('reasonEN', '')) for entry in findings)), encoding='utf-8-sig')
    atomic_text(ROOT / 'docs/duplicate-audit.md', markdown(report, reports))
    # The asset store must remain byte-for-byte unchanged throughout an audit.
    if hashlib.sha256((ROOT / 'data/catalog.json').read_bytes()).hexdigest() != catalog_sha:
        raise ValueError('Catalog changed during duplicate audit')
    print(json.dumps(stats, ensure_ascii=False))


if __name__ == '__main__':
    main()
