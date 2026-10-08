# 개별 모션 소스 확장

검토일: 2026-10-08. 결과는 `data/expanded-assets.json`의 **58개** 개별 자료다. 5개 원출처에서 CSS 코드 40개, SVG 코드 12개, 개별 컴포넌트 참고 자료 6개를 확인했다. MP4나 영상 파일은 추가하지 않았다.

브랜드 이름만으로 효과를 추측하지 않았다. 코드의 실제 선택자·키프레임·속성·요소 수 또는 컴포넌트 구현 및 문서에서 확인한 구성만 기록했다. 같은 효과를 크기·색상 조합으로 늘리지 않았다.

| 원출처 / 고정 버전 | 개별 자료 | 기록 방식 | 근거 |
| --- | ---: | --- | --- |
| Loaders.css / Connor Atherton | 29 | CSS 요소 구조와 키프레임·선택자 블록 | [원본 CSS](https://github.com/ConnorAtherton/loaders.css/blob/dee8aabed3adbfb121b931a42e3ebc233fafdd68/loaders.css), [실제 자식 수 매핑](https://github.com/ConnorAtherton/loaders.css/blob/dee8aabed3adbfb121b931a42e3ebc233fafdd68/loaders.css.js), [README의 전체 MIT](https://github.com/ConnorAtherton/loaders.css/blob/dee8aabed3adbfb121b931a42e3ebc233fafdd68/README.md#licence) |
| Luke Haas CSS Loaders | 8 | 개별 CSS 파일 전체와 wrapper/loader DOM | [load1.css](https://github.com/lukehaas/css-loaders/blob/c7fdf5ac73c71fec3142414adf8d592c7d2c6bf4/css/load1.css), [MIT](https://github.com/lukehaas/css-loaders/blob/c7fdf5ac73c71fec3142414adf8d592c7d2c6bf4/LICENSE) |
| Sam Herbert SVG Loaders | 12 | 개별 SVG 파일 전체와 SMIL 속성 | [audio.svg](https://github.com/SamHerbert/SVG-Loaders/blob/561eacac2f46e2b02e48df547324dcea94a6a1c5/svg-loaders/audio.svg), [MIT](https://github.com/SamHerbert/SVG-Loaders/blob/561eacac2f46e2b02e48df547324dcea94a6a1c5/LICENSE.md) |
| Hover.css **v2.1.1** | 3 | 실제 해당 버전의 CSS 효과 블록 | [고정 CSS](https://github.com/IanLunn/Hover/blob/7b2597e011c3495511f93cbca4e148308e0df1c7/css/hover.css), [MIT 원문](https://github.com/IanLunn/Hover/blob/7b2597e011c3495511f93cbca4e148308e0df1c7/license.txt), [당시 사용 조건](https://github.com/IanLunn/Hover/blob/7b2597e011c3495511f93cbca4e148308e0df1c7/README.md#license) |
| Magic UI | 6 | 개별 TSX 구현·문서를 읽은 참고 메타데이터 | [Text Animate 구현](https://github.com/magicuidesign/magicui/blob/cdb348cb4c72a9b54b554d8617801e479fbc8714/apps/www/registry/magicui/text-animate.tsx), [컴포넌트 문서](https://magicui.design/docs/components/text-animate), [MIT](https://github.com/magicuidesign/magicui/blob/cdb348cb4c72a9b54b554d8617801e479fbc8714/LICENSE.md) |

## 실제 분해 목록

**Loaders.css — 29개**: ball-pulse, ball-grid-pulse, ball-clip-rotate, ball-clip-rotate-pulse, square-spin, ball-clip-rotate-multiple, ball-pulse-rise, ball-rotate, cube-transition, ball-zig-zag, ball-zig-zag-deflect, ball-triangle-path, ball-scale, line-scale, line-scale-party, ball-scale-multiple, ball-pulse-sync, ball-beat, line-scale-pulse-out, line-scale-pulse-out-rapid, ball-scale-ripple, ball-scale-ripple-multiple, ball-spin-fade-loader, line-spin-fade-loader, triangle-skew-spin, pacman, ball-grid-beat, semi-circle-spin, ball-scale-random.

이 목록은 upstream `loaders.css.js`의 `divs` 매핑에 있는 실제 컴포넌트 중 CSS를 확인한 것이다. SCSS 파일 이름 개수로 자료 수를 추정하지 않았다. `line-scale-party`처럼 SCSS 파일 이름과 공개 CSS 클래스 이름이 다른 경우 실제 CSS 클래스를 기록했다.

**Luke Haas — 8개**: load1(막대 높이), load2(두 반원의 링 노출), load3(그라디언트 원호 회전), load4(그림자 점 크기 순환), load5(그림자 점 투명도 순환), load6(회전하는 그림자 꼬리), load7(세 그림자 점 바운스), load8(테두리 링 회전).

**SVG Loaders — 12개**: audio, ball-triangle, bars, circles, grid, hearts, oval, puff, rings, spinning-circles, tail-spin, three-dots. 각 SVG의 `animate`/`animateTransform`, 대상 속성, 값 목록, 시작 시간, 주기를 `evidence.animations`에 기록했다.

**Hover.css v2.1.1 — 3개**: Pulse, Wobble Vertical, Curl Top Right. 선택한 구버전에는 최신 문서의 Underline From Center가 없어 수집하지 않았다. 현재 Hover.css의 사용 조건을 이 구버전 자료에 대입하거나, 구버전 MIT를 현재 전체 제품에 적용했다고 주장하지 않는다.

**Magic UI — 6개**: Text Animate, Meteors, Shimmer Button, Animated Beam, Particles, Border Beam. 각각 문자 분할·변형, 유성 위치·지연, 원추 그라디언트 둘레 빛, 요소 경계 기반 SVG 곡선, 캔버스 입자 갱신, 마스크·offsetDistance 기반 테두리 이동을 확인했다. React/Tailwind 및 Motion 의존성을 `evidence.details.dependencies`에 기록했다. CSS/SVG 실행 계약에 해당하지 않는 TSX 코드를 임의의 CSS 미리보기로 바꾸지 않았으며, 이 6개는 `kind: reference`, `code: null`이다.

## 데이터 및 실행 계약

- 모든 자료는 고정 커밋의 개별 아티팩트 URL, 라이선스 URL, 전체 `licenseText`, 검토일, `sourceCommit`을 포함한다.
- `evidence`는 실제 컴포넌트, 원본 경로, 동작 요약, 출처 URL, 요소 구조, CSS 키프레임/관찰 속성 또는 SVG SMIL 속성을 담는다.
- 52개 코드에는 저작권자와 전체 MIT 조건을 넣었다. SVG에는 XML 주석으로 삽입하여 XML 구문을 유지했다.
- `evidence.storedCodeSha256`은 **전체 라이선스 주석을 포함한 저장 코드**의 SHA-256이다. 원저장소 파일 전체의 해시라고 주장하지 않는다.
- CSS는 원래 클래스 이름·숫자·선택자·변환 값을 유지했다. `.motion-sample`로 바꾸지 않았다. `preview.dom`에 실행에 필요한 실제 닫힌 요소 트리를 제공한다.
- Luke Haas에는 `.load1 .loader`처럼 부모 클래스가 필요하다. 따라서 `load1 > loader` 구조와 화면 낭독기용 “Loading...” 텍스트를 제공한다.
- Loaders.css는 `scale`·`rotate` 같은 전역 키프레임 이름을 여러 컴포넌트에서 재정의한다. 필요한 선택자 블록과 그 선택자보다 앞에 있는 가장 가까운 참조 키프레임 정의를 추출하여 컴포넌트를 분리했다. 각 코드 예제를 독립 iframe/범위에서 실행해야 이름 충돌을 피할 수 있다.
- 일부 원본 CSS에는 `:first-child`, `:last-child`, `:nth-child(2n)`, `:nth-child(2n-1)`, `:nth-of-type(n)`가 있다. 요소 수뿐 아니라 이러한 선택자와 여러 애니메이션을 지원해야 실제 조합을 재현할 수 있다.
- Hover 효과는 `hover/focus/active`에서 실행한다. `preview.requiresInteraction: true`로 이를 명시했다. 기본 상태만으로 계속 움직이는 애니메이션이라고 표시하지 않는다.
- SVG 12개에는 스크립트·이벤트 핸들러·외부 href·inline style이 없다. tail-spin의 `url(#...)`은 같은 SVG 안의 선형 그라디언트를 참조한다.
- 미리보기의 안전 검사·선택자 지원은 실행 엔진이 별도로 수행한다. 원본에 없는 애니메이션을 합성하여 실제 원본 재현으로 표시하지 않는다.

## 수집 및 검증 기록

Exa 4회 검색으로 20개 결과를 요청·검토했고 Parallel Search 1회에서 10개 결과를 받았다. 검색 결과의 미러·IP 호스트·라이선스 추정은 아티팩트 근거로 사용하지 않았다. 원저장소와 라이선스를 재확인하고, Exa로 16개 페이지/원문 URL을 읽었다. HTML 추출기가 SVG 태그를 제거하는 경우에는 추출 결과를 코드라고 저장하지 않았다.

정확한 원문은 공개 GitHub contents API의 base64 또는 raw 파일로 읽었다. 채택한 고정 버전의 서로 다른 원문 파일은 38개다(Loaders.css 4, Luke Haas 10, SVG Loaders 14, Magic UI 7, Hover v2.1.1 3). 브라우저·로그인·접근 제한 우회는 사용하지 않았다. 일반 셸 네트워크의 DNS 제한 후 공개 파일 읽기만 범위를 지정하여 승인된 조회를 사용했다.

검증 결과:

- 58개 모두 프로젝트 `validate_item` 통과.
- 입력 파일 내부 ID 중복 없음.
- 52개 코드 모두 전체 MIT 고지·저작권·조건·면책 문구 보존.
- 12개 SVG 모두 XML 파싱 통과.
- 40개 CSS 모두 닫힌 DOM 미리보기 구조 포함, `@import`·외부 `url()` 없음.
- 코드 바이트를 기준으로 저장 SHA-256 생성.

제외 사례도 명확히 남긴다. [React Bits의 현재 라이선스](https://github.com/DavidHDev/react-bits/blob/main/LICENSE.md)는 검색에서 MIT + Commons Clause로 확인되어 일반 MIT 코드로 복제하지 않았다. [easings.net 원저장소](https://github.com/ai/easings.net/blob/master/LICENSE)는 GPLv3이므로 이 MIT 코드 확장에는 포함하지 않았다. 영상 및 단순 출처 링크 개수를 늘리기 위한 브랜드 참고 항목은 추가하지 않았다.

