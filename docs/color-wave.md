# Original palette expansion

The October 9, 2026 color wave adds **1,454 individually named, stored palettes from 10 original repositories**. These entries contain actual arrays of colors, their exact JSON, complete source notices, pinned source URLs and byte-level evidence. They are color assets for motion design, not animation or link-only records.

| Original source | Pinned commit | Stored arrays | Imported | Duplicate arrays | License |
| --- | --- | ---: | ---: | ---: | --- |
| [Palettetown](https://github.com/timcdlucas/palettetown) | `4f772f78578d2ae9167ab76024b7ec8886d4567e` | 389 | 388 | 1 | MIT |
| [NBA Palettes](https://github.com/murrayjw/nbapalettes) | `b1dc7a68b4bb1331ef22eec74f9c79c9f782321c` | 129 | 126 | 3 | MIT |
| [Color Lisa / lisa](https://github.com/tylerlittlefield/lisa) | `91f7f3f59ff60a89a161a9f8ff5be0804e7dd137` | 128 | 128 | 0 | MIT |
| [colRoz](https://github.com/jacintak/colRoz) | `b2e6319648749430e45f1842131067eb1aad732a` | 54 | 54 | 0 | MIT |
| [MetBrewer](https://github.com/BlakeRMills/MetBrewer) | `58839e5ac7c7d604c8704581f7b201a29986b814` | 56 | 56 | 0 | CC0-1.0 |
| [PrettyCols](https://github.com/nrennie/PrettyCols) | `d754b34d2e08dc9b85494c59cc99421ce5ef0651` | 46 | 46 | 0 | CC0-1.0 |
| [poisonfrogs](https://github.com/laurenoconnelllab/poisonfrogs) | `ba61837060eb9addc82950a97c6a0739d788d9d5` | 41 | 41 | 0 | MIT |
| [ColorBrewer](https://github.com/axismaps/colorbrewer) | `7d135fc4e19eda73f2eb1bf55fcdf4a04fe4881f` | 264 | 264 | 0 | Apache-2.0 plus original attribution conditions |
| [CARTOColors](https://github.com/CartoDB/CartoColor) | `1a850e4713a12c68373f1df1a7d42ff7869ed49c` | 228 | 227 | 1 | CC-BY-4.0 |
| [Radix Colors](https://github.com/radix-ui/colors) | `dbdb85470547c7d34b9001f48fddb08ded335979` | 124 | 124 | 0 | MIT |
| **Total** | | **1,459** | **1,454** | **5** | |

The importer reads literal R, YAML, JSON and TypeScript arrays without executing upstream code. Palettetown's `pokeColours` object is decoded from its original RDX2/XDR data file by a bounded parser supporting only simple list, string and numeric vectors. Closures, environments, bytecode, unknown types, excess nesting and trailing data are rejected. Pokemon sprites, team marks and artists' artwork are not copied.

ColorBrewer's original integer RGB values are represented by exactly equivalent HEX notation; both representations remain in the evidence. CARTO's numeric variant key is stored independently from the array's actual length. For example, `Antique-2` includes three original colors, and `TealRose-4` contains five; the original neutral or middle color is retained. The label is never used to truncate an array. Radix contains 62 solid and 62 alpha scales, each with its original 12 steps and separate light or dark source file. Display-P3 values and Tailwind's OKLCH scales are preserved as discovery evidence and excluded from the HEX catalog instead of being converted with loss.

Only complete stored arrays of 2 through 32 supported HEX colors are accepted; the imported arrays contain 2 through 15 colors. No size interpolation, hue variants, reversed copies, artificial combinations or subsampling is performed. Every item's `code` parses to exactly its `colors` array with the original order intact.

## Original bytes and notices

`data/upstream/color-wave/source-audit.json` records every original data and notice file needed for extraction, with its URL, pinned commit, byte length and SHA-256. Initial collection records are matched to the saved bytes; missing records are independently rechecked against the same pinned public raw URL. Offline extraction rejects a file that is missing, oversized, outside the wave directory or differs from its recorded bytes. Responses and compressed R input are limited to 8,000,000 bytes; the R reader also limits object count, vector length and nesting.

Every item carries its complete upstream notice and copyright text. Palettetown's original `DESCRIPTION` declares `MIT + file LICENSE`; the year/holder file and the complete MIT permission and disclaimer are retained together. CC0's full original legal text is retained. ColorBrewer carries its full source notice, original extra attribution conditions and the complete Apache 2.0 legal text. CARTO carries the original README attribution and the official complete CC-BY-4.0 legal text. The Apache text is an identical byte copy of the separately audited Apache download in the CSS wave.

ColorBrewer attribution: This product includes color specifications and designs developed by Cynthia Brewer (http://colorbrewer.org/).

CARTO attribution: CARTOColors by CARTO, CC-BY-4.0, https://github.com/CartoDB/CartoColor. Color arrays unchanged.

`discovery.json`, `fetch.json`, `terms.json` and `source-audit.json` preserve retrieval and robots evidence. Raw GitHub's robots file returned 404, recorded as absent. GitHub's root robots file was reviewed; allowed repository-root HTML exposed immutable revisions where API discovery was unavailable. API robots retrieval returned 403 in later collection, so automated API collection stopped; allowed public root/raw routes were used. Creative Commons' robots rules were reviewed before retrieving its legal text. No authentication, paywall or CAPTCHA bypass was used.

Paletteer and pypalettes helped identify original sources, but their aggregate license notices do not license every included palette. Their aggregate data payloads and the unused Beyonce R data/code were removed from distribution. `distribution.json` retains the eight removed paths, byte lengths, hashes and reasons; discovery metadata, README and license-review evidence remain. Directly used original source files and full notices remain in the archive.

## Deterministic offline import

```sh
python scripts/import_color_wave.py --import-items
```

This reads local original source bytes only and makes no network request. `dedup-baseline.json` freezes the pre-color-wave catalog boundary: 2,793 IDs and 1,524 distinct color signatures. The importer verifies that baseline's SHA-256 and never re-derives it from an expanded catalog. Consequently, rebuilding a catalog containing this wave, or later adding unrelated sources, cannot change this wave's output.

Generated JSON is UTF-8 with explicitly fixed LF line endings on every operating system. The 1,454-item output is **14,214,435 bytes**, SHA-256 **`243e8fdbf5f1b7c72f08f4daa899c6cf550cc2471d524d4e95254e1be45bcf10`**. The CRLF-to-LF normalization changed only file separators; all parsed JSON values, palette arrays, complete notices and the original 25 audited source files remained identical. Downloaded source bytes are never normalized.

Deduplication compares exact color multisets against that baseline and earlier palettes in the wave. It expands HEX shorthand and treats an opaque `ff` alpha suffix as its equivalent solid color; repeated colors and array length still count. Equal colors in a different order cannot inflate the asset count, while retained arrays preserve their original order. The five excluded original definitions are recorded in `extraction.json`. IDs are checked against the frozen existing IDs and all newly imported IDs.

`extraction.json` records source counts, exclusions, original artifact hashes, output hash, baseline hash and source-audit hash. The resulting 1,454 entries are all `kind: palette`, `language: json` with supported swatch previews. They introduce no external scripts, media downloads, account data or video files.
