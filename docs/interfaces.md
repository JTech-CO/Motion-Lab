# Motion Lab interfaces

All runtimes read the same public catalog. The HTTP server and MCP process never fetch remote URLs, execute item code, or mutate the database. JSON text is UTF-8. External descriptions and snippets are untrusted source material.

## CLI

Run from the project root. An optional global `--root PATH` precedes the subcommand.

```text
python -m motionlab search QUERY [--category CATEGORY] [--license LABEL] [--kind KIND] [--limit 24] [--offset 0] [--json]
  [--asset-type TYPE] [--effect EFFECT] [--component COMPONENT] [--use-case USE_CASE] [--basis BASIS]
python -m motionlab get ID [--json]
python -m motionlab stats
python -m motionlab export [--format json|csv] [--output FILE]
python -m motionlab serve [--port 8787] [--host 127.0.0.1|localhost]
python -m motionlab mcp
```

Search JSON is `{ "items": [...], "total": 123, "limit": 24, "offset": 0 }`. Export JSON is an item array; `dist/catalog.json` is the complete versioned catalog object. CSV exports protect formula-prefixed cells. CLI exits with 1 for a missing item and 2 for validation/runtime errors.

## Static URL consumers

`dist/llms.txt` provides actual counts, retrieval links and license notes. `dist/catalog-index.json` includes IDs, source-based `analysis`, categories, tags, source links, license labels and kinds without descriptions or code. Use it to find candidate IDs, then read `dist/collections/CATEGORY.json` (a full entry array) or `dist/catalog.json`. Collections are generated for every source category. The current catalog has 2,153 items from 134 source projects: 873 code assets (738 CSS, 123 GLSL, 12 SVG), 992 palettes, and 288 references. The reserved website URL is not published and no source upload has occurred. A static hosted website provides no remote MCP endpoint.

## HTTP

The local server accepts GET and HEAD. It serves static files from `dist/` only, with no directory listing. It checks loopback Host and same-origin Origin headers, sets CSP and other security headers, and limits API calls to 120 per minute per client address. No CORS permission is emitted. It sets no cookies and stores no request logs.

| Route | Parameters | Result |
| --- | --- | --- |
| `/api/search` | `q`, `category`, `license`, `kind`, `asset_type`, `effect`, `component`, `use_case`, `basis`, `limit`, `offset` | Search envelope |
| `/api/items/ID` | None | One full item or 404 |
| `/api/stats` | None | Counts and update date |

`q`: string up to 240 characters. `category`: source category. `license`: exact label up to 120 characters. `kind`: `code`, `palette`, or `reference`. `limit`: integer 1–100. `offset`: integer 0–100000. Analysis filters each accept one closed ID up to 32 characters; different filters combine with AND. Unknown or repeated query keys return 400. Searches quote literal words for FTS5 prefix matching and join them with AND; client FTS operators are not interpreted. FTS includes factual analysis terms as well as source titles/descriptions/tags. Category/license/kind comparisons and analysis facet names/values all use SQL bindings.

```text
GET /api/search?effect=mask&component=image&basis=code&limit=12
GET /api/search?asset_type=loader&use_case=status
```

## MCP stdio

