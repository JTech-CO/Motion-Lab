"""Keep the bilingual README counts and composition chart in sync with the catalog."""

from datetime import date
import os
from pathlib import Path
import stat
import sys
import tempfile

if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.package import checked_path

SUMMARY_START = "<!-- motionlab:catalog-summary:start -->"
SUMMARY_END = "<!-- motionlab:catalog-summary:end -->"
CHART_PATH = "docs/assets/catalog-composition.svg"
COLLECTIONS = (("motion", "Motion", "#69e6f7"),
               ("design", "Design", "#edf7fa"),
               ("references", "References", "#91a5b0"))


def composition(stats):
    """Count canonical motion/design assets and references, never aliases or variants."""
    if not isinstance(stats, dict):
        raise ValueError("Catalog statistics must be an object")
    domains, kinds = stats.get("domains", {}), stats.get("kinds", {})
    if not isinstance(domains, dict) or not isinstance(kinds, dict):
        raise ValueError("Catalog domain/kind counts must be objects")
    counts = {"motion": domains.get("motion", 0), "design": domains.get("design", 0),
              "references": kinds.get("reference", 0)}
    for value in (*counts.values(), stats.get("total"), stats.get("storedAssets"), stats.get("sources")):
        if type(value) is not int or not 0 <= value <= 1_000_000_000:
            raise ValueError("Catalog counts must be bounded nonnegative integers")
    if sum(counts.values()) != stats["total"] or counts["motion"] + counts["design"] != stats["storedAssets"]:
        raise ValueError("Catalog composition does not match canonical totals")
    updated = stats.get("updatedAt")
    if not isinstance(updated, str) or len(updated) != 10 or date.fromisoformat(updated).isoformat() != updated:
        raise ValueError("Catalog update date must be an ISO date")
    return counts


def render_chart(stats):
    counts = composition(stats)
    total = stats["total"]
    percentages = {key: count * 100 / total if total else 0 for key, count in counts.items()}
    description = "; ".join(f"{label}: {counts[key]:,} ({percentages[key]:.1f}%)"
                            for key, label, _ in COLLECTIONS)
    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="960" height="420" viewBox="0 0 960 420" role="img" aria-labelledby="chart-title chart-description">',
        f'<title id="chart-title">Motion Lab catalog composition: {total:,} entries</title>',
        f'<desc id="chart-description">{description}. Updated {stats["updatedAt"]}. Canonical entries only; preserved variants are excluded.</desc>',
        '<rect width="960" height="420" rx="12" fill="#080a0c"/>',
        '<g font-family="Arial, Helvetica, sans-serif">',
        '<text x="44" y="45" fill="#edf7fa" font-size="17" letter-spacing="1.5">CATALOG COMPOSITION</text>',
        '<circle cx="216" cy="215" r="118" fill="none" stroke="#1c2c32" stroke-width="58"/>',
    ]
    start = 0.0
    for key, _, color in COLLECTIONS:
        share = percentages[key]
        if counts[key]:
            parts.append(f'<circle data-collection="{key}" cx="216" cy="215" r="118" fill="none" stroke="{color}" stroke-width="58" stroke-linecap="butt" pathLength="100" stroke-dasharray="{share:.8f} 100" stroke-dashoffset="{-start:.8f}" transform="rotate(-90 216 215)"/>')
        start += share
    total_size = min(35, 170 / (len(f"{total:,}") * 0.62))
    parts.extend([
        f'<text x="216" y="214" text-anchor="middle" fill="#edf7fa" font-size="{total_size:.1f}" font-weight="700">{total:,}</text>',
        '<text x="216" y="243" text-anchor="middle" fill="#b0c1c7" font-size="15">total entries</text>',
    ])
    for index, (key, label, color) in enumerate(COLLECTIONS):
        y = 130 + index * 84
        parts.extend([
            f'<g id="legend-{key}">',
            f'<circle cx="440" cy="{y - 7}" r="5" fill="{color}"/>',
            f'<text x="460" y="{y}" fill="#edf7fa" font-size="22">{label}</text>',
            f'<text x="908" y="{y + 3}" text-anchor="end" fill="{color}" font-size="28" font-weight="700">{percentages[key]:.1f}%</text>',
            f'<text x="460" y="{y + 27}" fill="#b0c1c7" font-size="15">{counts[key]:,} entries</text>',
            '</g>',
        ])
    parts.extend([
        f'<text x="44" y="391" fill="#b0c1c7" font-size="13">Catalog {stats["updatedAt"]} · Canonical entries; preserved variants excluded</text>',
        '</g>', '</svg>', '',
    ])
    return "\n".join(parts)


