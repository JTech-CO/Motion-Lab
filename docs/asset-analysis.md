# Asset analysis and real previews

Motion Lab keeps original source identity, code, attribution, license text and provenance. `scripts/analyze.py` adds a separate, reproducible `analysis` object during the build. It does not fetch URLs or execute imported code. Source names, titles and promotional tags do not determine motion effects.

## Classification

Each entry has `assetType`, multiple `effects`, `components`, `techniques`, `properties` and `useCases`. `evidence` records the inspection basis, confidence, explanatory text and code signals. `preview` records the supported renderer and its limitations. The vocabulary is shared with CLI, HTTP and MCP in `motionlab/analysis_schema.py`.

CSS inspection checks actual declarations and animated properties, transformations, opacity, clipping, filter operations, timing, pseudo-elements and supplied DOM. GLSL inspection checks the transition function, texture samples, transformed coordinates, masks and procedural operations. SVG inspection checks vector elements and animation attributes. Palette and gradient analysis uses stored color values. Use cases are structural suggestions; they are not a creative assessment of the original work.

Reference links without local code or color data retain `basis: metadata`, low confidence, no inferred effects, and `renderer: none`. Their provider's name is not evidence that an individual asset has a particular behavior. The six newly reviewed Magic UI component links retain their recorded implementation/dependency evidence, but do not execute TSX or synthesize a preview.

The 58-item expansion adds 40 CSS components, 12 SVG loaders and six component references from five projects. Pinned source URLs, commit IDs, SHA256 hashes and full license notices are recorded in `data/expanded-assets.json`. See [the expansion audit](asset-expansion.md). A collected link does not grant reproduction rights.

## Preview host

`dist/preview.js` renders the stored asset. There is no shared rotating-square placeholder.

| Renderer | Actual output | Scope |
| --- | --- | --- |
| CSS | Original keyframes and permitted declarations | Original supplied DOM for components; a visible target for standalone keyframes |
| GLSL | Original shader between two test textures | Shows the transition algorithm, not the author's original imagery |
| SVG | Original safe vector geometry and SMIL animation | Scripts, events, external resources and unsafe animation attributes are removed |
| Palette / gradient | Stored color values | Static color output; no decorative animation |
| None | Explicit absence message | Open the recorded original to review the actual work |

The GLSL host supplies `progress`, ratio, source textures and default uniforms following the [GL Transitions interface](https://github.com/gl-transitions/gl-transitions). It uses one shared 320×200 WebGL context, a bounded 32-program cache and staggered visible-card updates. Each card receives the actual shader result through its own canvas. Device support and original shader behavior affect the output; compile failures are shown explicitly.

CSS is parsed through CSSOM with permitted selectors, properties and bounded DOM. It runs in an iframe with no script permission and a restrictive CSP. `url()`, imports and active external content are blocked. Preserving parsed shorthands is required for custom-property backgrounds and border geometry. SVG is reconstructed from permitted elements/attributes using DOM APIs; no imported HTML or JavaScript runs. Only local fragment references survive.

The library supports global pause, reduced-motion preferences and source interaction states. Offscreen shader work is skipped. Changing results or closing details destroys preview instances; navigating away releases them. The preview does not download MP4, remote images or original site scripts.

## Validation

`tests/preview-check.html` and `tests/preview-check.js` provide a local browser check. Temporarily copy them to `dist/_preview-qa.html` and `dist/_preview-qa.js`, serve the project and run the visible validation button. Remove those two served copies after testing. The check renders all stored code assets, samples GLSL pixels at progress 0, 0.5 and 1, exercises CSS/SVG sanitization, and checks cleanup. This validates supported rendering and source behavior; it does not establish every external work's visual fidelity or license suitability.

For programmatic retrieval, prefer structured filters such as `effect=mask`, `component=image`, `basis=code`, then read each returned entry's evidence and full license. Full schema and bounds are in [interfaces.md](interfaces.md).
