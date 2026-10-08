# Vector and CSS collection wave

Verified on 2026-10-09. This wave stores **1,857 individual code assets**: 1,260 animated SVGs and 597 source-authored CSS effects. No video, generated color variants, icon frame exports, or reference-only records are counted.

| Source | Pinned revision | Original candidates | Imported | Excluded |
| --- | --- | ---: | ---: | ---: |
| [SDS Motion Forge](https://github.com/salkomdesignstudio/SDS-Motion-Forge/tree/e10005175c50a9b2a6bc757539b6fd9e30e8e53a) | `e10005175c50a9b2a6bc757539b6fd9e30e8e53a` | 604 registered effects | 597 | 6 declared aliases; 1 incomplete effect |
| [SVG Spinners](https://github.com/n3r4zzurr0/svg-spinners/tree/abfa05c49acf005b8b1e0ef8eb25a67a7057eb20/svg-smil) | `abfa05c49acf005b8b1e0ef8eb25a67a7057eb20` | 46 canonical SMIL files | 46 | 0 |
| [Material Line Icons / Line MD](https://github.com/cyberalien/line-md/tree/2ed22555cee9c1e50d4269865681d01ee8cffd7c/svg) | `2ed22555cee9c1e50d4269865681d01ee8cffd7c` | 1,222 canonical SVG files | 1,214 | 2 static files; 6 byte-identical duplicates |

SDS categories are 103 typography effects, 100 buttons, 99 inputs, 97 cards, 99 loaders, and 99 scroll transitions. The SVG records are classified from their actual animation elements and changed attributes. Line MD's `svg-static`, `svg-style`, preview pages, and rendered frames were not collected as additional assets.

## Provenance and permissions

The original files are preserved under `data/upstream/vector-wave/`. The manifest registers **1,277 original artifacts**: seven SDS source files, 46 spinner SVGs plus their license, and 1,222 Line MD SVGs plus their license. It records immutable URLs, original sizes, SHA-256 hashes, and the SVG Git blob IDs. The canonical Line MD files were compared with the actual pinned Git objects before the temporary checkout was removed. Its 1,222 paths correspond to 1,216 distinct Git blobs because six paths contain duplicate bytes.

All three sources have complete MIT notices verified at their pinned revisions. This does not change the licenses of other Motion Lab sources. Each imported item retains its source-specific `licenseText` and `licenseUrl`.

| Source | Copyright notice | Original license SHA-256 |
| --- | --- | --- |
| SDS Motion Forge | Copyright (c) 2025 Salkom Design Studio | `f352b0c58afe20318340f856a5328ba3607a94f2d4601dd64eb42fba9616a2b8` |
| SVG Spinners | Copyright (c) Utkarsh Verma | `712f8f614e9a23cc754a21d72ea443f1166077e4ee0e6c3b6f9fa576a6d37254` |
| Line MD | Copyright 2020 Vjacheslav Trushkin | `2b88bafca347c6a12c33612fa51c5efbdd00c2753ed67fc474d7a6af9c61e430` |

GitHub API and raw-content robots requests returned 404 and are recorded as absent policies. The checked GitHub robots document and its digest are retained in the probes directory. Registered raw requests use HTTPS, a single worker, at most 48 requests per minute, a 25-second timeout, and a 2 MiB response limit. Access or rate blocks stop collection. Source JavaScript and package scripts are never executed.

## Extraction and exclusions

SVG `code` contains the exact original UTF-8 file. The complete license is a separate field so an original XML declaration remains first. At least one actual `animate`, `animateTransform`, or `animateMotion` element is required. Each file is bounded to 128 KiB and 700 XML elements; doctypes and entities are rejected. Original byte duplicates are removed per source and recorded with their retained path.

SDS CSS is parsed with balanced braces, strings, and comments. Each effect retains its original selector rules, required keyframes, original `:root` tokens, and original cascade order. Enclosing media headers are reconstructed and the full MIT notice is prepended. `sourceRanges` identify the exact slices in the archived `dist/motion.css`; the stored code has its own hash. The original docs-data JavaScript wrapper is read as a standalone JSON assignment, never evaluated. Its source-authored HTML samples are parsed into bounded allowlisted DOM trees: at most 64 nodes, shallow nesting, class names, text, placeholders, and numeric custom variables. The actual largest sample has 18 nodes.

`sds-char-orbit` is excluded because the pinned upstream CSS references the missing `sds-charOrbitBob` keyframes. Its parent entry animation exists, but the complete child orbit effect cannot run as authored. No replacement animation was invented. The complete CSS, registry, missing dependency, and exclusion reason remain in the archive and report. Six registry-declared SDS aliases, two static Line MD files, and six identical Line MD files are also listed in `report.json`.

## Preview limits

The catalog preserves the original assets and source DOM. Motion Lab's preview host separately sanitizes and renders the supported CSS/SVG subset. Hover, focus, and active effects depend on those original interaction states. Input samples may be disabled by the host. SDS scroll playback can run on class application; automatic viewport triggering requires the optional upstream scroll engine, which is not imported or executed here. SVG masks, filters, `set`, SMIL timing, and inline transform styles require host support and may be omitted by an unsupported renderer. These are source assets, not video captures or promises that every browser reproduces every source feature.

## Offline reproduction

From the repository root:

```sh
python scripts/import_vector_wave.py --offline
```

This makes zero network requests, verifies the complete artifact path set and source identities, checks original sizes and SHA-256/Git blob hashes, validates all three full license notices and the preserved robots artifact, then regenerates `data/vector-wave-items.json` and the report. The archived source files and manifest are sufficient; no source Git checkout or upstream build is required. `--fetch` is a bounded initial collection mode, not a license bypass or an automatic update to a newer revision.

Audit evidence: all 1,260 stored SVG code bodies match their original artifact bytes; all 597 CSS records have bounded original source ranges and stored-code hashes; the output contains 1,857 unique IDs. Deliberately missing artifacts, duplicated source identities, changed digests, wrong artifact URLs, unsafe paths, and script-bearing source DOM were rejected. A second offline rebuild after checkout removal produced the same catalog SHA-256, `62ea9ca6271c6e7071e602beda817f5f1fee180dd2d133e239d674508ede7d82`. `report.json` alone receives a fresh rebuild timestamp.
