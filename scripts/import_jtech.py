"""Index the four public Motiongraphic works; retain links, not unlicensed code."""
import json
import re
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

from crawl import ROOT, request, check_robot, LOG

def main():
    for host in ('api.github.com','raw.githubusercontent.com'): check_robot(host)
    tree = json.loads(request('https://api.github.com/repos/JTech-CO/Motiongraphic/git/trees/main?recursive=1'))
    if tree.get('truncated'): raise RuntimeError('Repository tree truncated; manual review required')
    commit = tree['sha']
    if not re.fullmatch(r'[0-9a-f]{40}',commit): raise RuntimeError('Invalid revision')
    records = tree['tree']
    paths = [entry['path'] for entry in records if entry['type']=='blob' and entry['path'].endswith('index.html')]
    print(json.dumps({'commit':commit,'htmlPaths':paths,'licenseFiles':[e['path'] for e in records if re.search(r'(^|/)(license|copying)(\.|$)',e['path'],re.I)]},ensure_ascii=False,indent=2))
    out = ROOT / 'data' / 'upstream' / 'jtech'
    out.mkdir(parents=True,exist_ok=True)
    (out/'tree.json').write_text(json.dumps(tree,ensure_ascii=False,indent=2),encoding='utf-8')
    (out/'request-log.json').write_text(json.dumps(LOG,ensure_ascii=False,indent=2),encoding='utf-8')
    reviewed = {
        '1. SpaceX Motion/index.html': ('spacex','SpaceX 2002–2026','우주 산업의 성장 과정을 수치와 장면 전환으로 설명하는 HTML 데이터 스토리입니다.'),
        '2. Genesis Motion/index.html': ('genesis','Genesis 2015–2026','자동차 브랜드의 성장 지표를 시간 흐름과 제품 장면으로 엮은 HTML 모션그래픽입니다.'),
        '3. DJI Motion/index.html': ('dji','DJI 2006–2026','드론과 카메라 기업의 변화를 짧은 데이터 이야기로 구성한 HTML 모션그래픽입니다.'),
        '4. Loopfield-Studio Motion/index.html': ('loopfield','Loopfield Studio','GLSL 기반 루프 패턴과 프리셋을 소개하는 HTML 모션그래픽 레퍼런스입니다.'),
    }
    items=[]
    for path in paths:
        if path not in reviewed: continue
        key,title,description=reviewed[path]
        items.append({'id':'jtech-'+key,'title':title,'description':description,'category':'shader' if key=='loopfield' else 'reference','tags':['HTML','모션그래픽','데이터 스토리','dataviz','JTech',key],'sourceUrl':f'https://github.com/JTech-CO/Motiongraphic/blob/{commit}/{urllib.parse.quote(path)}','sourceName':'JTech-CO / Motiongraphic','license':'reference-only','licenseNote':'검토한 저장소 트리에 라이선스 파일이 없습니다. 코드 재배포 권한은 별도 확인이 필요합니다.','verifiedAt':'2026-10-08','verification':'readme-and-file-tree-reviewed','kind':'reference','preview':{'type':'reference','variant':'grid'},'code':None,'colors':[],'language':'link','access':'public','upstreamCommit':commit})
    (ROOT/'data'/'jtech-items.json').write_text(json.dumps(items,ensure_ascii=False,indent=2),encoding='utf-8')
    print(f'{len(items)} reference records saved; no source code or videos copied')

if __name__=='__main__': main()
