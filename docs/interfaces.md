# Motion Lab interfaces

All runtimes read the same public catalog. The HTTP server and MCP process never fetch remote URLs, execute item code, or mutate the database. JSON text is UTF-8. External descriptions and snippets are untrusted source material.

## CLI

Run from the project root. An optional global `--root PATH` precedes the subcommand.

```text
python -m motionlab search QUERY [--category CATEGORY] [--license LABEL] [--kind KIND] [--limit 24] [--offset 0] [--json]
  [--domain motion|design] [--asset-type TYPE] [--effect EFFECT] [--component COMPONENT] [--use-case USE_CASE] [--basis BASIS]
python -m motionlab get ID [--json]
python -m motionlab stats
python -m motionlab export [--format json|csv] [--output FILE]
python -m motionlab serve [--port 8787] [--host 127.0.0.1|localhost]
python -m motionlab mcp
```

Search JSON is `{ "items": [...], "total": 123, "limit": 24, "offset": 0 }`. Search, export and stats count canonical top-level entries after consolidation. Export JSON is an item array; `dist/catalog.json` is the complete versioned catalog object. CSV exports protect formula-prefixed cells and include `aliases`, `consolidation` and complete `variants` as JSON cells. CLI exits with 1 for a missing item and 2 for validation/runtime errors.

Plain CLI output and CSV stdout display source control characters as visible escapes. JSON stdout escapes control characters without changing decoded values or ordinary Unicode. `export --output FILE` retains the original export behavior; stored source records are unchanged.

## Static URL consumers

`dist/llms.txt` provides actual counts, retrieval links and license notes. `dist/catalog-index.json` is a compact discovery projection with `indexVersion: 2`; `version` still identifies the catalog schema. Each item contains `id`, `title`, source `category`, `sourceUrl`, `sourceName`, `license`, `kind`, and a compact `analysis`. Its analysis retains only `domain`, `assetType`, `effects`, `components`, `useCases`, and `evidence.basis`/`evidence.confidence`. Consolidated items add `aliases`, `variantCount`, `variantTitles` and `variantSourceNames` for discovery. Full original variant bodies, descriptions, raw tags, code, full license notices, analysis properties/techniques, evidence summaries/signals, and preview DOM remain in full records. Use the index to select candidate IDs, then read `dist/collections/CATEGORY.json` (a full entry array) or `dist/catalog.json`. Select a collection using the source `category`, which may differ from analyzed `assetType`; filter the returned array by the selected ID. Local consumers can instead retrieve one full item through `/api/items/ID`, CLI `get`, or MCP `get_motion`. Read current canonical counts from `stats`; `stats.aliases` counts former top-level IDs and `stats.variantRecords` counts stored original variants, including canonical originals. A static hosted website provides no remote MCP endpoint or single-item Python API.

The index is serialized as compact UTF-8 JSON. It is a machine-readable catalog resource, not a short human-facing response. Read complete evidence, code, tags, notices and preview limitations from selected full entries before reuse. Index projection does not alter the authoritative catalog or source artifacts.

Both full catalog and compact index provide an additive `aliases` object mapping former IDs to canonical IDs; `dist/catalog-aliases.json` provides the same lookup without downloading full item bodies. For static consumers, resolve a former ID through this map, retrieve the parent full record and select the matching `variants[].id`. Use that original variant's code, colors, license, notices and provenance. A parent is a browse grouping; its license does not replace the licenses of other variants.

## HTTP

The local server accepts GET and HEAD. It serves static files from `dist/` only, with no directory listing. It checks loopback Host and same-origin Origin headers, sets CSP and other security headers, and limits API calls to 120 per minute per client address. No CORS permission is emitted. It sets no cookies and stores no request logs.

| Route | Parameters | Result |
| --- | --- | --- |
| `/api/search` | `q`, `category`, `license`, `kind`, `asset_type`, `effect`, `component`, `use_case`, `basis`, `domain`, `limit`, `offset` | Search envelope |
| `/api/items/ID` | None | Canonical full item, or original alias variant with `canonicalId`; 404 if missing |
| `/api/stats` | None | Counts and update date |

