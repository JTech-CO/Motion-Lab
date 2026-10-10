![Motion Lab - motion and design for people and AI](docs/assets/og-repository.jpg)

# Motion Lab

**English** · [한국어](README-KO.md)

![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=flat-square)
![SQLite FTS5](https://img.shields.io/badge/SQLite-FTS5-003B57?style=flat-square)
![MCP stdio](https://img.shields.io/badge/MCP-stdio-222222?style=flat-square)
![KO / EN](https://img.shields.io/badge/UI-KO%20%2F%20EN-555555?style=flat-square)

A library of motion code, design assets and reviewed references for people and AI tools. Compare local previews, search by effect and component, then retrieve the original code or image with its source and license. The collection stores code, colors and images rather than MP4 files.

<!-- motionlab:catalog-summary:start -->
**11,563 stored assets + 283 reviewed references**, across 177 registered sources.
Counts below reflect the catalog on 2026-10-10; run `python -m motionlab stats` for the current totals.

| Collection | Entries | Contents |
| --- | ---: | --- |
| Motion | 3,399 | Animation, transitions, typography, loaders and interaction effects |
| Design | 8,164 | Patterns, shapes, illustrations, palettes, gradients and material images |
| References | 283 | Reviewed examples, libraries, tools, case studies and learning resources |
<!-- motionlab:catalog-summary:end -->

[GitHub repository](https://github.com/JTech-CO/Motion-Lab) · [AI SKILL](skills/motion-lab/SKILL.md) · [CLI, HTTP & MCP](docs/interfaces.md)

## Quick start

Requires Git, Python 3.10+, and SQLite with FTS5 support. Browsing, building, CLI and MCP use the Python standard library and require no API key.

```sh
git clone https://github.com/JTech-CO/Motion-Lab.git
cd Motion-Lab
python scripts/build.py
python -m motionlab serve --port 8787
```

Run the build after cloning. The full `data/catalog.json` and `dist/catalog.json` are generated locally from the tracked inputs and notices, and are included in static exports and portable packages.

Open [the introduction](http://127.0.0.1:8787/) or [the library](http://127.0.0.1:8787/library.html). The Korean/English interface supports effect/component filters, 20/50/100 entries per page, motion pause and reduced-motion preferences. The local server binds to loopback only.

```sh
python -m motionlab search --domain motion --effect mask --component image --limit 12 --json
python -m motionlab search --domain design --asset-type pattern --limit 12 --json
python -m motionlab get gl-transitions-drop-zone-flicker --json
```

## Collection composition

![Motion, Design and References proportions](docs/assets/catalog-composition.svg)

The chart and both README count summaries update automatically when `python scripts/build.py` builds the catalog. Preserved original variants are not counted as additional entries.

## Connect an AI tool

**Local MCP:** launch `motionlab/launch_mcp.py` from the cloned project's absolute path. The stdio server provides `search_motion`, `get_motion` and `motion_stats`. Replace the example path with your clone location:

```json
{
  "mcpServers": {
    "motion-lab": {
      "command": "python",
      "args": ["/absolute/path/to/Motion-Lab/motionlab/launch_mcp.py"]
    }
  }
}
```

**SKILL, CLI and HTTP:** use the included [Motion Lab SKILL](skills/motion-lab/SKILL.md) and [interface guide](docs/interfaces.md). The site's **AI connection** dialog also provides copyable setup examples.

**Static links and JSON:** serve `dist/`. Start with `/llms.txt` and `/catalog-index.json`, then retrieve selected records from `/collections/*.json` or `/catalog.json`. Full records retain code, evidence and license notices. The [GitHub Pages workflow](.github/workflows/pages.yml) rebuilds the untracked full catalog and deploys the site on each push to `main`. GitHub and static site URLs do not provide a remote MCP endpoint or Python API.

## Reuse and provenance

Licenses apply **per asset and per original variant**. Preserve the source attribution and required license notices when reusing code or images. Similar entries are grouped for browsing while retaining original IDs, code, exact colors and rights; variants are not counted as additional independent assets.

The [Grok source review](data/grok-import-report.json) added 21 static design assets: 12 illustrations, 8 material images and 1 pattern. Each accepted work passed individual license checks and comparisons against the retained catalog; original files, notices and verification evidence are preserved.

Stored previews use supported CSS, GLSL, SVG, exact colors or local images, including raster illustrations and scanned textures. Reference previews are separate concept illustrations or related stored assets, with their own rights and limitations. They do not reproduce the original website or grant rights to the referenced work. Classification and source checks do not certify imported code as safe to execute.

- [Collection, rebuilding and packaging](docs/collection.md)
- [Classification, previews and original variants](docs/asset-analysis.md)
- [Original recipes](docs/recipes.md)

The local API and MCP are read-only; no accounts, cookies or uploads are required. CLI output escapes terminal control characters. Portable packaging rejects external file links and preserves the previous ZIP if creation fails. See the guides above for input and preview safeguards.

Run `python scripts/package.py` to create a portable package. Only optional image similarity checks require [additional Python packages](scripts/phase2-requirements.txt).
