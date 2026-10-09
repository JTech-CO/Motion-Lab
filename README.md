![Motion Lab - motion assets for people and AI tools](docs/assets/og-repository.jpg)

# Motion Lab

![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=flat-square)
![SQLite FTS5](https://img.shields.io/badge/SQLite-FTS5-003B57?style=flat-square)
![MCP stdio](https://img.shields.io/badge/MCP-stdio-222222?style=flat-square)
![KO / EN](https://img.shields.io/badge/UI-KO%20%2F%20EN-555555?style=flat-square)

A searchable archive of verified motion code and static design assets. Explore motion, transitions, typography and loaders separately from patterns, shapes, textures and colors. Browse local previews on the web, search with the CLI, or connect an AI tool through local MCP and the included SKILL. No MP4 files are stored.

**10,001 stored assets** from 160 source projects: 3,345 motion assets and 6,656 static design assets, plus 285 reviewed references. The library provides local previews and structured filters. Similar entries are grouped with each original variant and its source rights preserved.

[GitHub repository](https://github.com/JTech-CO/Motion-Lab) · [AI SKILL](skills/motion-lab/SKILL.md) · [CLI, HTTP & MCP](docs/interfaces.md)

## Quick start

Requires Git, Python 3.10+, and SQLite with FTS5 support. The Python backend uses only the standard library; no package installation or API key is required.

```sh
git clone https://github.com/JTech-CO/Motion-Lab.git
cd Motion-Lab
python scripts/build.py
python -m motionlab serve --port 8787
```

Open [the home page](http://127.0.0.1:8787/) or [the library](http://127.0.0.1:8787/library.html). The server binds to loopback only. Motion, Design and References tabs offer structured filters, 20/50/100 entries per page, arrow-key/Enter navigation, mouse selection, and Korean/English UI.

```sh
python -m motionlab search --effect mask --component image --basis code --limit 12 --json
python -m motionlab search --domain design --asset-type pattern --limit 12 --json
python -m motionlab search --domain design --kind image --category material --limit 12 --json
```

## Connect an AI tool

Use the [MCP configuration and tool schemas](docs/interfaces.md) to launch `motionlab/launch_mcp.py` from the cloned project's absolute path. The local stdio server provides `search_motion`, `get_motion`, and `motion_stats`. Follow the [Motion Lab SKILL](skills/motion-lab/SKILL.md) for finding and reusing entries.

For link-based access, serve the static `dist/` directory: `/llms.txt`, `/catalog-index.json`, `/catalog.json`, and `/collections/*.json` describe the same collection. The compact index identifies candidates; full records contain code, evidence, and license notices. GitHub and static site URLs are not MCP endpoints.

## Reuse and provenance

Licenses apply **per asset**. Keep each entry's original code or image, source attribution, and full license notice when reusing it. Reference entries and unknown licenses do not grant copying permission. Stored-asset previews use CSS, GLSL, SVG, exact colors or actual material images. Reference previews are independently authored CC0 concept illustrations or a related stored asset, with separate rights and limitations; they do not reproduce the original reference page or source execution.

The collection preserves source IDs, code, licenses, pinned commits, and hashes. Former IDs resolve to their original variants; each variant retains its own code or exact palette array and license. Analysis derives effects, components, and use cases from code or color values; reference-only metadata is marked separately.

- [Collection, rebuilding and packaging](docs/collection.md)
- [Classification, previews and original variants](docs/asset-analysis.md)
- [Original recipes](docs/recipes.md)

The local API and MCP are read-only. The project does not require accounts, cookies, or uploads.

Browsing, rebuilding and serving require no third-party Python packages.
Optional image similarity checks use [phase2-requirements.txt](scripts/phase2-requirements.txt).
Run `python scripts/package.py` to create a portable package from the current repository.
