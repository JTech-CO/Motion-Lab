# Motion Lab 수집과 유지 관리

Motion Lab은 공개 원본에서 확인한 코드·색상·이미지와 검토한 레퍼런스를 보관합니다. 현재 수량은 `python -m motionlab stats` 또는 `data/catalog.json`의 `stats`에서 확인합니다. 원본 라이선스와 검토 근거는 레코드 및 `data/upstream/`에 보존합니다.

## 로컬 실행과 재생성

프로젝트 폴더에서 실행합니다. 빌드와 로컬 인터페이스는 Python 3.10+ 표준 라이브러리와 SQLite FTS5만 사용하며 API 키가 필요 없습니다.

```sh
python scripts/build.py
python scripts/verify_catalog.py
python -m motionlab serve --port 8787
```

홈은 `http://127.0.0.1:8787/`, 자료 탐색은 `http://127.0.0.1:8787/library.html`입니다. 서버는 루프백에만 바인딩합니다. CLI·HTTP·MCP 연결 방법과 조회 스키마는 [인터페이스](interfaces.md)에 있습니다.

빌드는 저장된 입력만 읽으며 원격 요청이나 원본 코드 실행을 하지 않습니다. `data/catalog.json`, `data/motionlab.sqlite`와 `dist/`의 전체·경량 카탈로그, 별칭, 컬렉션, `llms.txt`를 다시 만듭니다. 생성된 카탈로그를 수집 입력으로 재사용하지 않습니다.

웹 탐색은 `dist/catalog-browse.json`의 검색·분류 목록을 먼저 읽고, 미리보기와 상세 원문은 `dist/catalog-details/`에서 필요한 파일만 가져옵니다. 각 원문 파일은 512 KiB·64개 이하이며 코드, 라이선스, 변형과 검토 근거를 그대로 보존합니다. 홈 전환은 작은 `dist/home-transition.json`을 사용합니다. 이 파일들도 같은 빌드에서 생성·검증하며 Git 추적에서 제외합니다. 전체 JSON과 AI 인터페이스의 데이터는 유지합니다.

전체 JSON 두 파일은 Git 추적에서 제외하고 클론 후 위 빌드로 생성합니다. 원본 입력, 고지, 검증 근거는 저장소에 보존하며 생성된 전체 JSON은 로컬 API, 정적 배포 및 휴대용 패키지에서 계속 사용할 수 있습니다.

GitHub Pages는 `.github/workflows/pages.yml`에서 `main` 변경 시 카탈로그를 다시 만들고 검증한 뒤 배포합니다. 저장소 설정의 Pages 배포 원본은 **GitHub Actions**로 지정합니다. `python scripts/build_pages.py`는 공개 `dist/`만 `_site/dist/`에 복사하고 프로젝트 루트에 이동 안내를 생성하므로 기존 `/dist/index.html#library` 주소를 유지합니다. 전체 JSON은 배포 산출물에 포함되며 Git 이력에는 추가하지 않습니다. 비공개 설정·수집 작업 폴더는 배포하지 않고 파일 링크 및 사이트 크기 1 GB 초과를 차단합니다. `_site/`는 배포 검사용 생성 폴더이며 기존 내용이 있으면 덮어쓰지 않습니다.

같은 빌드에서 `README.md`와 `README-KO.md`의 수량 요약 및 공통 원형 그래프 `docs/assets/catalog-composition.svg`도 갱신합니다. 그래프는 대표 탐색 항목의 모션·디자인·레퍼런스 수량을 사용하며 별칭과 보존 원본 변형을 추가로 계산하지 않습니다. README의 자동 생성 마커 밖 문장은 유지합니다. 현재 SQLite 통계로 문서와 그래프만 갱신하려면 `python scripts/readme_assets.py`를 실행합니다. 외부 차트 서비스나 추가 Python 패키지는 필요하지 않습니다.

홈페이지 구성 그래프의 수량과 비율은 같은 빌드에서 생성하는 작은 `dist/catalog-stats.json`을 사용합니다. 전체 카탈로그와 일치하는지 배포 전 검증하므로 자료가 늘어나면 README와 홈페이지가 같은 기준으로 갱신됩니다.

## 입력과 근거

