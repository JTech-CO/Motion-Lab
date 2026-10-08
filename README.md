# Motion Lab

모션 코드, 전환, 타이포그래피, 인터랙션, 배경, 로더, 셰이더, 팔레트와 외부 레퍼런스를 검색하는 데이터 창고입니다. 웹 화면, SQLite FTS5 검색, CLI, 읽기 전용 MCP stdio 서버, AI용 SKILL을 같은 카탈로그로 연결합니다. MP4를 저장하지 않습니다.

2026-10-08 기준 **134개 출처 프로젝트 · 2,153개 항목**을 제공합니다: 코드 873개(CSS 738 · GLSL 123 · SVG 12), 팔레트 992개, 탐색용 레퍼런스 288개입니다. CSS에는 정적 그라디언트 382개와 24개 직접 제작 예제가 포함됩니다. 원본 DOM을 갖춘 CSS 로더·컴포넌트 40개, SVG 로더 12개, 개별 컴포넌트 참고 링크 6개를 5개 출처에서 추가했습니다. 사용자가 지정한 CHA의 카드 160개와 JTech의 HTML 작품 4개도 포함합니다. 수집·분석 범위는 [에셋 분석 문서](docs/asset-analysis.md)와 [추가 수집 근거](docs/asset-expansion.md)에 기록합니다.

Python 3.10 이상과 SQLite FTS5가 필요합니다. Python 표준 라이브러리만 사용하므로 패키지 설치나 API 키가 필요하지 않습니다. 프로젝트 디렉터리에서 실행합니다.

```powershell
python scripts/build.py
python -m motionlab serve --port 8787
```

