# Motion Lab 초기 소스 조사

조사일: 2026-10-08 (Asia/Seoul). 저장 파일: `data/research-sources.json`.

이번 파일은 **118개 고유 공개 URL의 레퍼런스 목록**이다. 전 세계 전체 소스를 수집했다는 뜻이 아니며, 수집 가능한 후보를 확장하는 초기 조사 결과다. 외부 작품의 원본 코드·이미지·MP4를 복제하지 않았다. 설명은 검색 발췌 또는 페이지 응답에 근거해 새로 작성한 짧은 한국어 요약이다.

## 결과와 검증 범위

| 구분 | 수 |
| --- | ---: |
| Exa 검색 호출 | 6 |
| Exa 요청 결과 합계 (`sources_reviewed` 규칙의 요청 수) | 120 |
| Exa 실제 반환 결과 | 119 |
| Parallel Search 검색 호출 | 2 |
| Parallel Search 실제 반환 결과 | 20 |
| 검색 결과의 고유 URL | 139 |
| 정확한 URL 페이지 추출 요청 | 50 |
| 페이지 추출 응답 성공 | 49 |
| 최종 선정 고유 URL / 고유 ID | 118 / 118 |
| 최종 `page-reviewed` | 47 |
| 최종 `search-reviewed` | 71 |

`page-reviewed`는 Exa가 반환한 해당 URL의 본문 또는 메타데이터를 읽었다는 뜻이다. 브라우저 렌더링·전체 예제 실행·라이선스 전문 확인을 뜻하지 않는다. `search-reviewed`는 제목과 관련 발췌를 검토한 상태이며 전체 페이지 검증은 남아 있다. `verifiedAt`은 조사일이며 외부 페이지의 최종 수정일이나 실시간 HTTP 접근 보증이 아니다.

JavaScript 앱의 일부 페이지는 추출 본문이 제목·메타데이터 정도에 그쳤다. Three.js, Shader Gradient, Color Hunt, uiGradients, Mesh Gradients, Swup, React Bits 등이 이에 해당한다. 이 페이지의 요약은 응답이 지원하는 범위로 제한했다. Coolors와 React Bits의 구체적 도구 기능은 Parallel Search의 공식 페이지 발췌에서도 확인했다. Mesh Gradients의 응답은 `https://oodesign.github.io/mesh-gradients/`로 연결되는 리디렉션 안내였다. `hue.tools`는 추출 오류로 제외했다. Material Design 3와 Uber Base는 제목·셸만 반환되어 이번 최종 목록에서는 제외했다.

## 검색 로그

| 도구 / 흐름 | 질의 각도 | 요청 / 실제 결과 |
| --- | --- | ---: |
| Exa 1 | 공식 JavaScript 타임라인·스프링·SVG·스크롤 애니메이션 구현 문서 | 20 / 20 |
| Exa 2 | WebGL·GLSL·절차적 그라디언트·제너러티브 아트·입자 소스 | 20 / 20 |
| Exa 3 | 키네틱 타이포그래피·페이지 전환·마이크로인터랙션 제작 사례 | 20 / 20 |
| Exa 4 | 모션 디자인 시스템·이징·색상 도구·브랜드 가이드 | 20 / 19 |
| Exa 5 | 일본어·한국어 크리에이티브 코딩과 모션그래픽 프로젝트 | 20 / 20 |
| Exa 6 | 브라질·프랑스·독일 등 글로벌 실험적 디자인 스튜디오 | 20 / 20 |
| Parallel Search 1 | 팔레트·CSS/SVG 배경·그라디언트·이징의 공식 도구 | 결과 수 옵션 없음 / 10 |
| Parallel Search 2 | 페이지 전환·React 효과·크리에이티브 코딩의 공식 프로젝트 | 결과 수 옵션 없음 / 10 |

Exa의 의미 기반 검색은 관련도를 보장하지 않으므로, 빈 GitHub topic 페이지·동일 프로젝트의 포크·동일 라이브러리의 여러 진입 페이지·일반 홍보 글·제목과 발췌가 어긋난 결과를 걸렀다. 검색이 Coolors와 Barba에 편중된 구간은 알고 있던 공개 도구의 정확한 URL을 추가 추출해 팔레트·전환·SVG·이징의 범위를 보완했다. 링크 추적 파라미터는 저장 전 제거했다. 동일 프로젝트의 문서가 별도 목적을 가진 경우만 유지했다.

## 사용자가 제공한 출발점

- [Career Hacker Alex · 따라 만드는 모션그래픽 160](https://www.careerhackeralex.com/sharings/cha-motion-kit): 페이지 응답에 160개 모션, 2026-10-03 업데이트, 화면·창작·녹화 편집 소스 61개와 프롬프트 사용 흐름이 명시되어 있었다. 이는 출처 페이지의 설명이며 모든 160개 항목을 개별 추출·실행했다는 뜻은 아니다.
- [JTech-CO/Motiongraphic](https://github.com/JTech-CO/Motiongraphic): README에서 SpaceX, Genesis, DJI, Loopfield Studio의 HTML 기반 데이터 스토리 4편과 코드·프롬프트·스토리보드 링크를 확인했다. 작품의 라이선스 전문은 이 조사에서 확인하지 않았다.

## 분류

| 분류 | 레퍼런스 수 |
| --- | ---: |
| reference | 41 |
| typography | 18 |
| animation | 17 |
| shader | 12 |
| gradient | 9 |
| interaction | 7 |
| palette | 6 |
| background | 4 |
| transition | 3 |
| loader | 1 |

도구·자료·포트폴리오의 링크를 분류한 수다. 라이브러리 하나에 들어 있는 모든 효과를 각각 센 수가 아니다. 한국어와 일본어 소스, 영어 공식 문서, 브라질·프랑스·독일 스튜디오가 포함되어 있지만 언어·국가별 완전한 coverage는 보장하지 않는다.

## 저작권과 수집 경계

모든 항목은 `kind: reference`, `code: null`, `license: reference-only`로 저장했다. 이는 원본 파일 복제나 상업적 재배포 권한을 부여하지 않는다. 공개 저장소의 라이선스 라벨이 보이는 경우에도, 코드·이미지·폰트·예제 자산에 서로 다른 조건이 적용될 수 있어 이번 링크 목록은 보수적으로 통일했다. 실제 코드를 가져오는 작업은 정확한 라이선스 파일과 적용 범위를 별도로 확인해야 한다. SVG Backgrounds처럼 자체 라이선스와 표시 조건이 있는 자산은 그 조건을 따라야 한다.

검색과 페이지 추출은 연결된 Exa 및 Parallel Search 도구를 사용했다. 직접 수행한 robots.txt 검사·브라우저 방문 기록은 이 파일에 포함되지 않는다. robots.txt나 서비스 약관이 자동 수집을 제한하면 해당 출처의 일괄 수집을 중단하고 링크 레퍼런스로 유지한다. 로그인·유료 구간·CAPTCHA·접근 차단을 우회하지 않는다. 공개 브라우저 확인 또한 대량 수집 제한을 우회하는 수단으로 사용하지 않는다.

확장 시에는 도메인별 허용 정책, 최대 깊이·페이지 수, 요청 간격, 라이선스 근거, 최종 URL, 원본 변경 감지, 실패·차단 이유를 함께 기록하는 것이 적절하다. 이 초기 목록에는 원본 저장 없이 재검토할 수 있도록 출처 URL과 확인 수준이 남아 있다.

