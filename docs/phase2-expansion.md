# Phase 2: verified motion and separate design assets

Motion Lab first qualifies playable motion sources, then expands static design
resources in a separate domain. A shape, pattern, color map or texture is not
counted as an animated effect. Reference links remain a third browsing scope
and do not contribute to the stored-asset target.

The authoritative counts are in `data/catalog.json` under `stats.storedAssets`,
`stats.domains` and `stats.kinds`. The starting point was 6,074 browse entries:
5,786 stored assets and 288 reference links. Preserved variants and repaired
source bodies are comparison inputs, not additional independent assets.

The final collection contains **10,001 stored assets**: 3,345 in Motion and
6,656 in Design. With the unchanged 288 references, there are 10,289 browse
entries from 163 source projects. This expansion adds 4,215 stored assets:

| Input | Accepted | Contents |
| --- | ---: | --- |
| Verified motion | 510 | 343 original CSS compositions and 167 animated SVGs |
| Static design | 3,157 | 2,956 shapes, 69 patterns, 110 gradients and 22 full categorical color maps |
| Materials | 494 | 342 ambientCG and 152 Poly Haven color/diffuse images |
| Supplemental shapes | 54 | Original Game Icons compositions from 191 reviewed candidates |

The final catalog contains 7,078 code records, 2,429 palette records and 494
images. Color-map SVGs count as code records while remaining in the Design
domain. The supplemental 54 shapes also remain in Design. Counts and final
validation bindings are recorded in `data/phase2-report.json`.

## Source qualification