| 역할 | 파일 |
| --- | --- |
| 초기 원본·레퍼런스·자체 예제 | `data/imported-items.json`, `research-sources.json`, `jtech-items.json`, `glsl-items.json`, `manual-items.json` |
| CSS·SVG·색상 추가 입력 | `data/expanded-assets.json`, `css-wave-items.json`, `vector-wave-items.json`, `color-wave-items.json` |
| 모션·디자인·소재·추가 형상 | `data/phase2-motion-items.json`, `phase2-design-items.json`, `phase2-material-items.json`, `phase2-game-design-items.json` |
| 12,000개 확장 입력 | `data/expansion12-motion-items.json`, `expansion12-pattern-items.json`, `expansion12-vector-items.json`, `expansion12-material-items.json`, `expansion12-shape-items.json`, `expansion12-openmoji-items.json`, `expansion12-ctrlv-items.json`, `expansion12-motion-reserve-items.json` |
| Grok 후보의 검증된 실제 에셋 | `data/expansion12-grok-items.json`, `data/grok-import-report.json` |
| Promptfilm의 검토된 구성요소 | `data/expansion12-promptfilm-items.json`, `data/promptfilm-import-report.json` |
| 원본 변형 병합 정책 | `data/consolidation-policy.json` |
| 레퍼런스 분류·독립 미리보기 | `data/reference-review-cha.json`, `reference-review-sources.json` |
| 접근 불가 레퍼런스 제외 정책 | `data/reference-removals.json` |
| 전체 링크 점검과 정리 결과 | `data/link-audit-report.json` |
| 고정 원본·라이선스·정책·해시·검토 근거 | `data/upstream/` |

입력의 원본 ID·코드·색상·출처·고지를 유지합니다. JSON은 LF로 생성하며 `.gitattributes`는 upstream 원본에 줄바꿈 변환을 적용하지 않습니다. 원본·라이선스·근거 파일이 사라지거나 고정된 해시가 바뀌면 빌드 또는 검증이 실패합니다. 각 검증 JSON은 검사한 카탈로그와 입력 해시에 연결된 기록이므로 당시 범위와 날짜를 읽어야 합니다.

`data/upstream/`의 README, LICENSE, 약관 및 스토리보드는 출처 근거입니다. 프로젝트 안내 문서와 달리 제거하거나 편집하면 원본 검증과 이용 조건 추적이 깨질 수 있습니다.

전체 링크 점검 결과는 `data/link-audit-report.json`에 검사 날짜와 카탈로그 해시를 함께 기록합니다. 일반 브라우저에서도 확인할 수 없고 공개 원본 대체 경로가 없는 레퍼런스는 제외 정책으로 사이트·CLI·API·MCP에서 제거합니다. 자동 수집 차단이나 일시적인 요청 실패는 원본 삭제와 구분하며, 공개된 동일 원본이 확인되면 출처를 복구합니다. 삭제 결정과 당시 원본 기록은 감사 근거로 보존합니다.

## 저장 공간과 수집 캐시

채택한 원본, 전체 고지, 현재 입력이 참조하는 증빙은 `data/upstream/`에 보존합니다. 사이트에서 사용하는 JPEG는 `dist/assets/materials/`를 기준으로 삼으며 같은 미리보기를 upstream에 다시 복사하지 않습니다. 원본과 배포 JPEG가 같아 보여도 원본 영수증이 가리키는 파일을 삭제하거나 재인코딩하지 않습니다.

`exa-results/`는 수집과 검수의 임시 작업 공간입니다. 수집을 마치면 채택 입력·원본·권리 증빙·최종 판정을 먼저 확정하고, 필요한 근거를 보존한 뒤 카탈로그 사본과 재생성 가능한 개별 렌더를 정리합니다. 최종 검수 시트, 권리 원문, 현재 항목이 참조하는 검수 파일과 미검토 후보는 단순 캐시로 취급하지 않습니다. 전체 카탈로그, 컬렉션 JSON 및 배포 이미지는 웹·정적 AI 인터페이스가 사용하므로 유지합니다.

이번 보관 위치와 정리 이력은 [보관 영수증](../data/storage-retention.json)에 있습니다. `duplicate` 항목의 과거 경로는 `replacementPath`에 있는 동일 SHA256 파일로 확인합니다. `derived-cache`는 재생성 가능한 작업 사본을 정리한 기록입니다. `rejected-candidate`는 최종 제외된 이미지 원본을 퇴역시킨 기록이며, 출처 URL·원본 해시·제외 판정·시각 특징·검수 이미지가 남습니다. 과거 보고서는 당시 원본 경로와 해시를 그대로 유지하며, 현재 원본이 남아 있다는 의미로 해석하지 않습니다. 권리나 원본 식별이 보류된 항목, 작은 SVG 기하 증빙은 별도로 보존합니다.

