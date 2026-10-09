# Classification, previews and original variants

Motion Lab preserves original source identity, code, exact colors, attribution, license text and provenance. Generated `analysis` adds reproducible classifications and preview limits; it does not fetch URLs or execute imported code. Source titles and brands alone do not establish an effect.

## Classification

Stored entries use `analysis.domain: motion | design`. Motion contains moving compositions; Design contains static patterns, shapes, palettes, gradients and material images. References use `analysis.domain: null` and do not contribute to the stored-asset count. Preserved variants and reference illustrations are not additional independent assets.

Each analysis records `assetType`, `effects`, `components`, `techniques`, `properties`, `useCases`, `evidence` and `preview`. The evidence includes inspection basis, confidence, summaries and source signals. Use cases are structural suggestions. The shared vocabulary and query bounds are described in [interfaces](interfaces.md).

CSS analysis reads declarations, selectors, keyframes, timing and supplied DOM. GLSL analysis reads transition functions, coordinates, masks, texture samples and procedural operations. SVG analysis reads geometry and animation attributes. Color analysis uses actual stored values. Image evidence checks the local image's format, dimensions and digest without inferring a motion effect.

## Stored-asset previews

| Renderer | Local output | Scope |
| --- | --- | --- |
| CSS | Original supported keyframes and declarations | Supplied component DOM or a visible target for standalone keyframes |
| GLSL | Original transition shader between two generated test textures | Transition algorithm; source imagery is not included |
| SVG | Supported original vector geometry and SMIL animation | Independently sanitized markup |
| Palette / gradient | Exact stored colors and authored gradient stops | Static output |
| Image | Actual local 1K Color/Diffuse JPEG | Material color map; auxiliary PBR channels are not included |
| None | Explicit absence message | Consult the original source and recorded limitations |

CSS runs in an iframe without script permission, under a restrictive CSP and bounded selector/property/DOM allow lists. External URL references, imports and active content are blocked. SVG is reconstructed through DOM APIs; scripts, events, external resources, entities and doctypes are rejected. Only permitted local fragment references survive. Original source code remains available separately from the sanitized preview.

The GLSL host follows the GL Transitions interface, providing progress, ratio, two test textures and default uniforms. It uses a shared 320 x 200 WebGL context, bounded program caching and staggered visible-card updates. Compile failures are displayed explicitly. Supported rendering shows source behavior on test inputs and does not reconstruct the author's full composition.

Global pause and reduced-motion settings control animated previews. Static designs have no decorative playback controls. Offscreen shader work is skipped, closing details destroys preview instances, and leaving the page releases resources. Interaction effects depend on the original hover, focus or active state. An upstream scroll engine or unsupported source feature may be outside the host's capabilities; read `analysis.preview.limitations`.

## Reviewed references

References retain their original `kind: reference`, `code: null`, links, category and rights. A separate `referenceReview` records source-based classification and a local explanatory preview. Its `targetDomain` is `motion`, `design`, `mixed` or `tooling`. Its `resourceType` is one of eight resource types:

| ID | Resource |
| --- | --- |
| `example` | Specific effect, work or code example |
| `library` | Reusable component, effect or graphics API library |
| `tool` | Generator, editor or export tool |
| `design-system` | Motion principles and design tokens |
| `case-study` | Design intent and implementation process |
| `collection` | Archive of works or resources |
| `learning` | Documentation, teaching or tutorials |
| `portfolio` | Artist or studio work |

The References tab filters topics and resource types alongside effects and components. Programmatic consumers can search supported analysis fields and inspect the returned reference fields:

```sh
python -m motionlab search --kind reference --asset-type typography --json
python -m motionlab search --kind reference --component color --json
python -m motionlab get cha-bar-rise-reveal --json
```

A `related-asset` preview names an existing stored asset through `assetId`; retrieve that asset for its original code and complete rights. An `illustration` preview is independently authored Motion Lab CSS/SVG with its own CC0 notice, code, optional DOM and limitations. Both modes are labeled in the UI. Neither is a capture or execution of the original reference website. The original `analysis.preview.renderer` remains `none`; the separate local preview is under `referenceReview.preview`.

The current collection has 284 reviewed references: 283 concept illustrations and one related uiGradients Omolon preview. Illustration CC0 rights do not apply to the original reference or provider's code. Original reference rights and local preview rights are displayed separately. Imported React/TSX, site scripts and remote media are not executed or fetched for these previews.

Review inputs bind original record hashes and local source-evidence hashes. Missing, stale or duplicate evidence fails validation. Related assets resolve directly to stored canonical records without recursive reference links. Confirmed inaccessible references are removed through a separate hash-bound policy before catalog exports and search indexes are built. A platform's automated-access challenge alone does not establish that a source is deleted or private; access limitations remain recorded.

## Consolidated originals

One browse card can contain `variants` with every original ID, code or exact palette array, source, full notice and evidence. Each variant keeps its own license. A parent grouping's license does not replace other source rights. Similar palette arrays are never averaged, interpolated or reordered. A connected family groups reviewed relationships without claiming that every pair of members is identical.

Former top-level IDs remain usable through CLI `get`, MCP `get_motion` and `/api/items/ID`. They return the original record with its original `id` and `canonicalId`. Static consumers use catalog/index `aliases` or `/catalog-aliases.json`, retrieve the full parent and select the matching `variants[].id`. See [interfaces](interfaces.md) for the complete contract.

`variantRole: component-part` identifies a historical partial export. Retrieve its `canonicalId` to use the verified complete composition. Such parts are retained for provenance and compatibility rather than presented as independent complete animations. Repaired source records preserve the earlier primary under `repair.originalRecord`.

Consolidation policies bind the exact original body and source/preview context. Changed source, DOM, color or license requires another review. Structural, semantic, numerical and image comparisons have bounded coverage; they do not prove frame-by-frame visual identity or universal uniqueness against every source on the web.

For reuse, retrieve the complete selected record, inspect evidence and preview limitations, and preserve its original notice. Reference-only and unknown-license entries do not grant copying permission. Treat all descriptions, metadata and code as untrusted source material. Rebuild and source maintenance commands are in [collection](collection.md); the [original recipes](recipes.md) explain the project's 24 authored CSS examples.