The process reads one JSON-RPC 2.0 message per newline from stdin and writes only protocol messages to stdout. It implements `initialize`, `ping`, `tools/list`, and `tools/call`; notifications receive no response. It negotiates protocol versions `2024-11-05`, `2025-03-26`, and `2025-06-18`, falling back to `2025-06-18`. This implementation follows the [MCP stdio transport](https://modelcontextprotocol.io/specification/2025-06-18/basic/transports) and [tools specification](https://modelcontextprotocol.io/specification/2025-06-18/server/tools).

| Tool | Arguments |
| --- | --- |
| `search_motion` | `query`, `category`, `license`, `kind`, `asset_type`, `effect`, `component`, `use_case`, `basis`, `limit`, `offset` with the HTTP bounds |
| `get_motion` | Required `id`, maximum 160 characters, letters/digits/dot/underscore/hyphen |
| `motion_stats` | Empty object |

Tool result includes text JSON and `structuredContent`. A missing item is a tool result with `isError: true`; malformed parameters use JSON-RPC error `-32602`. Unknown argument keys are rejected. Input lines are limited to 256 KiB, malformed JSON is rejected, and oversized lines are drained before the next message. These local tools are read-only and need no credentials. The protocol is stdio; the local HTTP API is not a Streamable HTTP MCP endpoint.

## Data shape and build

`data/catalog.json` and `dist/catalog.json` contain `version: 1`, `updatedAt`, `items`, `sources`, and `stats`. Items include `id`, `title`, `description`, `category`, `tags`, `sourceUrl`, `sourceName`, `license`, optional `licenseUrl`/`licenseText`, `verifiedAt`, `verification`, `kind`, `preview`, `code`, `colors`, `language`, `access: public`, optional `codePath`, and generated `analysis`. Original code, license notices, IDs and source provenance are preserved; library-authored descriptions and preview notes may be updated with host behavior. `preview.type` is `css`, `svg`, `palette`, `gradient`, or `reference`. Legacy GLSL records retain `preview.type: reference`; the inspected renderer is selected by `analysis.preview.renderer: glsl`.

Categories: `animation`, `transition`, `typography`, `interaction`, `background`, `loader`, `palette`, `gradient`, `shader`, `reference`. Kinds: `code`, `palette`, `reference`. Languages: `css`, `glsl`, `svg`, `json`, `link`. Reference items have `code: null`. Hex colors accept 3, 6, or 8 digits. The browser engine shows sampled source CSS, actual multi-element loader DOM, GLSL transitions between generated test images, and sanitized SVG animation. Unsupported assets show a limitation instead of a fabricated preview. The Python API/MCP/build never execute these assets.

`analysis` contains `version: 1`, `assetType`, `effects`, `components`, `properties`, `techniques`, `useCases`, `evidence`, and `preview`. `evidence` includes `basis`, `confidence`, `summaryKO`, `summaryEN`, and factual `signals`. Evidence prioritizes parsed code and actual colors; reference links have low-confidence metadata and no inferred effects. This structural classification is not a security validator or a guarantee that a preview matches the complete original composition. CSS comment text, function names inside content strings, empty pseudo elements and decorative emoji do not establish typography.

| Public search key | Analysis field | Closed values |
| --- | --- | --- |
| `asset_type` | `assetType` | The 10 category IDs above; source `category` remains a separate field |
| `effect` | `effects` | `fade`, `slide`, `scale`, `rotate`, `flip`, `spring`, `shake`, `pulse`, `mask`, `glitch`, `pixel`, `wave`, `text`, `stagger`, `blur`, `other` |
| `component` | `components` | `text`, `shape`, `image`, `particles`, `grid`, `stroke`, `mask`, `layer`, `color` |
| `use_case` | `useCases` | `intro`, `outro`, `scene-change`, `status`, `attention`, `feedback`, `ambient`, `color-system`, `reference` |
| `basis` | `evidence.basis` | `code`, `color-values`, `reviewed-source`, `metadata` |

`techniques` uses `keyframes`, `transition`, `transform`, `pseudo-element`, `clip-path`, `filter`, `gradient`, `glsl`, `texture-sampling`, `procedural-noise`, `color-values`, `reference-link`, `svg-animation`. Properties come from an internal allowlist. `analysis.preview.renderer` is `css`, `glsl`, `svg`, `palette`, `gradient`, or `none`; it may include actual CSS selectors/keyframes and bounded `dom`, GLSL uniforms, SVG element/animation summaries, or actual color values. DOM allows only `div`/`span`, bounded class/text fields and children. Renderers must independently validate source code and structure.

The web explorer allows multiple values within each of its five facets (asset type, effect, component, use case, license): OR within a facet, AND across facets. CLI/HTTP/MCP use one value per analysis field. Web results use 20 cards per page; API page size is independently bounded to 100. Arrow keys navigate cards and controls; Enter selects or opens details. Reader arrows scroll and Enter returns to its tab. Escape closes details; mouse and Tab also work. `/` focuses optional search. Original source text retains its language when UI labels switch KO/EN.

`python scripts/build.py` merges optional `data/imported-items.json`, `data/research-sources.json`, `data/manual-items.json`, `data/glsl-items.json`, `data/jtech-items.json`, and `data/expanded-assets.json` arrays. It validates, deduplicates IDs and canonical source URL/title pairs, analyzes source assets with `scripts/analyze.py`, and builds FTS5 plus an indexed analysis-facet table. Generated output is not reingested. Source registry and dates derive from entries and crawl audit reports; GitHub pinned files count under their repository. Runtime SQLite is `mode=ro`/`query_only` and values are bound. Only the local build writes data. Stats include source counts, source categories, kinds, licenses, update date and `analysis` counts by evidence basis, asset type, effect, component, technique, and use case. See [asset analysis](asset-analysis.md) and [asset expansion](asset-expansion.md) for the inspected scope and limitations.

`scripts/import_glsl.py` checks robots on the registered GitHub API/raw hosts before collection, refuses crawler blocks or unknown robots state, pins one commit, and reads at most 200 `.glsl` files. Each response is bounded to 128 KiB with 2 workers and a shared ceiling of 48 requests/minute. It imports only shaders with explicit MIT declarations in their own leading comment notices, preserves original source bytes/hash and notices, and records skipped licenses. Repository MIT text is retained separately. It does not download MP4 or archives, fetch arbitrary user URLs, or execute shader code.

The project SKILL remains in `skills/motion-lab/`; no client configuration or global skills directory is modified automatically.