제외된 소재의 검수 JPEG는 `data/upstream/expansion12-materials/retired-review/`에, 현재 CtrlV 자료의 검수 PNG는 `data/upstream/expansion12-ctrlv/preview-proof/`에 보관합니다. 캐시에서 옮긴 파일은 같은 바이트와 SHA256을 유지합니다. 영수증의 `evidencePromotions`와 `metadataMigrations`로 과거 경로를 새 경로에 연결하므로 새 클론과 휴대용 패키지에서도 검수 근거를 확인할 수 있습니다.

다음 확장에서는 새 후보의 원본 해시와 ID를 보관 영수증의 제외 기록에도 대조해 이미 제외한 자료를 다시 수집하지 않습니다. 시각 특징은 후보를 거르는 보조 정보이며 유일성 증명이 아닙니다. 제외 판정을 재검토하려면 공개 원본을 다시 취득하고 작품별 권리·기존 에셋과의 유사를 새로 검증해야 합니다. 정리 이후에도 로컬 빌드, 카탈로그 검증과 휴대용 패키지에서의 독립 재빌드를 통과해야 합니다.

과거 대용량 파일의 Git 이력 정리는 [이력 정리 영수증](../data/history-retention.json)에 별도로 기록합니다. 현재 커밋의 모든 파일 내용·경로·모드를 보호하고, 이전 버전의 불필요한 객체만 제거합니다. 과거 커밋은 일부 파일 없이 남을 수 있으므로 과거 빌드의 완전한 재현을 보장하지 않습니다. 기존 수집 보고서의 원본 해시와 커밋 ID는 당시 증빙으로 보존하며, 재작성된 커밋 ID는 영수증의 매핑으로 확인합니다. 원격 반영 상태도 영수증에서 확인하고, 기존 원격 이력을 다시 병합해 제거한 객체를 복원하지 않도록 합니다.

## 자료 추가와 검증

새 자료는 원본과 적용 라이선스를 확인한 뒤 기존 입력 스키마에 맞게 추가합니다. 코드·DOM·색상·이미지 구성, 출처 URL과 고정 버전, 전체 고지, 원본 및 저장 파일 해시, 검토 근거를 보존합니다. 기존 입력과 보존된 변형도 함께 대조해 같은 코드·색상·형상이나 사실상 같은 효과를 추가 카드로 늘리지 않습니다. 원본이나 고지가 불명확한 링크는 복제 권한이 있는 저장 에셋으로 취급하지 않습니다.

Promptfilm 입력은 `data/upstream/expansion12-promptfilm/`의 고정 원본·고지·`source-lock.json`·`import-plan.json`에서 오프라인으로 재생성합니다. 다음 명령은 검토된 정확한 줄 범위와 SHA256을 확인해 JavaScript 발췌문 및 독립 CC0 개념도를 만들며, 원문 JavaScript를 실행하지 않습니다. 재생성 후 아래 빌드와 검증을 실행합니다.

```sh
python scripts/import_promptfilm.py
```

```sh
python scripts/build.py
python scripts/verify_catalog.py
python scripts/recheck_consolidation.py
```

중복·유사성 재검사는 현재 대표 항목을 CSS·SVG·팔레트·GLSL·레퍼런스·이미지 기준으로 확인하고 `data/consolidation-recheck.json`을 생성합니다. 기존 판정은 원본과 문맥 해시가 일치할 때만 적용됩니다. 검사에서 발견된 미검토 후보를 판단한 뒤 정책을 갱신해야 합니다. 수치·구조 비교가 전 세계의 모든 모션이나 모든 프레임에 대한 유일성을 보장하지는 않습니다. 이미지 중복·유사성 재검사에만 선택 의존성을 사용합니다.

저장량 목표는 무결성 검사와 별도로 `python scripts/verify_catalog.py --minimum-stored 12000`으로 확인합니다. 목표에 미달하면 실패합니다. 이번 확장의 표본 채택률, 실제 추가 수량, 부족분과 검토한 공급 범위는 `data/expansion12-report.json`에 기록하며, 접근 불가·권리 불명·미지원 후보를 잔여 채택 가능 자료로 계산하지 않습니다.

```sh
python -m pip install -r scripts/phase2-requirements.txt
python scripts/recheck_consolidation.py
```