| Source | Stored resource | Qualification |
| --- | --- | --- |
| [CSS Loaders](https://github.com/vineethtrv/css-loader) | Native CSS and original span/text composition | Exact program/DOM, timing/paint normalization and manual minor-geometry review |
| [Meteocons](https://github.com/basmilius/meteocons) | Original SVG geometry and SMIL animation | Animated sources only; local symbols and gradients preserved; paint/timing variants excluded |
| [Tabler](https://github.com/tabler/tabler-icons), [Lucide](https://github.com/lucide-icons/lucide), [Phosphor](https://github.com/phosphor-icons/core) | Static SVG shapes | One drawing style and one semantic concept; brands, direction, numeric and toggle variants collapsed across publishers |
| [Coolshapes](https://github.com/realvjy/coolshapes-react), [Hero Patterns](https://heropatterns.com/) | Static SVG silhouettes and repeating patterns | Literal shape geometry or authored patterns; full notices; optional Coolshapes grain, gradients and React runtime excluded |
| [Scientific colour maps](https://github.com/callumrollo/cmcrameri), [cmocean](https://github.com/matplotlib/cmocean), [Colorcet](https://github.com/holoviz/colorcet), [Wes Anderson](https://github.com/karthik/wesanderson) | Full authored color maps or swatch SVG | Perceptual comparison against prior colors; exact source RGB values and all samples retained |
| [ambientCG](https://ambientcg.com/), [Poly Haven](https://polyhaven.com/textures) | Actual 1K Color/Diffuse images | CC0 evidence, source hashes, conservative family grouping, decoded-image and stored-JPEG comparisons |
| [Game Icons](https://github.com/game-icons/icons) | Selected static SVG compositions | Pinned originals by Lorc and Delapouite; author attribution and full CC BY 3.0 terms; independent composition review before import |

Registered source revisions, archive hashes, individual artifact hashes and
complete author notices are saved in each `data/upstream/phase2-*` directory.
No upstream JavaScript, TypeScript, Python or R is executed. Unsupported p5.js
sketches and Paper Shaders are held rather than represented by invented motion
or an incompatible shader host. A repository license alone does not establish
that the existing preview host supports its code.

Collectors use official APIs or pinned public files, checked access policies,
serialized bounded requests and registered hosts. They stop on access denial,
rate limiting or changed pinned inputs. Browsers verify permitted previews;
they are not a mechanism for bypassing access restrictions.

## Duplicate and similarity checks

Motion and design importers compare against an immutable snapshot covering all
6,108 former source identities plus three repaired complete primary bodies.
This includes merged variants that no longer appear as separate cards. The
snapshot is hash bound so rebuilding after expansion cannot remove the new
inputs by treating them as their own baseline.

New static designs also compare against the newly qualified animated SVGs.
The animated source takes priority when both represent the same base concept.
Exact geometry and rendered contour comparisons supplement semantic grouping
where the geometry parser supports the full composition. Complex local-symbol
compositions receive semantic comparisons; deferred contour checks are listed
explicitly in the qualification report.

Supplemental game designs compare against the immutable original bodies and
all qualified new motion and design records. Independent visual review of
the original compositions rejects decorative variants of existing concepts
and admits one representative per concept. Reviewed decisions bind the exact
source-code hashes. The supplemental collector preserves original geometry,
colors and author attribution; these records remain static design assets.

Design qualification collapses publisher/style differences, directional and
numeric families, mirrored/rotated contours, aliases and known semantic
synonyms. Continuous color paths are compared in ordered and reversed OKLab
samples; categorical colors use assignment comparisons. These comparison
samples never replace the stored source arrays. A scientific map retains its
full authored stops, and Glasbey remains a categorical swatch grid.

Materials first collapse explicit resolution/channel variants and related
source families. Actual decoded color maps are compared with rotation/mirror
perceptual hashes, tonal quantiles, frequency distribution and edge structure.
The web JPEG is checked again after conversion, because a threshold boundary
can change during re-encoding. Flat or very similar low-contrast surfaces and
manually reviewed minor brick/ground variants do not increase the count.
Rejected originals are discarded after preserving URL, SHA-256, features and
the rejection decision; retained originals and their web images remain local.

`scripts/recheck_consolidation.py` inspects the final canonical catalog across
CSS, SVG, palettes, GLSL, references and images. Review decisions apply only
while both the exact code and source/preview context hashes match. It writes
`data/consolidation-recheck.json` without replacing the historical audit.

These checks describe specific structural, semantic, numerical and image
criteria. They do not prove universal perceptual uniqueness, compare every
animation frame or guarantee uniqueness against every resource on the web.

## Browsing and AI retrieval

The web library has separate Motion, Design and References tabs. Design exposes
pattern, shape, material, palette and gradient filters, using the same black,
white and Cyan interface. Arrow keys and Enter, mouse selection, Korean/English
and 20/50/100 entries per page remain available. A direct link can select
`library.html?domain=design`.

```sh
python -m motionlab search --domain motion --category loader --limit 12 --json
python -m motionlab search --domain design --asset-type pattern --limit 12 --json
python -m motionlab search --domain design --kind image --category material --limit 12 --json
```

HTTP and `search_motion` use the same `domain: motion | design` field. Static
exports include `/collections/domain-motion.json` and
`/collections/domain-design.json`. The compact index locates records; the full
record contains original code or a validated local image descriptor, evidence
and license. Image retrieval uses its relative `image.path` on the same server.
Material entries store the actual color map, not a PBR render, and do not claim
to include normal, roughness or displacement channels.

SVG previews retain supported source geometry and authored color stops. Hero
Patterns receives a light preview surface so its original black fill stays
visible. Static designs have no decorative playback controls. Material detail
shows the actual image, dimensions and download. Imported scripts, events,
external SVG resources and CSS network references remain blocked.

## Rebuild and verification

The website, build, SQLite search, CLI, HTTP and MCP use the Python standard
library. Additional packages are needed only for offline qualification and
image similarity rechecking:

```sh
python -m pip install -r scripts/phase2-requirements.txt
python scripts/import_phase2_motion.py --offline
python scripts/import_phase2_design.py --offline
python scripts/import_phase2_materials.py --offline
python scripts/import_phase2_game_design.py --offline
python scripts/build.py
python scripts/verify_catalog.py --minimum 10000 --minimum-stored 10000
python scripts/recheck_consolidation.py
python -m unittest discover -s tests -p "test_*.py"
node tests/variant-ui-check.js
```

`--minimum-stored` counts only code, color and image assets. References and
preserved variants cannot satisfy that target. With a temporary local server
running on port 8791, `python tests/phase2-interface-check.py` compares complete
qualified records and notices through separate CLI/MCP processes and HTTP.

The upstream reports record raw candidates, excluded variants, accepted inputs,
source and snapshot hashes, supported comparison coverage and browser checks.
`tests/phase2-design-qa.*` checks original gradient stops and categorical swatches
in the real renderer. `tests/preview-check.*` checks every qualified CSS/SVG
preview and sanitizer regressions. `tests/phase2-browser-check.js` runs local
Chrome keyboard, domain, pagination, language, image and mobile-width checks
against a temporary loopback server on port 8791. Browser test profiles and
transient served test pages are kept separate from the user's browsing profile.

Final validation passed with 166 Python tests, 19 actual-browser UI checks and
16 CLI/HTTP/MCP checks. The canonical duplicate recheck reports zero exact or
near groups, zero unreviewed candidates and zero errors under its stated
criteria. All 33 candidates have source/code/context-bound review decisions.
The original variant DOM model also passes with 20 families and 49 selectable
originals. Machine-readable evidence is in `data/phase2-report.json`.

Source renderer reports retain their actual tested catalog hashes. Motion,
design and all-CSS checks preceded the last 54 static shapes; their frozen
qualified inputs and renderer hashes still match the final distribution.
Final verification checks their complete canonical source fields again.
Supplemental shapes, UI and interfaces were checked against the final catalog.

A separate color-source preflight is saved under
`data/upstream/phase2-color-preflight/`. It admits zero additional assets.
Numerical novelty alone does not establish original attribution or license
coverage; unqualified provenance and palette-family decisions remain held.

No push, publication, account configuration or external AI-client settings are
performed by this expansion.

Generated full JSON and collection exports omit unnecessary whitespace while
preserving every field and source string. SQLite payloads use bounded standard
library compression; all interfaces return the same complete JSON records and
can still read older databases with text payloads. Source inputs remain readable
and uncompressed. This storage change does not alter motion, colors or licenses.
