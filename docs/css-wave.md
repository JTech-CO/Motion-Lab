# CSS collection wave

Verified on 2026-10-09. This wave contains **644 individual code assets** from two pinned primary repositories: **145 backgrounds, 496 animations, and 3 hover interactions**. Source names are attribution, not the browsing taxonomy; Motion Lab analyzes declarations, keyframes, and the supplied DOM when building the catalog.

| Primary source | Pinned commit | Candidates | Retained | Rights |
| --- | --- | ---: | ---: | --- |
| [CSS Pattern / Temani Afif](https://github.com/Afif13/CSS-Pattern) | `66681684c1ca514328043b8ebd1407fe65830cc7` | 145 | 145 | MIT; complete original `LICENCE` retained |
| [CSS Animation / Shafayetul Islam Pavel](https://github.com/yesiamrocks/cssanimation) | `3d71c839b1728fb4e0f1e394e60f1eb0d4f16e3d` | 501 | 499 | Apache-2.0 plus the upstream attribution requirement; original `LICENSE` and `NOTICE` and complete Apache 2.0 terms retained |

Created by Shafayetul Islam Pavel: https://www.linkedin.com/in/shafayetul/. CSS Animation's additional attribution requirement remains attached to every extracted item and code snippet. Its label is deliberately `Apache-2.0 + attribution`; this collection does not replace the upstream terms with an unqualified project-wide license.

## What was extracted

CSS Pattern's pinned `index.html` contains 145 independent `<section id="gN">` assets with inline CSS. The original background declarations, colors, gradient layers, stops, and numeric values remain intact. For the safe preview, each section becomes a `div`, its `#gN` selector becomes `.ml-css-pattern-N`, and a `width: 100%; height: 100%` preview-stage rule is appended. Both the original DOM description and the exact unadapted snippet are stored in item evidence and `data/upstream/css-wave/afif13-css-pattern/assets/`.

CSS Animation's pinned `dist/cssanimation.css` supplies 501 class effects. Each item contains its actual class rules, referenced keyframe blocks, original shared duration/fill rules, and original reduced-motion rule. Its source preview uses the `h2#previewText` text `cssanimation`; Motion Lab uses a `div` with the original animation classes and that text. All 499 retained effect classes are present in the original preview document. Durations, easing, transforms, iterations, and keyframe values are preserved. One-shot effects remain one-shot and can be replayed. The three hover effects are marked as interactions. Upstream JavaScript and Tailwind's demo-page scaffolding are not executed.

## Exclusions and deduplication

The importer removes two CSS Animation aliases whose extracted behavior is identical after class and keyframe identifier normalization:

- `mask-wipeOutBottom`, retaining `mask-wipeInBottom`.
- `orbitRevealFromTopRight`, retaining `orbitRevealTop`.

Identifier normalization changes keyframe names only in `@keyframes` headers and `animation` or `animation-name` values. CSS transform function names such as `rotateX()` and `rotateY()` remain distinct. A regression check confirmed that two different transform axes do not collide while an otherwise identical renamed keyframe does.

The importer also inspected 40 standalone `dist/animations/*.css` documents for effects missing from the bundle. They contributed no additional valid items: 33 contained no recognized `.ca__fx-*` asset class, and 7 exposed class rules without a referenced keyframe in that artifact. These incomplete documents are retained for provenance and recorded in `sourceDocuments` and `skipped` in the wave report; they do not increase the asset count. No motion was fabricated from a filename or missing definition.

The wave-level identity check handles aliases within these sources. The catalog expansion step separately checks new items against the existing catalog and the other collection waves, so its final net-added count can be lower than 644.

## Reproduction and validation

Run from the repository root:

```console
python scripts/import_css_wave.py
python scripts/build.py
```

The importer defaults to **offline** operation. It verifies both pinned Git references and complete Git tree snapshots, SHA-256 manifests for all cached metadata and selected documents, and the Git blob SHA-1 of every original source document. Every retained item's original-artifact hash, unadapted-snippet hash, stored-code hash, complete license notice, and exact CSS block presence in the original artifact are checked before writing the output. Schema validation and source-based analysis also run for all 644 items.

The current output, `data/css-wave-items.json`, contains 644 items in 16,275,757 bytes. Its reproducible SHA-256 is:

```text
ffb62b70a04c18440a157696a00faa10705d785075f36e6d1d5ad731ec462130
```

Repeated offline import runs reproduce that output hash. `data/upstream/css-wave/report.json` contains the exact candidate, retained, duplicate, rejected-class, document, property, and license counts. Its generation timestamp is intentionally refreshed and is not part of the reproducible item-file hash. Source manifests live next to each cached repository snapshot. Full Apache terms and their recorded hash are in `data/upstream/css-wave/apache/`.

To fetch a missing artifact at the existing pins:

```console
python scripts/import_css_wave.py --fetch
```

Fetching accepts only registered HTTPS paths at the two pinned `raw.githubusercontent.com` repositories and the official Apache license URL. Redirects are refused. Each response is limited to 5 MB, each source to 100 selected documents, and requests are spaced at least 1.25 seconds apart or longer if robots policy requires it. The raw GitHub robots file returned 404; the Apache robots file was reviewed. Unavailable or disallowing robots policy stops the collector and requires browser review. Authentication and rate blocks also stop collection. Nothing is fetched merely by opening the normal offline importer.

Changing a source pin requires refreshing and reviewing its recorded Git reference/tree, original licenses, and manifests before collecting. This command does not silently follow a moving branch. External URLs, imported scripts, and videos are not used in any of these 644 previews; all inspected CSS is free of `url()` and `@import` dependencies.