공개 원본을 확인할 때 robots.txt와 출처 약관을 따르고 접근 거부·호출 제한에서는 중단합니다. MP4/MOV/WebM은 저장하지 않으며 출처의 실행 스크립트를 사이트에서 실행하지 않습니다. 원본 HTML·JS·TS는 추출과 권리 확인의 근거로 보존하며, 검토된 JavaScript 발췌문은 실행하지 않는 원본 데이터로도 저장합니다. 이 발췌문의 개념도는 별도 CC0 코드로 제공하며 원본의 라이선스와 구분합니다. 갱신된 원본에는 기존 병합·레퍼런스 검토 정책의 해시가 맞지 않을 수 있으므로 해당 항목을 다시 검토합니다. 레퍼런스는 자동으로 최신 상태가 보장되지 않습니다.

이번 확장은 저장 에셋 12,000개를 목표로 하며 검토 레퍼런스는 별도로 집계합니다. 모션 100개, 패턴 120개, 소재 100개, 벡터 130개, 복합형상 50개를 먼저 고정해 원본·권리·미리보기·기존 변형·분야 간 유사를 검증합니다. 소재의 최신 100개 표본은 해당 목록의 전수 조사이며 전체 공급량으로 채택률을 외삽하지 않습니다. 결과와 개별 채택·제외 근거는 `data/upstream/expansion12-*/`에 보존합니다. 다음 15,000개와 20,000개 확장은 이번 실채택률과 아직 검증하지 않은 원본 공급량을 확인한 뒤 별도로 진행합니다.

새 확장 입력의 `collectionEvidence`는 원본 파일·고지·저장 본문의 SHA256을 연결합니다. 빌드와 카탈로그 검증은 네트워크 접속 없이 이 증거를 검사하며, 해시 불일치·누락·프로젝트 밖 경로·파일 링크가 있으면 중단합니다. 절차형 GLSL은 원본 조각과 공개 초깃값을 보존한 로컬 시간 호스트 어댑터로 재생하고, SVG는 허용한 로컬 기하·필터·마스크만 렌더링합니다.

Grok의 후보 4곳은 사이트 전체를 복제할 수 있다는 뜻이 아닙니다. 실제 채택은 개별 작품의 공개 원본·저자·재배포 권리·미리보기·중복 검증을 통과해야 합니다. 동일 작품의 저자 배포본 또는 명시적 CC0 공개 미러를 이용하면 원래 후보 사이트와 대체 원본의 관계를 함께 보존합니다. 접근 또는 권리 확인이 막힌 후보는 저장량에 포함하지 않으며, 이번 결과와 원본 근거는 `data/grok-import-report.json` 및 `data/upstream/expansion12-grok/`에서 확인합니다.

과거 JSON 검토 기록은 당시 실행 결과·카탈로그·원문에 연결된 이력입니다. 그 안에 남은 당시 도구나 개발 문서 경로는 해당 파일이 현재도 존재한다는 보증이 아니며, 현재 재현 명령은 이 문서의 빌드·검증·재검사 명령입니다.

## 개발 회귀 검사

인터페이스·정책·미리보기 코드의 변경을 확인할 때 실행합니다.

```sh
python -m unittest discover -s tests -p "test_*.py"
node tests/reference-ui-check.js
node tests/variant-ui-check.js
```

`tests/preview-check.html`과 `tests/preview-check.js`는 실제 브라우저에서 CSS·SVG 렌더러와 보안 제한을 확인하는 검사 도구입니다. JavaScript 문법 검사만으로 브라우저 동작을 검증했다고 판단하지 않습니다.

## 패키징과 사이트 자산

```sh
python scripts/package.py
```

현재 파일을 포함한 `Motion-Lab.zip`을 생성하고 ZIP 무결성을 확인합니다. 새 패키지가 필요한 경우 현재 입력으로 빌드·검증한 뒤 생성합니다. `dist/`는 정적 웹 호스팅에 사용할 수 있고 CLI·MCP는 Python 런타임과 데이터베이스를 사용합니다.

패키징은 파일과 부모 경로의 symlink·junction·reparse point 및 프로젝트 밖 경로를 거부합니다. 일반 파일로 준비한 원본을 사용하세요. ZIP은 임시 파일에서 무결성을 확인한 뒤 교체하므로 생성 실패 시 이전 ZIP을 유지합니다.

사이트 OG 이미지는 `dist/assets/og-site.png`, README 배너와 GitHub 소셜 이미지는 `docs/assets/og-repository.jpg`입니다. 호스팅 주소를 정할 때 `dist/index.html`, `dist/library.html`의 `og:url`, `og:image`, `twitter:image`를 실제 HTTPS 주소로 맞춥니다. GitHub 소셜 이미지는 저장소 Settings > Social preview에서 별도로 설정합니다. README 이미지를 커밋하는 것만으로 원격 소셜 이미지가 설정되지는 않습니다.