브라우저에서 [Motion Lab](http://127.0.0.1:8787)을 엽니다. 서버는 루프백 주소에만 연결합니다. `dist/`는 정적 호스팅에 사용할 수 있고, `dist/catalog.json`은 전체 공개 데이터입니다. 정적 호스팅은 로컬 Python API나 MCP 서버를 실행하지 않습니다.

웹 화면은 실제 미리보기 카드와 5개 다중 선택 필터(에셋 종류·모션 효과·구성요소·용도·라이선스)를 제공합니다. 같은 필터 안에서는 OR, 서로 다른 필터 사이에서는 AND로 좁힙니다. 분류는 CSS 선언·키프레임·선택자, GLSL 연산·uniform, SVG 요소·애니메이션, 실제 HEX 색상에서 생성한 `analysis`를 사용합니다. 제목이나 브랜드 이름으로 효과를 추측하지 않습니다. 코드 분석 491개, 색상 값 분석 1,374개, 메타데이터 수준 참고 항목 288개를 구분하며 상세에서 근거와 한계를 확인할 수 있습니다.

페이지마다 최대 20개 카드를 보여주고, 기본 정렬은 에셋 종류와 출처를 번갈아 배치합니다. 검색창·체크박스·카드·페이지 번호로 탐색할 수 있습니다. 방향키로 카드와 실제 도구를 이동하고 `Enter`로 선택하거나 상세를 엽니다. 코드 본문에서는 방향키로 스크롤하고 `Enter`로 탭에 복귀합니다. `Esc`로 상세를 닫으며 마우스와 `Tab`도 지원합니다. `/`로 선택적인 검색창에 이동합니다. 상세에서 원본 코드·전체 라이선스·수집 근거를 읽고 복사할 수 있으며 읽기 위치를 유지합니다. KO/EN을 전환할 수 있고 보조 글자도 최소 12px입니다. 원본 제목·코드·라이선스 언어는 보존됩니다.

CSS는 원본 키프레임을 샘플 대상에 적용하고, 새 로더는 실제 원본 DOM을 사용합니다. GLSL은 테스트 이미지 A→B를 실제 WebGL 셰이더로 렌더링하며, SVG는 안전 검사한 원본 애니메이션을 표시합니다. 복합 구성이나 실행 환경 때문에 원본과 차이가 있을 수 있어 상세의 한계를 함께 제공합니다. 로컬 에셋이 없는 참고 링크에는 가짜 미리보기를 만들지 않습니다. 시스템의 모션 줄이기 설정과 재생·정지 조작을 지원합니다.

정적 사이트 예약 주소는 [Motion Lab Archive](https://motion-lab-archive.bryan131.chatgpt.site)이며 현재 미게시 상태입니다. 소스·데이터를 원격 호스팅에 업로드하지 않았습니다. 로컬 서버나 나중에 게시한 정적 URL을 사용하는 AI는 `/llms.txt`, 코드 없는 `/catalog-index.json`, 카테고리별 `/collections/animation.json` 등을 읽을 수 있습니다. 정적 사이트에 원격 `/mcp` 엔드포인트는 없습니다. MCP는 아래 로컬 stdio 설정으로 연결합니다.

```powershell
python -m motionlab search "transition" --category transition --limit 12 --json
python -m motionlab search "" --kind code --license MIT --json
python -m motionlab search --effect mask --component image --basis code --limit 12 --json
python -m motionlab search --asset-type loader --use-case status --json
python -m motionlab stats
python -m motionlab get ITEM_ID --json
python -m motionlab export --format json --output catalog-export.json
python -m motionlab export --format csv --output catalog-export.csv
python -m unittest discover -s tests -v
```

`ITEM_ID`는 검색 결과의 `id`로 바꿉니다. 조회 명령에 `--json`을 사용하면 AI나 다른 프로그램에서 바로 파싱할 수 있습니다. CSV에는 스프레드시트 수식 실행을 막기 위한 이스케이프가 적용됩니다.

MCP 클라이언트 설정 예시입니다. `command`는 사용 중인 Python의 실제 경로로 바꾸고, 아래 프로젝트 경로도 설치 위치에 맞춥니다. 클라이언트가 `cwd`를 지원하면 프로젝트 폴더를 지정합니다.

```json
{
  "mcpServers": {
    "motion-lab": {
      "command": "C:\\Users\\MSI\\AppData\\Local\\Programs\\Python\\Python314\\python.exe",
      "args": [
        "-m", "motionlab", "--root",
        "C:\\Users\\MSI\\Desktop\\내 폴더\\코딩\\기획\\Motion Lab",
        "mcp"
      ],
      "cwd": "C:\\Users\\MSI\\Desktop\\내 폴더\\코딩\\기획\\Motion Lab"
    }
  }
}
```

`cwd`를 지원하지 않는 클라이언트에서는 `args` 앞부분을 `["C:\\...\\Motion Lab\\motionlab\\launch_mcp.py", "--root", "C:\\...\\Motion Lab"]` 형태로 바꾸면 됩니다. 제공 도구는 `search_motion`, `get_motion`, `motion_stats`입니다. 상세 스키마와 HTTP API는 [인터페이스 문서](docs/interfaces.md)에 있습니다.

AI용 지침은 [Motion Lab SKILL](skills/motion-lab/SKILL.md)에 있습니다. 이 폴더를 AI 도구의 스킬 디렉터리에 복사하거나 프로젝트 지침에서 경로를 참조하면 됩니다. 이 프로젝트는 전역 설정을 바꾸거나 스킬을 자동 설치하지 않습니다.

각 항목에는 원본 URL, 출처, 검증 시점, 라이선스, 검증 수준이 있습니다. `kind: reference`는 발견·영감·추가 확인용 링크이며, 코드나 디자인의 복제 권한을 의미하지 않습니다. `Unknown`, `See source` 등은 직접 확인해야 하고, 상용 소스는 해당 제공자의 조건을 따라야 합니다. 로컬에서 작성한 예시와 수집한 외부 레퍼런스를 구분해 사용하세요.

GL Transitions는 파일별 명시적 MIT 선언을 확인한 원본 GLSL 코드로 수록합니다. 원본 주석과 저자·저작권 고지, 저장소 MIT 고지는 그대로 보존합니다. GLSL은 `from`/`to` 텍스처, `progress`와 관련 함수·uniform을 제공하는 WebGL 호스트가 필요하며 웹 미리보기 엔진이 이 환경을 제공합니다. 수집·분석 스크립트와 Python API/MCP는 셰이더를 실행하지 않습니다. 수집 감사 기록은 `data/glsl-report.json`, 고정 커밋·파일 해시는 `data/upstream/gl-transitions/manifest.json`에 있습니다. `python scripts/import_glsl.py --offline`은 해시가 일치하는 기존 MIT 스냅샷만 다시 읽습니다.

데이터 입력은 `data/imported-items.json`, `data/research-sources.json`, 선택 파일 `data/manual-items.json`, `data/glsl-items.json`, `data/jtech-items.json`, `data/expanded-assets.json`의 항목 배열입니다. 입력들이 원본이며 생성된 카탈로그는 다시 입력하지 않습니다. 빌드는 검증·중복 제거 후 `scripts/analyze.py`로 새 `analysis`만 생성하고 원본 코드·출처·라이선스·ID를 보존합니다. 분석 용어도 FTS5 검색에 포함됩니다. 출력은 `data/catalog.json`, `data/motionlab.sqlite`, `dist/catalog.json`, `dist/catalog-index.json`, 카테고리별 `dist/collections/*.json`, `dist/llms.txt`입니다. 출처 프로젝트는 GitHub 개별 파일 링크를 저장소별로 묶어 셉니다.

공개 참조 데이터만 읽는 구조로 계정·쿠키·업로드·결제·사용자 개인정보 저장 기능이 없습니다. API는 파라미터 바인딩, 입력 상한, 호출 제한, Host/Origin 검사, 보안 헤더, 정적 경로 검사를 적용하고 DB를 읽기 전용으로 엽니다.

수집 경계·갱신 명령은 [수집 문서](docs/collection.md), 직접 제작 예제는 [기법 문서](docs/recipes.md), 확인 범위는 [검증 기록](docs/validation.md)에 있습니다. [Motion-Lab.zip](Motion-Lab.zip)은 카탈로그, 검색 DB, 소스 스냅샷, 웹 화면과 SKILL을 함께 옮길 수 있는 패키지입니다.
