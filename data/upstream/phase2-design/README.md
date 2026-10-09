# Phase 2 static design collection

These are original design resources, separate from playable motion effects. The
importer does not turn static SVG files into artificial rotating-box animations.

Rebuild the reviewed collection offline:

```powershell
python -m pip install Pillow==12.0.0 fonttools==4.60.1
python scripts/import_phase2_design.py --offline
python -m unittest discover -s tests -p test_phase2_design.py -v
```

Pillow and fontTools are required only for the importer's geometry qualification.
The website, CLI, API and MCP continue to read their stored JSON/SVG without those
libraries. Upstream TypeScript, JavaScript, Python and R are parsed as bounded
data and never evaluated, imported or executed.

`manifest.json` pins each original author's Git commit, archive SHA-256, individual
artifact SHA-256, exact path and full source notice. The Hero Patterns bundle is
first-party content pinned by a reviewed SHA-256, with its first-party license
page and complete CC BY 4.0 legal text saved alongside it. `--fetch` accepts only
those registered revisions/content hashes; it does not follow moving branches.
Responses, archive expansion, regular member paths and request rates are bounded.
An access block, unavailable robots policy, changed source hash or changed
inventory stops collection instead of switching endpoints. A robots.txt response
of 404 or 410 is recorded as an absent policy; other policy-fetch errors stop.

`baseline-comparison.json` is a compact comparison snapshot of all 6,108 original
catalog identities plus three repaired complete primary bodies. Its manifest
records the original catalog and snapshot SHA-256 so that later catalog expansion
cannot accidentally treat these new resources as the original baseline.

`motion-comparison.json` and its manifest separately pin the 167 animated SVG
records from the final 510-item motion input. They take priority over static design
concepts. A same-concept static icon is excluded even when another publisher uses
a different drawing style. Complex local-symbol compositions are still covered
by semantic grouping; unresolved contour comparisons are listed explicitly in
the report rather than reported as successful geometric comparisons.

The qualification report includes every rejected candidate and retained match:

* One static icon per semantic concept. Existing animated concepts are preferred.
  Synonyms, weight, fill, direction, small status symbols and numbered variations
  are conservatively grouped before any new card is counted.
* Exact drawable geometry and sampled contour masks are compared against the
  existing original SVGs and every accepted new SVG. Paint and stroke weights are
  normalized; eight rotation/reflection orientations are tested. Contour Jaccard
  similarity of at least 0.90 causes exclusion. Complex transforms or masks that
  the collector cannot faithfully compare are deferred rather than approximated.
* The 87 Hero Patterns are extracted as exact individual SVG literals. Simple
  dot, stripe, checker and grid concepts already represented by the existing CSS
  pattern library are excluded.
* Coolshapes stores the original literal silhouettes as standalone SVGs. Optional
  React runtime, gradient and grain treatments are explicitly omitted from these
  geometry assets. Complex nonliteral compositions are deferred.
* Every continuous scientific map remains a single gradient with all authored RGB samples.
  Full source precision and arrays are preserved; no 256-color map is split into
  artificial cards or truncated to the catalog's 32-swatch field. Every original
  palette/gradient array, including consolidated originals and alpha, is compared
  using a common 64-sample path over both black and white. Ordered and reversed
  paths with mean Euclidean OKLab distance at most 1 and maximum at most 2 are
  excluded. Same-size discrete palettes also use a Hungarian color-set match.
  Categorical Glasbey color sets remain a single 256-swatch grid rather than a
  fabricated continuous map. Glasbey starting-palette/chroma variations are one
  source family. Wes Anderson's discrete palettes use complete swatch bars.

This is a conservative structural and semantic filter, not a proof that every
possible human interpretation of similarity has been eliminated. The root build
performs a further cross-wave comparison before publishing these candidates.
Counts describe static design resources and never independent motion mechanisms.

The full original source notices are retained per asset. Author repository and
immutable per-file links are included in each record's provenance. MIT, ISC/MIT
and CC BY terms apply to their respective upstream sources; no new blanket
license replaces those terms.

`product-renderer-qa.json` records the current input, published catalog, preview
renderer and QA harness hashes. The owned `tests/phase2-design-qa.html` and `.js`
exercise the site's actual `MotionPreview.create` renderer for every published
`design-*` SVG with `?all=1`, comparing readiness and every authored SVG tag count.
`visual-qa.html`, `.png` and `.json` also preserve six representative source-only
renders. Coolshapes previews deliberately show qualified silhouette geometry;
upstream optional grain, gradients and React runtime are not previewed.
