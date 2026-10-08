# Motion Lab 수집과 확장

수집일은 2026-10-08, 기준 시간대는 Asia/Seoul입니다. 이 저장소는 검색 가능한 초기 데이터베이스와 재수집 도구입니다. 전 세계 모든 작품이나 각 사이트의 전체 카탈로그를 수집했다는 의미는 아닙니다.

## 보관 방식

- `data/imported-items.json`: 공개 원본에서 실제로 읽은 CSS 키프레임, 팔레트, 그라디언트와 브라우저 확인 카드.
- `data/research-sources.json`: Exa와 Parallel Search로 발견한 118개 링크 레퍼런스. 페이지 본문 확인과 검색 결과 확인 수준을 구분합니다.
- `data/jtech-items.json`: 사용자 지정 저장소의 네 HTML 작품. 라이선스 파일이 없어 코드 없이 출처 링크로 보관합니다.
- `data/glsl-items.json`: 파일별 MIT 표시를 확인한 GLSL 전환 소스. 입력 텍스처와 렌더러가 필요한 실제 셰이더이며 사이트 미리보기는 개념 이미지입니다.
- `data/manual-items.json`: 직접 작성한 24개 기법 예제. 외부 수집 자료와 `original-authored`로 구분합니다.
- `data/upstream/`: 변경되지 않는 Git 커밋에 고정한 원본, 라이선스, SHA256 검증 자료.

생성된 `data/catalog.json`과 `data/motionlab.sqlite`는 위 입력으로 다시 만들 수 있습니다. `dist/catalog.json`, `dist/catalog-index.json`, `dist/collections/*.json`, `dist/llms.txt`는 웹과 AI용 정적 출력입니다. 정확한 현재 수량은 `python -m motionlab stats` 또는 카탈로그의 `stats`를 확인합니다.

## 수집 경계와 라이선스

크롤러는 등록된 공개 GitHub 저장소만 읽습니다. HTTPS 호스트 허용 목록, 파일 크기·동시 요청 수 제한, robots.txt 확인, 오류 기록을 적용합니다. robots.txt가 404/410인 경우 파일이 없음을 기록합니다. 네트워크 오류나 수집 금지 상태를 허용으로 간주하지 않습니다. 인증·유료 구간·CAPTCHA·차단을 우회하지 않으며 MP4/MOV/WebM은 다운로드하지 않습니다.

Career Hacker Alex의 robots.txt는 공개 페이지를 허용하고 관리자·API·로그인 등의 경로를 제외합니다. 지정 모션 페이지의 160개 카드 제목과 분류는 실제 브라우저 DOM에서 확인해 `data/browser-cha.tsv`에 기록했습니다. 원본 이미지, 영상, 프롬프트, 편집 파일을 복제하지 않았습니다. 페이지의 개인 학습·제작 안내를 사이트 전체의 재배포 허가로 해석하지 않았습니다.

코드 가져오기는 MIT 원문 확인을 통과한 자료만 대상으로 합니다. Animate.css는 최신 버전의 Hippocratic 라이선스를 MIT로 오인하지 않도록 MIT인 3.7.2 버전을 고정했습니다. 현재 Hover.css의 개인·오픈소스·유료 상업 조건은 MIT 자료로 가져오지 않았습니다. 레퍼런스의 `reference-only`는 탐색용 보관 방식이며 해당 원본이 실제로 비공개라는 뜻은 아닙니다.

CSS 단독 키프레임은 보이는 샘플 대상에 적용하고, 실제 DOM이 수록된 로더·컴포넌트는 그 구조를 사용합니다. GLSL과 SVG도 원본 동작을 재생합니다. 전체 원작품의 구성과 입력 자산을 모두 복원한 것은 아닙니다. MIT 원문과 코드의 저작권·허가문을 보존합니다. [추가 에셋 58개 수집 기록](asset-expansion.md), [분석과 미리보기 범위](asset-analysis.md)를 참고하세요.

## 갱신

```powershell
# 등록된 CSS·색상 소스의 현재 커밋과 라이선스를 확인해 재수집
python scripts/crawl.py

# 특정 소스만 갱신하고 나머지는 해시 검증한 로컬 스냅샷 사용
python scripts/crawl.py --source magic

# 네트워크 없이 원본 스냅샷을 검증하며 재생성
python scripts/crawl.py --offline

# 사용자 지정 저장소의 작품 경로를 확인 (링크만 보관)
python scripts/import_jtech.py

# 카탈로그·검색 DB·정적 AI 파일 재생성
python scripts/build.py
```

GLSL 수집은 `python scripts/import_glsl.py --help`의 옵션을 확인합니다. 위 명령은 자동 예약 작업이 아니며 실행할 때만 외부 소스를 요청합니다. 브라우저 확인 카드와 검색으로 조사한 레퍼런스는 자동으로 최신 상태가 보장되지 않습니다. 새 도메인을 추가할 때는 수집 경로와 라이선스 범위를 먼저 확인하고 입력 스키마에 맞게 저장합니다.

## AI 연결

웹 링크로는 `catalog-index.json`에서 후보를 찾고 해당 `collections/{category}.json`에서 코드와 출처를 읽습니다. 로컬 CLI와 MCP는 동일한 SQLite 데이터베이스를 검색합니다. 기본 MCP는 로컬 stdio이며 정적 사이트에 원격 `/mcp` 서버가 있는 것으로 안내하지 않습니다. 사용법은 `docs/interfaces.md`와 `skills/motion-lab/SKILL.md`에 있습니다.

현재 Sites의 사이트 주소만 예약되어 있습니다. 외부 소스 업로드는 자동 승인 심사에서 거절되어 배포되지 않았습니다. 사용자 승인 후 소스 업로드와 비공개 배포를 진행할 수 있습니다. 로컬 사이트와 데이터베이스는 독립적으로 사용할 수 있습니다.
