# Motion Lab Originals CSS recipes

작성일: 2026-10-08. `data/manual-items.json`에는 외부 소스를 가져오지 않고 이 프로젝트에서 작성한 **24개 CSS 예제**가 들어 있다. 가져온 키프레임 컬렉션과 별도로 표시하기 위해 `sourceName: Motion Lab Originals`, `verification: original-authored`를 사용한다. 모든 예제는 MIT 라이선스로 제공하며 전체 라이선스와 Copyright (c) 2026 Motion Lab contributors 표시가 각 코드 안에 포함되어 있다.

## 사용 방법

예제 하나의 CSS를 복사하고 요소 하나에 `motion-sample` 클래스를 붙인다. 기본 텍스트와 `preview.sampleText`는 `ML`이다. 나머지 필요한 시각 요소는 CSS 의사 요소로 생성된다. 키프레임 이름은 `ml-`로 시작한다. 여러 예제를 같은 문서에서 함께 사용할 때는 각 `.motion-sample` 선택자를 개별 클래스로 바꾸거나 별도 컨테이너 범위로 묶는다. 갤러리의 각 iframe은 이를 분리한다.

```html
<div class="motion-sample">ML</div>
```

호버·누름 예제는 실제 UI에서 의미 있는 버튼에 적용할 수 있다.

```html
<button type="button" class="motion-sample">확인</button>
```

각 코드에는 크기·색상·글꼴을 정하는 기본 스타일과 실제 효과가 함께 들어 있다. `--ml-accent`, `--ml-ink`를 바꿔 색상을 조정한다. 요소의 크기를 변경할 수 있지만, 스캔 라인·광택처럼 픽셀 이동 거리를 쓰는 예제는 이동 거리를 함께 조절해야 한다.

반복과 대기·퇴장 구간은 갤러리에서 동작을 비교하기 위한 데모다. 제품의 등장 효과로 적용할 때는 퇴장·재설정 키프레임을 제거하고 `100%`를 내용이 보이는 상태로 끝낸 뒤 `animation-iteration-count: 1`, `animation-fill-mode: both`로 설정한다. 반복 횟수만 바꾸면 마지막 퇴장 상태가 유지될 수 있다. 이벤트나 화면 진입 시 필요한 순간에만 클래스를 적용한다.

`Stepped Typewriter`는 기본 2글자·2ch이며, 내용을 바꾸면 `--ml-glyph-count`와 너비를 함께 맞춘다. 글자 수와 너비가 다른 비례 글꼴보다는 고정폭 글꼴에서 일정한 타이핑 간격이 나온다. `Decorative Stepped Ticker`는 의사 요소의 문자열을 바꾸는 장식 데모다. 실제 값은 HTML 텍스트로 제공하고, 숫자 변경을 스크린리더에 알려야 하는 기능은 별도의 의미 있는 상태 텍스트로 구현한다. 이 CSS는 실제 데이터를 계산하지 않는다.

모든 예제는 `prefers-reduced-motion: reduce`에서 반복과 전환을 끄고 변형·흐림·클리핑을 해제한다. 시차 막대는 정지된 막대로, 장식 숫자는 정지된 문자열로 남는다. 확인 립플과 광택 오버레이는 기본 투명 상태로 남는다. 타이포그래피의 정적 대비와 실제 버튼의 포커스 표시도 적용할 제품에서 확인한다.

## 수록된 24개 기법

| ID | 제목 | 분류 | 주 키프레임 |
| --- | --- | --- | --- |
| ml-original-wipe-reveal | Clip Wipe Reveal | transition | ml-wipe-reveal |
| ml-original-iris-reveal | Center Iris Reveal | transition | ml-iris-reveal |
| ml-original-diagonal-cut | Diagonal Cut Reveal | transition | ml-diagonal-cut |
| ml-original-perspective-flip | Perspective Card Flip | transition | ml-perspective-flip |
| ml-original-focus-reveal | Focus Blur Reveal | transition | ml-focus-reveal |
| ml-original-kinetic-tracking | Kinetic Tracking | typography | ml-kinetic-tracking |
| ml-original-stepped-typewriter | Stepped Typewriter | typography | ml-stepped-typewriter |
| ml-original-text-fill-sweep | Text Fill Sweep | typography | ml-text-fill-sweep |
| ml-original-rgb-ghost | RGB Ghost Offset | typography | ml-rgb-ghost |
| ml-original-neon-breathe | Neon Breathing Type | typography | ml-neon-breathe |
| ml-original-stagger-bars | Three Beat Stagger | loader | ml-stagger-bars |
| ml-original-squish-spring | Squish Spring Arrival | animation | ml-squish-spring |
| ml-original-overshoot-arrival | Overshoot Slide Settle | animation | ml-overshoot-arrival |
| ml-original-upright-orbit | Upright Orbital Motion | animation | ml-upright-orbit |
| ml-original-stepped-ticker | Decorative Stepped Ticker | typography | ml-stepped-ticker |
| ml-original-gradient-flow | Wide Gradient Flow | gradient | ml-gradient-flow |
| ml-original-checker-drift | Seamless Checker Drift | background | ml-checker-drift |
| ml-original-halftone-breathe | Halftone Field Breathe | background | ml-halftone-breathe |
| ml-original-scanline-sweep | Scanline Inspection Sweep | background | ml-scanline-sweep |
| ml-original-border-draw | Four Edge Border Draw | interaction | ml-border-draw |
| ml-original-sheen-pass | Diagonal Sheen Pass | interaction | ml-sheen-pass |
| ml-original-hover-elevation | Hover Elevation Demo | interaction | ml-hover-elevation |
| ml-original-press-feedback | Press Compression Demo | interaction | ml-press-feedback |
| ml-original-confirmation-halo | Confirmation Halo Ripple | interaction | ml-confirmation-halo |

스태거 막대는 중앙 배경과 좌우 의사 요소를 독립적으로 움직이기 위해 보조 키프레임 `ml-stagger-edge`를 추가 사용한다. 숫자 티커·스캔 라인·광택·확인 립플은 주 키프레임이 의사 요소에 적용된다. CSS 미리보기는 주 키프레임만 떼어내지 않고 `.motion-sample`, 의사 요소, 미디어 쿼리를 함께 보존해야 한다. 상세 미리보기에서는 호버와 `:active`를 직접 확인할 수 있다.

## 기록과 검증

각 레코드는 `kind: code`, `language: css`, `license: MIT`이며 전체 CSS가 `code`에 들어 있다. `preview.adapted: true`는 단일 요소 갤러리 시연에 맞춘다는 뜻이다. 외부 작품을 가져와 수정했다는 뜻이 아니다. `sourceUrl`은 Motion Lab 프로젝트의 예약된 공개 주소이며, 예제 작성 시점에 배포 완료를 확인했다는 뜻은 아니다.

24개 레코드의 고유 ID와 데이터 스키마, 주 키프레임 이름의 존재, 축소 모션 미디어 쿼리, MIT 표시를 검사했다. CSS 내부에 외부 URL·import·스크립트는 없다. 각 예제는 CSS 표현만 제공하며 폼·API·DB·개인정보 수집 기능이 없다. 숫자나 글자를 실제 데이터와 연결하는 코드는 별도 구현 범위다.

