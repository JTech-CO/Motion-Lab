"""Bounded, reproducible public-code harvesting. Never downloads videos.

Only the registered GitHub repositories below are fetched. robots.txt, licenses,
immutable Git commits, SHA256 hashes and every request outcome are recorded.
Unknown or restrictive licenses fail closed; blocked pages are not bypassed.
"""
from __future__ import annotations
import argparse
import concurrent.futures
import hashlib
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UA = 'MotionLab/1.0 (public motion research; no video; bounded requests)'
MAX_BYTES = 5_000_000
SOURCES = [
    ('animate', 'Animate.css 3.7.2', 'animate-css/animate.css', '3.7.2', 'animate.css', 'LICENSE', 'css'),
    ('magic', 'Magic Animations', 'miniMAC/magic', 'master', 'dist/magic.css', 'LICENSE', 'css'),
    ('vivify', 'Vivify', 'Martz90/vivify', 'master', 'vivify.css', 'LICENSE', 'css'),
    ('wicked', 'WickedCSS', 'kristofferandreasen/wickedCSS', 'master', 'wickedcss.css', 'LICENSE', 'css'),
    ('spinkit', 'SpinKit', 'tobiasahlin/SpinKit', 'master', 'spinkit.css', 'LICENSE', 'loader'),
    ('three-dots', 'Three Dots', 'nzbin/three-dots', 'master', 'dist/three-dots.css', 'LICENSE', 'loader'),
    ('csshake', 'CSShake', 'elrumordelaluz/csshake', 'master', 'dist/csshake.css', 'LICENSE', 'css'),
    ('nice-colors', 'Nice Color Palettes', 'Jam3/nice-color-palettes', 'master', '1000.json', 'LICENSE.md', 'palette'),
    ('uigradients', 'uiGradients', 'ghosh/uiGradients', 'main', 'gradients.json', 'LICENSE.md', 'gradient'),
]
ALLOWED = {'raw.githubusercontent.com', 'api.github.com'}
ROBOTS: dict[str, dict] = {}
LOG: list[dict] = []

