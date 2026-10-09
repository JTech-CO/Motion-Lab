# CSS duplicate audit

Snapshot: 2026-10-09, catalog SHA-256 `1688368bafbff4df4580d83d9ce8d8b128199cd0ac99089a9765d5828a4c9ea3`.

All 1,979 stored CSS records parsed successfully. Their 1,957,231 possible pairs were exhaustively screened by canonical source/preview signatures; 1,670 content-defined candidate pairs received deeper comparison. This is offline static analysis. No CSS was executed or browser frames compared, and no catalog records were removed.

The report found 8 equivalent stored-program groups (18 entries, 12 pair relationships, 10 entries beyond one representative per group), one pair differing only in duration, 20 review candidates, and 62 shared-motion families. The 20 candidates were then inspected from their actual declarations: 19 retain meaningful geometry variants and one is a companion component of a larger source loader. Shared motion families are not duplicate findings.

## Reproduce

```console
python -X utf8 scripts/duplicate_audit_css.py
python -X utf8 -m unittest tests.test_duplicate_audit_css
```

The generated [CSS report](../data/duplicate-audit/css.json) includes every inspected ID and its original-code, canonical-program and timing-normalized hashes. The [manual source review](../data/duplicate-audit/css-review.json) freezes all 20 candidate decisions, concrete changed declaration values, catalog/report hashes, and original component quality notes. It uses no source name/title as similarity evidence. Its manual decisions must be re-reviewed if their original code hashes change.

Exact comparison retains declaration/rule order, quoted strings, geometry, selectors and interaction triggers, preview element types/children/text, used variables and animation direction/iteration/fill. Consistent class/keyframe renaming is normalized only in selectors and animation name references. A keyframe named `rotateX` never renames the transform function `rotateX()`. Hex color case, shorthand and opaque alpha normalize to equivalent colors; reversed gradient order stays distinct.

Timing-only comparison masks duration, delay, easing and interior frame positions, while retaining 0%/100% endpoint anchors. Thus `from {translateY(200%)}` and `to {translateY(200%)}` remain distinct entrance/exit behavior. Numerical candidate comparisons also require equal element topology and playback controls, no sign reversal, equal units and only small coordinate changes. Candidate similarity percentages never by themselves authorize deletion.

The duration-only pair is `vector-sds-motion-forge-sds-scroll-stagger-grid` and `vector-sds-motion-forge-sds-scroll-wave-rise`. Both preserve the same three-child sample, `sds-viewportRise` keyframes and delays from 0s through 0.88s; the main duration is 0.6s versus 0.7s. This is a reasonable parameterized variant candidate.

## Equivalent stored snippets and source context

The exact stored groups are:

- `animate-fadein`, `vivify-fadein`, `wicked-fadein`.
- `animate-fadeout`, `vivify-fadeout`, `wicked-fadeout`.
- `spinkit-sk-chase`, `spinkit-sk-swing`.
- uiGradients pairs `0010/0020`, `0012/0021`, `0034/0343`, `0155/0344`, `0216/0345`.

SpinKit illustrates a material extraction limitation. The two stored snippets both contain only `100% { transform: rotate(360deg) }` and the same generated single-element animation. The pinned original [SpinKit source](../data/upstream/spinkit/source.css) instead defines Chase with six children, staggered delays, companion child rotations and pseudo-element scaling. Swing has two children, different sizes/positions and a different child scale animation. Their stored samples are equivalent; their complete original loaders are distinct. Repair the component extraction before deciding whether original source identities should be merged.

The Three Dots candidate has shadow coordinates 9999px versus 9984px, a difference of 15px. The pinned original [Three Dots source](../data/upstream/three-dots/source.css) sets `left: -9999px` and combines main/before/after shadows into three dots at 0/-15/+15px with different delays. The stored samples omit that positioning and composition. Large shared coordinate origins can inflate numerical similarity; this pair remains a source companion, with an extraction quality note.

Other candidates preserve explicit differences: square versus border triangle, top/center/bottom transform pivots, mask stripe angles/densities, reversed mask gradients, initial scale 0.4 versus 2, moving gradient stop widths, and loader bar geometry. Those values are retained in the review report. They should not be collapsed solely because they reuse a keyframe primitive.

Thirteen regression tests cover consistent renaming, quoted literals, hex equivalence, changed geometry/DOM/triggers, frame timing, endpoint swaps, direction/iteration, variable dependency context, large/sign-reversed numeric deltas, and parse failures. These checks validate the audit rules, not browser appearance. Arbitrarily different but visually equivalent CSS formulas remain outside its proof boundary.