def render_summary(stats, lang):
    counts = composition(stats)
    if lang == "ko":
        lines = [
            f"**저장 에셋 {stats['storedAssets']:,}개 + 검토 레퍼런스 {counts['references']:,}개**, 등록된 출처 {stats['sources']:,}개.",
            f"아래 수량은 {stats['updatedAt']} 카탈로그 기준입니다. 현재 수량은 `python -m motionlab stats`로 확인하세요.",
            "", "| 자료 모음 | 수량 | 내용 |", "| --- | ---: | --- |",
            f"| 모션 | {counts['motion']:,} | 애니메이션, 전환, 타이포그래피, 로더, 인터랙션 효과 |",
            f"| 디자인 | {counts['design']:,} | 패턴, 형상, 팔레트, 그라디언트, 소재 이미지 |",
            f"| 레퍼런스 | {counts['references']:,} | 검토한 예제, 라이브러리, 도구, 사례 연구, 학습 자료 |",
        ]
    else:
        lines = [
            f"**{stats['storedAssets']:,} stored assets + {counts['references']:,} reviewed references**, across {stats['sources']:,} registered sources.",
            f"Counts below reflect the catalog on {stats['updatedAt']}; run `python -m motionlab stats` for the current totals.",
            "", "| Collection | Entries | Contents |", "| --- | ---: | --- |",
            f"| Motion | {counts['motion']:,} | Animation, transitions, typography, loaders and interaction effects |",
            f"| Design | {counts['design']:,} | Patterns, shapes, palettes, gradients and material images |",
            f"| References | {counts['references']:,} | Reviewed examples, libraries, tools, case studies and learning resources |",
        ]
    return "\n".join(lines)


def replace_summary(text, stats, lang):
    if SUMMARY_START not in text and SUMMARY_END not in text:
        return text
    if text.count(SUMMARY_START) != 1 or text.count(SUMMARY_END) != 1:
        raise ValueError("README catalog summary requires exactly one marker pair")
    start, end = text.index(SUMMARY_START), text.index(SUMMARY_END)
    if start >= end:
        raise ValueError("README catalog summary markers are reversed")
    return (text[:start] + SUMMARY_START + "\n" + render_summary(stats, lang)
            + "\n" + text[end:])


def write_text(path, root, text):
    """Do not follow linked output paths or truncate an existing README on failure."""
    info = checked_path(path, root, missing=True)
    if info is not None:
        if not stat.S_ISREG(info.st_mode):
            raise ValueError("README asset output must be a regular file")
        if path.read_text(encoding="utf-8") == text:
            return
    path.parent.mkdir(parents=True, exist_ok=True)
    checked_path(path.parent, root)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".motionlab-readme-", suffix=".tmp",
                                         mode="w", encoding="utf-8", newline="\n", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(text)
        checked_path(path, root, missing=True)
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def write_readme_assets(root, stats):
    root = Path(root).absolute()
    chart = render_chart(stats)
    documents = []
    for name, lang in (("README.md", "en"), ("README-KO.md", "ko")):
        path = root / name
        info = checked_path(path, root, missing=True)
        if info is not None:
            if not stat.S_ISREG(info.st_mode):
                raise ValueError("README input must be a regular file")
            documents.append((path, replace_summary(path.read_text(encoding="utf-8"), stats, lang)))
    write_text(root / CHART_PATH, root, chart)
    for path, text in documents:
        write_text(path, root, text)


if __name__ == "__main__":
    import argparse
    project = Path(__file__).resolve().parent.parent
    from motionlab.catalog import Catalog

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=project)
    options = parser.parse_args()
    try:
        write_readme_assets(options.root, Catalog(options.root).stats())
        print("Bilingual README counts and catalog composition chart updated.")
    except (OSError, ValueError) as error:
        print(f"README assets failed: {error!r}", file=sys.stderr)
        sys.exit(1)