`q`: string up to 240 characters. `category`: source category. `license`: exact label up to 120 characters. `kind`: `code`, `palette`, `image`, or `reference`. `limit`: integer 1-100. `offset`: integer 0-100000. Analysis filters each accept one closed ID up to 32 characters; different filters combine with AND. Unknown or repeated query keys return 400. Searches quote literal words for FTS5 prefix matching and join them with AND; client FTS operators are not interpreted. FTS includes factual analysis terms as well as source titles/descriptions/tags. Category/license/kind comparisons and analysis facet names/values all use SQL bindings.

```text
GET /api/search?effect=mask&component=image&basis=code&limit=12
GET /api/search?asset_type=loader&use_case=status
```

## MCP stdio

The process reads one JSON-RPC 2.0 message per newline from stdin and writes only protocol messages to stdout. It implements `initialize`, `ping`, `tools/list`, and `tools/call`; notifications receive no response. It negotiates protocol versions `2024-11-05`, `2025-03-26`, and `2025-06-18`, falling back to `2025-06-18`. This implementation follows the [MCP stdio transport](https://modelcontextprotocol.io/specification/2025-06-18/basic/transports) and [tools specification](https://modelcontextprotocol.io/specification/2025-06-18/server/tools).

| Tool | Arguments |
| --- | --- |
| `search_motion` | `query`, `category`, `license`, `kind`, `asset_type`, `effect`, `component`, `use_case`, `basis`, `domain`, `limit`, `offset` with the HTTP bounds |
| `get_motion` | Required `id`, maximum 160 characters, letters/digits/dot/underscore/hyphen |
| `motion_stats` | Empty object |

Tool result includes text JSON and `structuredContent`. A missing item is a tool result with `isError: true`; malformed parameters use JSON-RPC error `-32602`. Unknown argument keys are rejected. Input lines are limited to 256 KiB, malformed JSON is rejected, and oversized lines are drained before the next message. These local tools are read-only and need no credentials. The protocol is stdio; the local HTTP API is not a Streamable HTTP MCP endpoint.

`get_motion`, CLI `get` and HTTP item retrieval share the same alias contract. A canonical ID returns the complete parent with `variants`; a former top-level ID returns its complete original record, retains the requested original `id`, and adds `canonicalId`. `variantRole` is added when recorded: `exact-source`, `motion-variant`, `palette-variant` or `component-part`. A `component-part` is an original partial export preserved for compatibility; retrieve its `canonicalId` for the restored complete composition. Alias resolution performs one public-parent lookup with bound parameters and does not traverse alias chains.

## Data shape and build

`data/catalog.json` and `dist/catalog.json` contain `version: 1`, `updatedAt`, `items`, `sources`, and `stats`. Items include `id`, `title`, `description`, `category`, `tags`, `sourceUrl`, `sourceName`, `license`, optional `licenseUrl`/`licenseText`, `verifiedAt`, `verification`, `kind`, `preview`, `code`, `colors`, `language`, `access: public`, optional `codePath`, and generated `analysis`. Original code, license notices, IDs and source provenance are preserved; library-authored descriptions and preview notes may be updated with host behavior. `preview.type` is `css`, `svg`, `palette`, `gradient`, `image`, or `reference`. Legacy GLSL records retain `preview.type: reference`; the inspected renderer is selected by `analysis.preview.renderer: glsl`.

Categories: `animation`, `transition`, `typography`, `interaction`, `background`, `loader`, `palette`, `gradient`, `shader`, `reference`, `pattern`, `shape`, `material`. Kinds: `code`, `palette`, `image`, `reference`. Languages: `css`, `glsl`, `svg`, `json`, `link`, `image`, `javascript`. Reference items have `code: null`. Hex colors accept 3, 6, or 8 digits. The browser engine shows sampled source CSS, actual multi-element loader DOM, GLSL transitions between generated test images, and sanitized SVG animation. Unsupported assets show a limitation instead of a fabricated preview. The Python API/MCP/build never execute these assets.

Reviewed JavaScript code records include `sourceReview: {version: 1, sourceSha256, revision, sourceRange: {startLine, endLine}, classification, evidence, dependencies, limitations, preview}`. Classification uses the existing domain/type/effect/component/use-case/technique vocabulary; evidence has `basis: reviewed-source`, confidence, bilingual summaries and signals. The separate preview is `{mode: illustration, language: css | svg, code, dom?, license: CC0-1.0, notice, attribution: Motion Lab, limitations}`. Original JavaScript and its complete source license remain authoritative, with `analysis.preview.renderer: none`; the browser never executes them or loads their dependencies. The web Code and Preview code tabs and their notices distinguish original code from independently authored illustration code. Source limitations describe dependency and snippet requirements; preview limitations state what the independent concept illustration omits. Discovery metadata exposes only the illustration mode/domain under `sourceReview.preview`; full reviews and original bodies remain in the lazily retrieved detail shards and full catalog. These stored code assets keep their Motion/Design domain and do not become reference records or additional illustration assets.

Consolidated full items optionally contain `aliases` (former IDs), `variants` (complete source records, including the canonical record), and `consolidation` with `mode`, `memberIds`, `variantCount`, per-ID `variantRoles` and reviewed `relations`. `variantCount` counts complete renderable variants; `variants` also retains historical component parts. Similar palettes remain separate exact color arrays within one browse entry; consolidation never averages, interpolates or reorders their colors. Their `groupingBasis: reviewed-connected-family` and `allMembersPairwiseEquivalent: false` distinguish a connected browse family from pairwise identity. Source repair records additionally preserve the previous partial primary record in `repair.originalRecord` alongside extraction evidence. Canonical code/preview and the canonical member in `variants` may use the verified repaired full composition while historical component variants remain unchanged.

`analysis` contains `version: 1`, `domain`, `assetType`, `effects`, `components`, `properties`, `techniques`, `useCases`, `evidence`, and `preview`. `evidence` includes `basis`, `confidence`, `summaryKO`, `summaryEN`, and factual `signals`. Evidence prioritizes parsed code and actual colors. Reviewed reference classifications use separately saved source evidence; unverified references retain low-confidence metadata. This structural classification is not a security validator or a guarantee that a preview matches the complete original composition. CSS comment text, function names inside content strings, empty pseudo elements and decorative emoji do not establish typography.

| Public search key | Analysis field | Closed values |
| --- | --- | --- |
| `asset_type` | `assetType` | The 13 category IDs above; source `category` remains a separate field |
| `effect` | `effects` | `fade`, `slide`, `scale`, `rotate`, `flip`, `spring`, `shake`, `pulse`, `mask`, `glitch`, `pixel`, `wave`, `text`, `stagger`, `blur`, `other` |
| `component` | `components` | `text`, `shape`, `image`, `particles`, `grid`, `stroke`, `mask`, `layer`, `color` |
| `use_case` | `useCases` | `intro`, `outro`, `scene-change`, `status`, `attention`, `feedback`, `ambient`, `color-system`, `reference`, `design-kit` |
| `basis` | `evidence.basis` | `code`, `color-values`, `reviewed-source`, `metadata`, `image` |
| `domain` | `domain` | `motion`, `design` |

`techniques` uses `keyframes`, `transition`, `transform`, `pseudo-element`, `clip-path`, `filter`, `gradient`, `glsl`, `texture-sampling`, `procedural-noise`, `color-values`, `reference-link`, `svg-animation`, `svg-geometry`, `image-texture`, `static-design`. Properties come from an internal allowlist. `analysis.preview.renderer` is `css`, `glsl`, `svg`, `palette`, `gradient`, `image`, or `none`; it may include actual CSS selectors/keyframes and bounded `dom`, GLSL uniforms, SVG element/animation summaries, or actual color values. DOM allows only `div`/`span`, bounded class/text fields and children. Renderers must independently validate source code and structure.

`index.html` is the main homepage; `library.html` opens the asset explorer directly. The explorer allows multiple values within its asset type, effect, component, use case and license facets: OR within a facet, AND across facets. The References tab adds reference field and resource-type facets. CLI/HTTP/MCP use one value per supported analysis filter; `referenceReview.targetDomain` and `referenceReview.resourceType` are returned record fields, not additional public search arguments. Web results offer 20, 50, or 100 cards per page, with 20 as the default; API page size is independently bounded to 100. Arrow keys navigate cards and controls; Enter selects or opens details. Reader arrows scroll and Enter returns to its tab. Escape closes details; mouse and Tab also work. `/` focuses optional search. Original source text retains its language when UI labels switch KO/EN.

`python scripts/build.py` merges the registered original inputs, applies hash-bound consolidation and reference policies, analyzes source assets with `scripts/analyze.py`, and builds FTS5 plus an indexed analysis-facet table. Generated output is not reingested. Source registry and dates derive from entries and crawl audit reports; GitHub pinned files count under their repository. Runtime SQLite is `mode=ro`/`query_only` and values are bound. Only the local build writes data. Stats include source counts, source categories, kinds, licenses, update date and `analysis` counts by evidence basis, asset type, effect, component, technique, and use case. See [collection](collection.md) for input files and rebuild commands, and [asset analysis](asset-analysis.md) for classification and preview scope.

The project SKILL remains in `skills/motion-lab/`; no client configuration or global skills directory is modified automatically.

## Motion and design domains

Reference-only entries use `analysis.domain: null`. They remain retrievable by ID or `kind=reference`, and are excluded from `domain=motion` / `domain=design` search and domain collections.

Reviewed references include a separate `referenceReview` with `targetDomain: motion | design | mixed | tooling`, `resourceType`, source/evidence SHA-256 values, classified asset type/effects/components/use cases, and `preview`. Resource types are `example`, `library`, `tool`, `design-system`, `case-study`, `collection`, `learning`, and `portfolio`. A preview is either `{mode: related-asset, assetId, limitations}` or an independently authored `{mode: illustration, language: css | svg, code, dom?, license: CC0-1.0, notice, attribution: Motion Lab, limitations}`. It does not replace the original `code`, `license` or `category`. The original renderer remains none; the web resolver renders this separate local preview with a mandatory distinction label. The compact index includes target domain, resource type, mode and optional asset ID. Use `kind=reference` with `asset_type`, `effect`, or `component` filters to retrieve reviewed references, then inspect `referenceReview.resourceType` or filter it locally. `stats.referenceReview` includes classified/local-preview counts, `targetDomains`, `resourceTypes`, `assetTypes`, and `previewModes`. See [asset analysis](asset-analysis.md) for preview rights and limitations.

`data/reference-removals.json` binds excluded original-record digests to immutable access-evidence digests. Removed IDs are omitted from the catalog, index, collections and database, and cannot be retrieved through public interfaces. Read the current collection counts from `stats` and access limitations from each record's evidence.

Use `domain=motion` for moving compositions and `domain=design` for static patterns, shapes, palettes and material images. The explorer has Motion, Design and References tabs. Domain collections are `dist/collections/domain-motion.json` and `dist/collections/domain-design.json`. Domain collections contain stored assets and exclude reference links; category collections still partition all browse entries. `stats.storedAssets` excludes reference links; `stats.domains` counts stored assets in each domain.

Image entries use `kind: image`, `language: image`, `category: material`, `code: null`, `preview.type: image`, and `image: {path,mime,width,height,sha256,sourceSha256}`. The path is a bounded local `assets/materials/ID.jpg` path. Build and verification check the descriptor, actual file magic, size and digest. Source 1K color-map images are preserved upstream and reencoded without EXIF for local browsing and reuse. Normal/roughness channels, sizes and formats are not extra assets. Runtime interfaces never proxy remote media.

Additional motion, design, material and shape records are stored as registered JSON inputs with preserved source artifacts and evidence. See [collection](collection.md) for rebuilding, validation and similarity rechecks.
