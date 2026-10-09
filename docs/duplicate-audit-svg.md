# SVG redundancy audit

The audit inspected all **1,272 stored SVG code assets** and classified all
**808,356 unordered pairs**, including pairs from different source projects.
There were no parsing or skipped-item errors. It reads local source code only;
no browser rendering, frame capture or perceptual comparison was performed.
The catalog and source assets were not modified.

| Source | Stored SVG items |
| --- | ---: |
| Material Line Icons | 1,214 |
| SVG Spinners | 46 |
| Sam Herbert SVG Loaders | 12 |

The audited full catalog SHA-256 is
`1688368bafbff4df4580d83d9ce8d8b128199cd0ac99089a9765d5828a4c9ea3`.
Every inspected ID, original code hash, canonical hash, timing-independent hash,
initial geometry hash, element inventory and numeric-geometry skeleton hash is
recorded in [the machine-readable report](../data/duplicate-audit/svg.json).

| Finding under this static comparison model | Groups or pairs | Items |
| --- | ---: | ---: |
| Canonical exact duplicates | 0 | 0 |
| Same structure with only timing differences | 2 pairs | 4 |
| Additional small-coordinate review candidates | 0 | 0 |
| Same initial geometry, with potentially different useful behavior/style | 327 families | 930 |
| Outside initial-geometry families | - | 342 |

Family and near-match membership overlap. The 930 family members are not 930
duplicates: many intentionally differ in final fill, one-shot versus looping
motion, direction of transition, animated attributes, or final pose.

## Two same-effect rhythm variants

`vector-svg-spinners-pulse-3` and
`vector-svg-spinners-pulse-multiple` use the same three circles centered at
`(12,12)`, radius values `0;11`, opacity values `1;0`, spline curve and `1.2s`
animation duration. Their staggers are **0.4/0.8s versus 0.2/0.4s**. The first
restarts from the third animation's `begin+0.4s`; the second restarts at the
third animation's `end`. Thus, the overall restart/overlap rhythm differs.

`vector-svg-spinners-pulse-rings-3` and
`vector-svg-spinners-pulse-rings-multiple` make the same timing changes to
otherwise identical outlined circle animations. Their stroke-width animation
is also retained in the comparison.

These four assets are good candidates for grouping as two effects with named
rhythm variants. The high confidence label means **structural equality after
timing removal**, not identical frames or a browser-confirmed visual duplicate.
The report recommends retaining the named variants unless later visual review
and product requirements justify removal.

## False positives avoided by preserving meaningful differences

- `heart-filled` versus `heart-twotone`: final fill-opacity **1 versus 0.3**,
  with fill duration **0.4s versus 0.15s**. They remain style variants.
- `circle-to-confirm-circle-transition` versus its reverse:
  stroke-dashoffset **14;0 versus 0;14**, revealing versus removing the check.
- `download` versus `download-loop`: the latter adds an **indefinite repeating**
  animation. A reveal followed by ongoing motion is a useful behavior change.
- `download` versus `download-outline`: the first fills to opacity **1**;
  the second retains **fill=none** without that fill animation.
- `arrow-left` versus `arrow-right`: opposite arrow direction and changed
  path coordinates preserve distinct directional semantics.
- `account` versus `account-add`: the plus-sign component is an actual
  additional semantic shape.
- `wifi` versus `wifi-fade`: **discrete versus linear** appearance and
  **0.001s versus 0.1s** reset durations create a useful fade distinction.

The report contains concrete attribute values and source hashes for nine
manually inspected original-code examples. No source name or shared text
prefix is used as a redundancy verdict.

## Comparison rules and limits

Exact comparison normalizes XML namespace prefixes, attribute ordering,
indentation, numeric spelling, comments, unreferenced nonvisual metadata and
local IDs together with their references. It preserves child paint order,
dimensions, viewBox, initial state, paint, transforms, timing, repeat behavior,
fill behavior, easing and actual animated values. Redundant numeric linear
samples are reduced only when exact rational collinearity proves the same
piecewise interpolation over the same normalized times.

Near matching requires the same complete tree, initial state, style and
animated-value sequence after removing only `begin`, `end`, `dur`, `min`,
`max` and `keyTimes`. Duration changes over a factor of two are review
candidates rather than high-confidence near groups. Near pairs are never
joined transitively into an unproven larger cluster.

Small-coordinate candidates require identical tree, paint, path commands,
static transforms and animation values. Maximum coordinate deviation must be
at most **1.5%** of the smaller viewBox extent and RMS deviation at most
**0.6%**. Arc paths retain exact numbers so discrete arc flags cannot be treated
as small coordinate changes. No such candidate occurred in this catalog.

Initial-geometry families ignore style and animation differences but preserve
all drawable shapes, root dimensions, ancestor static transform chains and
mask/defs context. Initial geometry can be identical while later motion or
meaning differs, which is why these families are not deletion recommendations.

This audit does not prove general geometric or perceptual equivalence between
relative/absolute path representations, Bézier/arc/circle alternatives,
matrix-equivalent transforms, or different inherited paint structures.
Absence of a match is absence under this defined model, not proof that two
animations could never look similar when rendered.

## Reproduce

```sh
python scripts/duplicate_audit_svg.py
python -m unittest tests.test_duplicate_audit_svg -v
```

All 21 audit tests pass, including false-positive fixtures for reversed motion,
looping, fill/outline, semantic additions, painting order, viewBox, referenced
metadata, exact frame interpolation, nonuniform keyTimes and discrete frames.
Security fixtures reject DTD/entities, executable SVG, external references,
excessive size/depth/node count and pathological numeric exponents. XML is
bounded data and is never executed; reports are written atomically as UTF-8/LF.