def request(url: str, *, check_robots: bool = True) -> bytes:
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != 'https' or parsed.hostname not in ALLOWED or parsed.username or parsed.password:
        raise ValueError('URL is outside the registered HTTPS source hosts')
    if re.search(r'\.(?:mp4|mov|webm|zip)(?:$|\?)', url, re.I):
        raise ValueError('Video and archive downloads are disabled')
    if check_robots:
        info = ROBOTS.get(parsed.hostname)
        if info is None:
            raise RuntimeError('robots.txt must be checked before requesting source')
        parser = info.get('parser')
        if info['status'] == 'unavailable' or (parser and not parser.can_fetch(UA, url)):
            raise RuntimeError('robots.txt blocks automatic collection; review in a browser')
    started = time.monotonic()
    req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept': 'application/json,text/plain;q=0.9'})
    try:
        with urllib.request.urlopen(req, timeout=25) as response:
            final = urllib.parse.urlsplit(response.geturl())
            if final.scheme != 'https' or final.hostname not in ALLOWED:
                raise ValueError('Unexpected redirect outside allowed source hosts')
            body = response.read(MAX_BYTES + 1)
            if len(body) > MAX_BYTES:
                raise ValueError('Source exceeds the 5 MB limit')
            LOG.append({'url':url,'status':response.status,'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest(),'seconds':round(time.monotonic()-started,2)})
            return body
    except urllib.error.HTTPError as exc:
        LOG.append({'url':url,'status':exc.code,'error':type(exc).__name__})
        raise

def check_robot(host: str) -> None:
    url = f'https://{host}/robots.txt'
    path = ROOT / 'data' / 'upstream' / f'robots-{host}.txt'
    try:
        body = request(url, check_robots=False)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body)
        parser = urllib.robotparser.RobotFileParser(url)
        parser.parse(body.decode('utf-8', errors='replace').splitlines())
        ROBOTS[host] = {'status':'reviewed','parser':parser,'url':url}
    except urllib.error.HTTPError as exc:
        # RFC 9309: a missing robots file is not a disallow directive.
        ROBOTS[host] = {'status':'absent' if exc.code in (404,410) else 'unavailable','url':url,'httpStatus':exc.code}
    except (OSError, ValueError) as exc:
        ROBOTS[host] = {'status':'unavailable','url':url,'error':str(exc)}

def keyframes(css: str):
    """Scan balanced CSS blocks, never execute downloaded CSS/JS."""
    clean = re.sub(r'/\*.*?\*/', '', css, flags=re.S)
    seen = set()
    for match in re.finditer(r'@(?:-webkit-|-moz-|-o-)?keyframes\s+([\w-]+)\s*\{',clean):
        name = match.group(1)
        if name in seen:
            continue
        start, depth, pos = match.end()-1, 1, match.end()
        while depth and pos < len(clean):
            if clean[pos] == '{': depth += 1
            elif clean[pos] == '}': depth -= 1
            pos += 1
        if depth:
            raise ValueError('Unbalanced CSS keyframe block')
        body = clean[start:pos]
        if re.search(r'url\s*\(|expression\s*\(|@import|</',body,re.I):
            raise ValueError('External resources or unsafe content in CSS')
        seen.add(name)
        yield name, '@keyframes ' + name + ' ' + body

def slug(text: str) -> str:
    return re.sub(r'[^a-z0-9]+','-',text.lower()).strip('-')

def motion_tags(name: str) -> list[str]:
    tokens = re.sub(r'([a-z])([A-Z])', r'\1 \2', name).lower().replace('-',' ').split()
    extra = []
    for term, ko in [('bounce','바운스'),('fade','페이드'),('zoom','확대'),('slide','슬라이드'),('rotate','회전'),('shake','흔들림'),('flip','뒤집기'),('pulse','맥동'),('scale','크기'),('in','등장'),('out','퇴장')]:
        if any(term in token for token in tokens): extra.append(ko)
    return list(dict.fromkeys(tokens + extra + ['css','모션','keyframes']))

def verified_mit_license(body: bytes, expected_sha: str | None = None, *, offline: bool = False) -> str:
    """Verify cached bytes and permission text before labeling or exporting MIT."""
    actual_sha = hashlib.sha256(body).hexdigest()
    if offline and (not isinstance(expected_sha,str) or not re.fullmatch(r'[0-9a-f]{64}',expected_sha)
                    or actual_sha != expected_sha):
        raise ValueError('Cached license hash mismatch or missing licenseSha256')
    license_text = body.decode('utf-8').replace('\r\n','\n').replace('\r','\n')
    mit_heading = re.search(r'(?im)^\s*(?:The\s+)?MIT\s+License(?:\s*\(MIT\))?\s*$',license_text)
    if not (mit_heading and 'Permission is hereby granted, free of charge' in license_text):
        raise ValueError('MIT license not verified; reference-only review required')
    return license_text

def import_source(spec: tuple, offline: bool) -> tuple[list[dict],dict]:
    key, title, repo, ref, filename, licensefile, kind = spec
    local = ROOT / 'data' / 'upstream' / key
    local.mkdir(parents=True,exist_ok=True)
    meta_path = local / 'manifest.json'
    if offline:
        meta = json.loads(meta_path.read_text(encoding='utf-8'))
        sha = meta['commit']
        data = (local / ('source.json' if kind in ('palette','gradient') else 'source.css')).read_bytes()
        license_body = (local / 'LICENSE.txt').read_bytes()
        license_text = verified_mit_license(license_body,meta.get('licenseSha256'),offline=True)
        if hashlib.sha256(data).hexdigest() != meta['sha256']:
            raise ValueError('Cached source hash mismatch')
    else:
        commit = json.loads(request(f'https://api.github.com/repos/{repo}/commits/{ref}'))
        sha = commit['sha']
        if not re.fullmatch(r'[0-9a-f]{40}',sha): raise ValueError('Invalid upstream commit')
        time.sleep(0.2)
        license_body = request(f'https://raw.githubusercontent.com/{repo}/{sha}/{licensefile}')
        license_text = verified_mit_license(license_body)
        time.sleep(0.2)
        data = request(f'https://raw.githubusercontent.com/{repo}/{sha}/{filename}')
        meta = {'id':key,'title':title,'repository':repo,'ref':ref,'commit':sha,'sourceUrl':f'https://github.com/{repo}/blob/{sha}/{filename}','license':'MIT','licenseUrl':f'https://github.com/{repo}/blob/{sha}/{licensefile}','licenseSha256':hashlib.sha256(license_body).hexdigest(),'verifiedAt':datetime.now(timezone.utc).date().isoformat(),'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data),'method':'robots-reviewed-public-file','kind':kind}
        (local / ('source.json' if kind in ('palette','gradient') else 'source.css')).write_bytes(data)
        (local / 'LICENSE.txt').write_bytes(license_body)
        meta_path.write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8')
    for directory in ('vendor','licenses'):
        (ROOT / 'dist' / directory).mkdir(parents=True,exist_ok=True)
    suffix = 'json' if kind in ('palette','gradient') else 'css'
    (ROOT / 'dist' / 'vendor' / f'{key}.{suffix}').write_bytes(data)
    (ROOT / 'dist' / 'licenses' / f'{key}.txt').write_text(license_text,encoding='utf-8')
    base = {'sourceUrl':meta['sourceUrl'],'sourceName':title,'license':'MIT','licenseUrl':meta['licenseUrl'],'licenseText':license_text,'verifiedAt':meta['verifiedAt'],'verification':'source-and-license-reviewed','access':'public','upstreamCommit':sha,'upstreamSha256':meta['sha256']}
    items = []
    if kind in ('palette','gradient'):
        dataset = json.loads(data)
        for index, row in enumerate(dataset,1):
            colors = row if kind == 'palette' else row['colors']
            if not isinstance(colors,list) or not 2 <= len(colors) <= 20 or not all(re.fullmatch(r'#[0-9a-fA-F]{3}(?:[0-9a-fA-F]{3})?',c) for c in colors):
                raise ValueError('Invalid color palette')
            colors = ['#' + ''.join(c*2 for c in color[1:]) if len(color)==4 else color for color in colors]
            item_title = f'Nice Palette {index:04}' if kind == 'palette' else row['name']
            bg = f'linear-gradient(135deg, {", ".join(colors)})'
            code = json.dumps(colors) if kind == 'palette' else f'/* {title} / MIT\n{license_text}\n*/\n.motion-background {{ background: {bg}; }}'
            items.append({**base,'id':f'{key}-{index:04}','title':item_title,'description':'공개 데이터에서 수집한 5색 조합. 브랜드, 배경, 모션 요소의 색상 설계에 활용합니다.' if kind=='palette' else '공개 그라디언트의 원래 색상 조합을 CSS로 변환했습니다. 각도를 조절해 배경과 전환에 활용할 수 있습니다.','category':kind,'tags':[kind,'색상','배경',*colors],'kind':'palette' if kind=='palette' else 'code','preview':{'type':kind,'variant':'swatches' if kind=='palette' else 'linear'},'code':code,'colors':colors,'language':'json' if kind=='palette' else 'css','codePath':f'vendor/{key}.{suffix}'})
    else:
        css = data.decode('utf-8-sig')
        for name, block in keyframes(css):
            category = 'loader' if kind == 'loader' else ('transition' if re.search(r'(?:In|Out|Enter|Exit|in|out)',name) else 'animation')
            tags = motion_tags(name)
            duration = '1.8s' if kind == 'loader' else '2.4s'
            code = f'/* {title} / MIT\n{license_text}\nSource: {meta["sourceUrl"]}\nMotion Lab adaptation: a single .motion-sample element demonstrates this keyframe.\n*/\n{block}\n\n.motion-sample {{ animation: {name} {duration} ease-in-out infinite; }}'
            items.append({**base,'id':f'{key}-{slug(name)}','title':name,'description':f'{title}의 {name} 키프레임을 가져온 단일 요소 데모입니다. 복합 로더와 원본 레이아웃은 전체 CSS 소스를 확인하세요.','category':category,'tags':tags,'kind':'code','preview':{'type':'css','variant':name,'keyframe':name,'adapted':True},'code':code,'colors':[],'language':'css','codePath':f'vendor/{key}.css'})
    meta['items'] = len(items)
    print(f'{title}: {len(items)} records (MIT; {sha[:10]})',flush=True)
    return items,meta

def browser_records() -> list[dict]:
    path = ROOT / 'data' / 'browser-cha.tsv'
    if not path.exists(): return []
    output = []
    for line in path.read_text(encoding='utf-8').splitlines():
        if not line.strip(): continue
        identifier,title,group = line.split('\t')
        category = 'typography' if '타이포' in group else 'transition' if '트랜지션' in group else 'interaction' if ('작업' in group or '컴포넌트' in group) else 'reference'
        output.append({'id':'cha-'+identifier,'title':title,'description':f'브라우저에서 확인한 CHA Motion Kit의 {re.sub(r"\s+\d+$", "", group)} 레퍼런스입니다. 원본 사이트에서 해당 제목의 카드를 열어 구성을 확인하세요.','category':category,'tags':['CHA','모션그래픽',group,identifier],'sourceUrl':'https://www.careerhackeralex.com/sharings/cha-motion-kit','sourceName':'Career Hacker Alex · CHA Motion Kit','license':'reference-only','licenseNote':'원본은 영상·프롬프트의 개인 학습·제작 사용을 안내합니다. 사이트 전체나 편집 소스의 재배포 허가는 별도 확인이 필요합니다.','verifiedAt':'2026-10-08','verification':'browser-reviewed','kind':'reference','preview':{'type':'reference','variant':'grid'},'code':None,'colors':[],'language':'link','access':'public','sourceCardId':identifier})
    return output

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--offline',action='store_true',help='Rebuild from hash-verified local source snapshots without network')
    parser.add_argument('--source', choices=[s[0] for s in SOURCES], help='Refresh only one source and preserve other cached sources')
    args = parser.parse_args()
    if not args.offline:
        for host in sorted(ALLOWED): check_robot(host)
    results, sources, failures = [], [], []
    # Two workers: bounded per-origin load; each source sleeps between files.
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        futures = {pool.submit(import_source,s,args.offline or bool(args.source and s[0] != args.source)):s for s in SOURCES}
        for future in concurrent.futures.as_completed(futures):
            spec = futures[future]
            try:
                items,source = future.result()
                results.extend(items); sources.append(source)
            except Exception as exc:
                failures.append({'source':spec[0],'error':str(exc)})
                print(f'{spec[1]}: skipped ({exc})',flush=True)
    results.extend(browser_records())
    results.sort(key=lambda x:(x['kind']=='palette',x['sourceName'],x['id']))
    target = ROOT / 'data'
    target.mkdir(exist_ok=True)
    (target / 'imported-items.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
    report = {'collectedAt':datetime.now(timezone.utc).isoformat(),'offline':args.offline,'items':len(results),'sources':sources,'failures':failures,'robots':{h:{k:v for k,v in info.items() if k!='parser'} for h,info in ROBOTS.items()},'requests':sorted(LOG,key=lambda x:x['url']),'browserReviewedCards':len(browser_records()),'excluded':['MP4/MOV/WebM files','Hover.css current dual/commercial terms: reference-only','Animate.css current Hippocratic license: use verified MIT 3.7.2 instead','unlicensed source redistribution']}
    report_name = 'rebuild-report.json' if args.offline else 'crawl-report.json'
    (target / report_name).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(f'Total: {len(results)} records; {len(sources)} imported sources; {len(failures)} failures',flush=True)
    if failures: raise SystemExit(1)

if __name__=='__main__': main()
