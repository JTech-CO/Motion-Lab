# Stored palette and static gradient color audit

This offline audit inspected all 2,446 stored palette arrays in the 6,108-entry
catalog. Catalog SHA-256:
`1688368bafbff4df4580d83d9ce8d8b128199cd0ac99089a9765d5828a4c9ea3`.
The catalog and source assets were not edited or removed.

| Relation | Palette-only result |
| --- | ---: |
| All palette pairs considered | 2,990,235 |
| Same color count | 904,907 |
| Different color count | 2,085,328 |
| Exact ordered RGBA arrays | 0 pairs |
| Exact reordered RGBA multisets | 0 pairs |
| Strict near colors with original order preserved | 25 pairs, 22 distinct items |
| Strict near colors in reversed order | 1 pair, 2 additional items |
| Strict near colors requiring another permutation | 0 pairs |
| Exact multiset containment at different color counts | 784 family pairs |
| Original ColorBrewer/CARTO named count variants | 69 families |
| Invalid or uninspected palette entries | 0 |

The 25 ordered near matches include 23 Radix neutral ramp pairs, one CARTO pair,
and one Nice Color Palettes pair. The Radix palettes are deliberately separate
neutral color tokens with different hue temperatures, such as gray, olive, sage,
sand and slate. A numeric near match does not justify deleting those tokens.

The CARTO pair is `color-wave-cartocolor-tealrose-2` and
`color-wave-cartocolor-temps-2`: the first color is `#009392` in both; the second
is `#d0587e` versus `#cf597e`. Their mean worst-background distance is about
0.12335 and maximum is 0.24670.

`nice-colors-0141` / `nice-colors-0494` preserves color order, with mean distance
0.98461 and maximum 1.34532. `nice-colors-0192` / `nice-colors-0378` has nearly
the same colors in reverse order, with mean 0.15453 and maximum 0.27160.
All confirmed pairs, their original values and per-color distances are present
in `data/duplicate-audit/palette.json`; no top-N cut was applied.

## Numeric method and interpretation

Each HEX value is normalized to eight-digit RGBA. Case, shorthand and explicit
opaque `ff` notation can change without changing a color; alpha and color order
are retained. Exact multiset comparison includes repeated swatches, rather than
treating the array as a set that discards multiplicity.

Near comparison composites every color over both opaque black and opaque white
in encoded sRGB, then converts those composites to OKLab. The distance is
Euclidean OKLab multiplied by 100. **It is not CIE DeltaE2000**, and the audit
does not claim a universal human just-noticeable difference threshold.

For a matched pair of swatches the distance is the larger of the black- and
white-background distances. A palette pair passes only when the average of
these distances is at most 1.0 and no swatch distance exceeds 2.0. Decisions use
unrounded double precision values. Alpha-only representations that resemble an
opaque color on one background must also pass on the other background.

Every same-count pair is considered. An average-color displacement bound safely
rejects pairs that cannot pass any one-to-one matching; remaining pairs are
tested in original and reversed order. For unordered candidates, symmetric
nearest-color bounds are followed by an exact Hungarian minimum-sum assignment,
with edges exceeding the per-color limit forbidden. Every retained relation
includes the matching right-array indices.

Near findings remain individual pairs. A-B and B-C similarity is never collapsed
into a purported A-B-C duplicate group when A-C fails. Different-count arrays
are checked for exact multiset containment and the original author's named
count variants. They are not interpolated, resampled or classified as duplicates.

The strict criteria intentionally miss broader stylistic similarities. This is
an exhaustive application of the stated numeric and containment criteria, not
a claim that every possible human perception of similarity was eliminated.

## Supplemental static gradient comparison

`data/duplicate-audit/color-representations.json` compares all 2,446 palette
arrays with 382 actual static CSS gradient arrays: 2,828 items and 3,997,378
pairs. The report retains findings only when at least one CSS gradient is
involved. It preserves each original kind, representation role, color values,
source URL, code hash, and the exact stored CSS, including its direction and
stop positions.

Five gradient pairs have the same ordered colors and the same CSS body:

- `uigradients-0010` / `uigradients-0020`
- `uigradients-0012` / `uigradients-0021`
- `uigradients-0034` / `uigradients-0343`
- `uigradients-0155` / `uigradients-0344`
- `uigradients-0216` / `uigradients-0345`

These are also covered by the CSS source audit and must not be counted twice.
There are no additional strict near color pairs involving a gradient. Sixteen
exact color containment relations are reported as families. Some connect a
two-color gradient with two of the colors in a larger palette; these have
different roles and remain related representations.

Equal color arrays alone do not establish equal gradient rendering: direction,
stop positions, repeating geometry and representation role matter. One CSS
motion asset labeled `gradient` but rendered by the CSS motion renderer is
outside this static gradient supplement and remains within the CSS audit.

## Reproduction

```powershell
python scripts/duplicate_audit_palette.py
python scripts/duplicate_audit_palette.py --include-gradients
python -m unittest tests.test_duplicate_audit_palette -v
```

All commands operate on local stored data without executing upstream code or
requesting a network connection. The 11 regression tests cover RGBA/HEX
normalization, alpha over both backgrounds, reversed and permuted order,
multiset multiplicity, exact assignment, non-transitive near chains, malformed
colors, bounded palette sizes, and preservation of CSS direction/original kind.
Outputs are deterministic UTF-8/LF JSON written through an atomic replacement.
