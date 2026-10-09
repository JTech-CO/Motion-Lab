![Motion Lab - motion assets for people and AI tools](docs/assets/og-repository.jpg)

# Motion Lab

![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=flat-square)
![SQLite FTS5](https://img.shields.io/badge/SQLite-FTS5-003B57?style=flat-square)
![MCP stdio](https://img.shields.io/badge/MCP-stdio-222222?style=flat-square)
![KO / EN](https://img.shields.io/badge/UI-KO%20%2F%20EN-555555?style=flat-square)

A searchable archive of motion code, transitions, typography, loaders, shaders, gradients, palettes, and references. Browse previews on the web, search with the CLI, or connect an AI tool through local MCP and the included SKILL. No MP4 files are stored.

**6,108 entries from 149 source projects:** 3,374 code assets, 2,446 palettes, and 288 references. The first 5,000-entry milestone is complete, including 5,820 stored assets.

[GitHub repository](https://github.com/JTech-CO/Motion-Lab) · [AI SKILL](skills/motion-lab/SKILL.md) · [CLI, HTTP & MCP](docs/interfaces.md)

## Quick start

Requires Git, Python 3.10+, and SQLite with FTS5 support. The Python backend uses only the standard library; no package installation or API key is required.

```sh
git clone https://github.com/JTech-CO/Motion-Lab.git
cd Motion-Lab
python scripts/build.py
python -m motionlab serve --port 8787
```

Open [the home page](http://127.0.0.1:8787/) or [the library](http://127.0.0.1:8787/library.html). The server binds to loopback only. The library offers five filters, 20/50/100 entries per page, keyboard navigation, and Korean/English UI.

```sh
python -m motionlab search --effect mask --component image --basis code --limit 12 --json
```

## Connect an AI tool

Use the [MCP configuration and tool schemas](docs/interfaces.md) to launch `motionlab/launch_mcp.py` from the cloned project's absolute path. The local stdio server provides `search_motion`, `get_motion`, and `motion_stats`. Follow the [Motion Lab SKILL](skills/motion-lab/SKILL.md) for finding and reusing entries.

For link-based access, serve the static `dist/` directory: `/llms.txt`, `/catalog-index.json`, `/catalog.json`, and `/collections/*.json` describe the same collection. The compact index identifies candidates; full records contain code, evidence, and license notices. GitHub and static site URLs are not MCP endpoints.

## Reuse and provenance

Licenses apply **per asset**. Keep each entry's original code, source attribution, and full license notice when reusing it. Reference entries and unknown licenses do not grant copying permission. CSS, GLSL, and SVG previews use the stored sources where supported; preview adaptations and limitations are documented in each entry.

The collection preserves source IDs, code, licenses, pinned commits, and hashes. Analysis derives effects, components, and use cases from code or color values; reference-only metadata is marked separately.

- [Collection pipeline and update commands](docs/collection.md)
- [Analysis and preview limitations](docs/asset-analysis.md)
- [Full catalog duplicate and similarity review](docs/duplicate-audit.md)
- [Additional source assets and evidence](docs/asset-expansion.md)
- [CSS collection](docs/css-wave.md) · [SVG and component collection](docs/vector-wave.md) · [Palette collection](docs/color-wave.md)
- [Original recipes](docs/recipes.md)
- [Validation and security checks](docs/validation.md)

The local API and MCP are read-only. The project does not require accounts, cookies, or uploads.
