![Motion Lab - motion and design for people and AI](docs/assets/og-repository.jpg)

# Motion Lab

**English** · [한국어](README-KO.md)

![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=flat-square)
![SQLite FTS5](https://img.shields.io/badge/SQLite-FTS5-003B57?style=flat-square)
![MCP stdio](https://img.shields.io/badge/MCP-stdio-222222?style=flat-square)
![KO / EN](https://img.shields.io/badge/UI-KO%20%2F%20EN-555555?style=flat-square)

A library of motion code, design assets and reviewed references for people and AI tools. Explore local previews and retrieve code, colors or images with their sources and licenses.

<!-- motionlab:catalog-summary:start -->
**11,603 stored assets + 283 reviewed references**, across 178 registered sources.
Counts below reflect the catalog on 2026-10-11; run `python -m motionlab stats` for the current totals.

| Collection | Entries | Contents |
| --- | ---: | --- |
| Motion | 3,417 | Animation, transitions, typography, loaders and interaction effects |
| Design | 8,186 | Patterns, shapes, illustrations, palettes, gradients and material images |
| References | 283 | Reviewed examples, libraries, tools, case studies and learning resources |
<!-- motionlab:catalog-summary:end -->

[Website](https://jtech-co.github.io/Motion-Lab/) · [GitHub repository](https://github.com/JTech-CO/Motion-Lab)

## Quick start

Requires Git, Python 3.10+ and SQLite with FTS5. Build after cloning to generate the full catalog; no API key is needed.

```sh
git clone https://github.com/JTech-CO/Motion-Lab.git
cd Motion-Lab
python scripts/build.py
python -m motionlab serve --port 8787
```

Open [the introduction](http://127.0.0.1:8787/) or [the library](http://127.0.0.1:8787/library.html). Browse in Korean/English with filters and 20/50/100 entries per page. The local server accepts loopback connections only.

## Collection composition

![Motion, Design and References proportions](docs/assets/catalog-composition.svg)

The chart and both README count summaries update automatically when `python scripts/build.py` builds the catalog. Preserved original variants are not counted as additional entries.

## Connect an AI tool

Use the [Motion Lab SKILL](skills/motion-lab/SKILL.md) and [CLI, local MCP, HTTP and JSON guide](docs/interfaces.md). The site's **AI connection** dialog includes setup examples. Local API and MCP access is read-only; the static website does not provide a remote MCP endpoint.

## Reuse and provenance

Licenses apply **per asset and per original variant**; preserve required attribution and notices. Reference previews have their own terms and do not grant rights to the referenced work. Source review does not certify imported code as safe to execute.

[Collection, rebuilding and packaging](docs/collection.md) · [Classification, previews and rights](docs/asset-analysis.md)
