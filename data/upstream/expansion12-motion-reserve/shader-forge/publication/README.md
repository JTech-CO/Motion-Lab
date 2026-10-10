# shader-forge

[![license](https://img.shields.io/github/license/wrennly/shader-forge?style=flat-square)](./LICENSE)
[![status](https://img.shields.io/badge/status-dormant-orange?style=flat-square)](#status)
[![python](https://img.shields.io/badge/python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![WebGPU](https://img.shields.io/badge/WebGPU-WGSL-005A9C?style=flat-square)](https://www.w3.org/TR/webgpu/)
[![model](https://img.shields.io/badge/model-Qwen3--Coder--80B-7C3AED?style=flat-square)](https://huggingface.co/Qwen)

> An autonomous shader studio — a local LLM writes WGSL/GLSL art shaders, `naga` + 6-axis LLM review gatekeep them, and a human curator (you) approves the final gallery.

![aurora](data/aurora_wgsl.png)

<table>
<tr>
<td><img src="gallery/2026-03-29_volumetric-clouds-with-god-rays-at-sunset/thumbnail.png" width="240"/></td>
<td><img src="gallery/2026-03-27_liquid-chrome-morphing-abstract-sculpture/thumbnail.png" width="240"/></td>
<td><img src="gallery/2026-03-28_colorful-gradient-waves/thumbnail.png" width="240"/></td>
</tr>
<tr>
<td><img src="gallery/2026-03-25_bright-neon-plasma-waves-filling-the-screen/thumbnail.png" width="240"/></td>
<td><img src="gallery/2026-03-25_abstract-impossible-geometry-optical-illusion/thumbnail.png" width="240"/></td>
<td><img src="gallery/2026-03-24_volumetric-god-rays-through-stained-glass-window/thumbnail.png" width="240"/></td>
</tr>
</table>

## Status

Research prototype, **currently dormant**. Phase 3 (WGSL quality lift) paused mid-flight while the author focuses on another project. Code, gallery (55 shaders), and design docs are preserved as-is. Issues welcome for reproduction questions; PRs deprioritized until the project resumes.

## Why it exists

Standalone WGSL *art* shaders barely exist in the wild — most WGSL corpora are engine internals (Bevy PBR, wgpu examples, Web-RTRT pipelines). shader-forge was an experiment to see whether a local 80B code model plus a curated RAG could produce something closer to Shadertoy-quality output, but in the WebGPU generation.

It's also a concrete reference for **fully local, autonomous creative loops**: no OpenAI call, no hosted inference, no external review API. Everything runs on one box.

## Pipeline

```
SCOUT    → Tavily API pulls trends → LLM proposes 3–5 shader themes
FORGE    → RAG selects references → Qwen3-Coder-Next 80B writes WGSL/GLSL
           → naga-cli validates → LLM reviews on 6 axes (30 pts total)
           → on failure, feedback-driven retry (max 5×)
RENDER   → headless WebGPU (Chrome + Vulkan) → thumbnail.png + preview.mp4
STAGE    → FastAPI WebUI on :3333, dual WebGL/WebGPU live preview
PUBLISH  → approved shaders drop into inbox/ for downstream pickup
```

## Stack

| Layer | Tech |
|-------|------|
| Inference | `llama.cpp` / llama-server on localhost:8080 |
| Model | Qwen3-Coder-Next 80B-A3B (Q4_K_XL, ~47GB) |
| Shader compiler | `naga-cli` (WGSL → SPIR-V), `glslang` (GLSL ES) |
| RAG | ChromaDB + `all-MiniLM-L6-v2` |
| Headless render | `wgpu-py` + Vulkan, Puppeteer + Chrome headless |
| Review WebUI | FastAPI + Three.js (WebGL) / raw WebGPU |

Designed for NVIDIA Project DIGITS (GB10 / ARM64), but any CUDA + Vulkan host with enough VRAM for the model should work.

## Highlights

- **514-shader curated WGSL corpus** from wgpu/Bevy/compute.toys/approved art + 23 shabon-fx GLSL references → 96.1% passed `naga` validation
- **`let`→`var` auto-fix** for the most frequent WGSL-vs-GLSL translation error the LLM makes
- **6-axis review rubric** (composition / motion / color / novelty / code quality / concept fit) — JSON-parsed, feedback fed back into the retry loop
- **Best score shipped:** 24/25 (`vibrant-plasma-energy-vortex`)
- **Temperature split:** creative director prompt runs at 0.7, the coder stays at 0.0 — separation of design intent and faithful implementation

## Gallery

55 generated shaders live in [`gallery/`](./gallery), each folder carrying:

- `shader.frag` (GLSL) or `shader.wgsl`
- `metadata.json` — theme, style hints, references used, review status
- `thumbnail.png` — 1080×1080 render

Browse locally via the Stage WebUI:

```bash
cd stage && python -m server  # http://localhost:3333
```

## Quick start

```bash
# 1. Environment
cp .env.example .env
# edit .env: set TAVILY_API_KEY and point LLM_BASE_URL at your llama-server

# 2. Python deps
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 3. naga-cli
cargo install naga-cli

# 4. Start your local llama-server (example)
llama-server -m /path/to/Qwen3-Coder-Next-UD-Q4_K_XL.gguf \
  --port 8080 --host 0.0.0.0 -ngl 99 --ctx-size 16384 --flash-attn on

# 5. Generate a WGSL shader
python forge/cli.py --theme "aurora borealis" --target wgsl
# Output lands in gallery/YYYY-MM-DD_aurora-borealis/

# 6. Review WebUI
python stage/server.py  # open http://localhost:3333
```

## Not included in this repo

- **`context/`** — the RAG corpus (third-party Shadertoy/Bevy/wgpu code). Regenerate via `forge/fetch_shadertoy.py` and `forge/extract_repos.py`.
- **`data/chromadb/`, `data/qlora_output/`, `data/training/`** — reproducible build artifacts.
- **`Web-RTRT/`, `WebGPU-Fluid-Simulation/`, `WebGPU-Lab/`, `webgpu-demo/`, `webgpu-native-examples/`** — upstream reference projects; clone them separately if you want those samples available to the ingest pipeline.
- Model weights — download from Hugging Face.

## Design docs

- [`DESIGN.md`](./DESIGN.md) — v1 (WebGL1 / GLSL ES 1.00) architecture
- [`DESIGN_v2.md`](./DESIGN_v2.md) — v2 migration to WebGPU / WGSL
- [`CHANGELOG.md`](./CHANGELOG.md) — running log of experiments and key findings
- [`WEBGPU_SHADER_REPOS.md`](./WEBGPU_SHADER_REPOS.md) — survey of WGSL corpora

## License

[MIT](./LICENSE)

## Links

- [@wrennly_dev](https://x.com/wrennly_dev) — updates
- [shabon-fx](https://github.com/wrennly/shabon-fx) — 24 curated GLSL shaders that seeded the RAG corpus
- [react-shadertoy](https://github.com/wrennly/react-shadertoy) — the renderer used for live preview

---

## 日本語メモ

ローカル LLM だけでシェーダー制作パイプラインを自律化する実験プロジェクト。trend スカウト → RAG 参照選択 → WGSL/GLSL 生成 → naga バリデーション → 6 軸 LLM レビュー → headless レンダリング → 人間キュレーションまで、外部 API を (Tavily を除き) 使わずに完結させた。

WebGPU 移行 (Phase 3) の途中で別プロジェクトに集中するため休眠中だが、**standalone な WGSL アートシェーダーという空白領域** に踏み込んだ記録として、設計書・コード・55作品のギャラリーを残している。
