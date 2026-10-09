"""Verify expanded source records across full JSON, compact JSON and read-only SQLite."""

import argparse
from collections import Counter
from contextlib import closing
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from motionlab.catalog import Catalog  # noqa: E402
from motionlab.payload_codec import decode_payload  # noqa: E402
from scripts.build import WAVE_INPUTS, compact_catalog_index, deduplicate_items, read_json, validate_item  # noqa: E402
from scripts.expansion import merge_expansion  # noqa: E402

BASE_INPUTS = ("imported-items.json", "research-sources.json", "manual-items.json",
               "glsl-items.json", "jtech-items.json", "expanded-assets.json")
MODES = {"exact": "exact-source", "motion": "motion-variant",
         "palette": "palette-variant", "component": "motion-variant"}


def original_record_views(entries, aliases):
    """Validate group structure and recover every pre-consolidation identity."""
    if not isinstance(aliases, dict) or any(not isinstance(value, str) for value in aliases.values()):
        raise ValueError("Catalog aliases must map directly to canonical IDs")
    by_id = {entry["id"]: entry for entry in entries}
    originals, expected_aliases, groups = {}, {}, []
    for entry in entries:
        identifier = entry["id"]
        validate_item(entry)
        if "consolidation" not in entry:
            if any(key in entry for key in ("variants", "aliases", "repair")):
                raise ValueError("Ungrouped entry carries consolidation fields")
            originals[identifier] = entry
            continue
        consolidation = entry["consolidation"]
        if not isinstance(consolidation, dict) or consolidation.get("version") != 1 or consolidation.get("mode") not in MODES:
            raise ValueError("Unsupported stored consolidation metadata")
        members, variants, roles = consolidation.get("memberIds"), entry.get("variants"), consolidation.get("variantRoles")
        if (not isinstance(members, list) or not 2 <= len(members) <= 64 or len(set(members)) != len(members)
                or members[0] != identifier or not isinstance(variants, list)
                or [variant.get("id") for variant in variants if isinstance(variant, dict)] != members
                or len(variants) != len(members) or not isinstance(roles, dict) or set(roles) != set(members)):
            raise ValueError("Group members, variants or roles disagree")
        if entry.get("aliases") != members[1:] or any(member in by_id for member in members[1:]):
            raise ValueError("Merged members still appear as independent cards")
        mode = consolidation["mode"]
        expected_roles = {member: "component-part" if mode == "component" and member != identifier
                          else MODES[mode] for member in members}
        if roles != expected_roles or consolidation.get("variantCount") != sum(role != "component-part" for role in roles.values()):
            raise ValueError("Renderable variant count or component-part roles disagree")
        if mode == "palette" and any(variant.get("kind") != "palette" for variant in variants):
            raise ValueError("Palette family contains a different asset kind")
        if variants[0] != {key: value for key, value in entry.items()
                           if key not in ("variants", "aliases", "consolidation", "repair")}:
            raise ValueError("Canonical variant is stale or differs from its parent asset")
        for variant in variants:
            validate_item(variant)
            if any(key in variant for key in ("variants", "aliases", "consolidation", "repair")):
                raise ValueError("Nested consolidation variants are forbidden")
            member = variant["id"]
            if member in originals:
                raise ValueError("An original identity occurs in multiple groups")
            originals[member] = variant
            if member != identifier:
                expected_aliases[member] = identifier
        if mode == "component":
            repair = entry.get("repair")
            original = repair.get("originalRecord") if isinstance(repair, dict) else None
            if not isinstance(original, dict) or original.get("id") != identifier:
                raise ValueError("Repaired component lost its original primary record")
            validate_item(original)
            if any(key in original for key in ("variants", "aliases", "consolidation", "repair")):
                raise ValueError("Original repaired record carries nested grouping")
            originals[identifier] = original
        elif "repair" in entry:
            raise ValueError("Only complete components may carry source repair provenance")
        fingerprints = consolidation.get("originalCodeSha256")
        if not isinstance(fingerprints, dict) or set(fingerprints) != set(members) or any(
                fingerprints[member] != hashlib.sha256((originals[member].get("code") or "").encode("utf-8")).hexdigest()
                for member in members):
            raise ValueError("Preserved source record differs from its approved code hash")
        groups.append(entry)
    if aliases != expected_aliases or set(aliases).intersection(by_id):
        raise ValueError("Global alias map does not exactly identify merged members")
    return originals, groups


def reconstruct_inputs(root):
    baseline = deduplicate_items([entry for name in BASE_INPUTS
                                  for entry in read_json(root / "data" / name, [])])
    waves = [(name, read_json(root / "data" / name, [])) for name in WAVE_INPUTS]
    additions, report = merge_expansion(baseline, waves, validate_item)
    return baseline, additions, waves, report


def verify(root=ROOT, minimum=5000, minimum_stored=0):
    if not isinstance(minimum, int) or not 1 <= minimum <= 100_000:
        raise ValueError("Minimum must be between 1 and 100000")
    if not isinstance(minimum_stored, int) or not 0 <= minimum_stored <= 100_000:
        raise ValueError("Stored minimum must be between 0 and 100000")
    root = Path(root).resolve()
    full = read_json(root / "data/catalog.json", {})
    published = read_json(root / "dist/catalog.json", {})
    if full != published:
        raise ValueError("Local and web full catalogs differ")
    entries = full["items"]
    by_id = {entry["id"]: entry for entry in entries}
    if len(entries) < minimum or len(entries) != len(by_id) or full["stats"]["total"] != len(entries):
        raise ValueError("Catalog minimum, unique IDs or recorded count failed")
    stored_entries = [entry for entry in entries if entry.get("kind") != "reference"]
    domains = dict(Counter(entry.get("analysis", {}).get("domain") for entry in stored_entries))
    if (len(stored_entries) < minimum_stored or full["stats"].get("storedAssets") != len(stored_entries)
            or set(domains) - {"motion", "design"} or full["stats"].get("domains") != domains
            or any(entry.get("analysis", {}).get("domain") is not None for entry in entries if entry.get("kind") == "reference")):
        raise ValueError("Stored asset minimum or domain counts failed")
    aliases = full.get("aliases", {})
    original_by_id, groups = original_record_views(entries, aliases)
    baseline, additions, waves, expected_expansion = reconstruct_inputs(root)
    source_by_id = {entry["id"]: entry for entry in baseline + additions}
    if set(source_by_id) != set(original_by_id):
        raise ValueError("Consolidation lost or invented an original input identity")
    for identifier, source in source_by_id.items():
        stored = original_by_id[identifier]
        if any(stored.get(key) != value for key, value in source.items() if key != "analysis"):
            raise ValueError(f"Original input fields or notices changed: {identifier}")
        if stored["kind"] == "palette" and json.loads(stored["code"]) != stored["colors"]:
            raise ValueError("Preserved palette code and exact color array disagree")
    policy_path = root / "data/consolidation-policy.json"
    if groups or policy_path.is_file():
        from scripts.analyze import analyze_items
        from scripts.consolidate import apply_consolidation
        from scripts.repair_components import verify_overlay
        policy = read_json(policy_path, {"version": 1, "groups": []})
        repair_path = root / "data/component-repairs.json"
        repairs = read_json(repair_path, {"version": 1, "repairs": []})
        repair_checks = {}
        if repairs["repairs"]:
            repair_checks = verify_overlay(root, repairs)
        expected_items, expected_aliases, expected_consolidation = apply_consolidation(
            analyze_items(baseline + additions), policy, repairs)
        if entries != expected_items or aliases != expected_aliases:
            raise ValueError("Published grouping or source repair differs from the reviewed policy")
        consolidation_report = read_json(root / "data/consolidation-report.json", {})
        if any(consolidation_report.get(key) != value for key, value in expected_consolidation.items()):
            raise ValueError("Consolidation report is stale")
        if (consolidation_report.get("componentSourceChecks") != repair_checks
                or (policy_path.is_file() and consolidation_report.get("policySha256") != hashlib.sha256(policy_path.read_bytes()).hexdigest())):
            raise ValueError("Consolidation policy or source-check report fingerprint is stale")
    report = read_json(root / "data/expansion-report.json", {})
    if any(report.get(key) != value for key, value in expected_expansion.items()):
        raise ValueError("Expansion input accounting or exclusion trace is stale")
    excluded = {entry["id"]: entry for entry in report.get("excluded", [])}
    added = 0
    input_counts = {}
    for name, inputs in waves:
        input_counts[name] = len(inputs)
        for source in inputs:
            if source["id"] in excluded:
                if source["id"] in original_by_id or excluded[source["id"]]["sameAs"] not in original_by_id:
                    raise ValueError("Duplicate exclusion does not identify a retained entry")
                continue
            stored = original_by_id.get(source["id"])
            if stored is None or any(stored.get(key) != value for key, value in source.items() if key != "analysis"):
                raise ValueError(f"Source record changed or missing: {source['id']}")
            if not stored.get("licenseText") or stored["kind"] == "reference":
                raise ValueError("Expansion asset lacks notice or is only a discovery link")
            if stored["kind"] == "palette" and json.loads(stored["code"]) != stored["colors"]:
                raise ValueError("Stored palette code and colors disagree")
            added += 1
    original_total = len(original_by_id)
    if (report["added"] != added or report["baseline"] + added != original_total
            or report.get("total") != original_total
            or report.get("publishedTotal", original_total) != len(entries)
            or original_total != len(entries) + len(aliases)):
        raise ValueError("Expansion accounting does not match published records")
    compact = read_json(root / "dist/catalog-index.json", {})
    if compact != compact_catalog_index(full):
        raise ValueError("Compact index has stale counts, aliases, variants or discovery fields")
    alias_path = root / "dist/catalog-aliases.json"
    expected_static_aliases = {"version": 1, "updatedAt": full["updatedAt"], "aliases": aliases}
    if (aliases or alias_path.is_file()) and read_json(alias_path, {}) != expected_static_aliases:
        raise ValueError("Static legacy alias map is stale")
    collections = []
    for domain in ("motion", "design"):
        if not (root / "dist/collections" / ("domain-" + domain + ".json")).is_file():
            raise ValueError("A required domain collection is missing")
    for path in (root / "dist/collections").glob("*.json"):
        subset = read_json(path, [])
        if path.stem in ("domain-motion", "domain-design"):
            expected = [entry for entry in entries if entry["kind"] != "reference" and entry["analysis"]["domain"] == path.stem[7:]]
            if subset != expected:
                raise ValueError("A domain collection is stale")
            continue
        if any(entry["category"] != path.stem or entry != by_id.get(entry["id"]) for entry in subset):
            raise ValueError("A source category collection is stale")
        collections.extend(entry["id"] for entry in subset)
    if len(collections) != len(entries) or set(collections) != set(by_id):
        raise ValueError("Collections do not partition the catalog")
    catalog = Catalog(root)
    if catalog.stats() != full["stats"]:
        raise ValueError("Read-only SQLite metadata is stale")
    with closing(catalog.connection()) as connection:
        rows = connection.execute("SELECT id,payload FROM items").fetchall()
        if len(rows) != len(entries) or any(decode_payload(row["payload"]) != by_id[row["id"]] for row in rows):
            raise ValueError("Read-only SQLite source records are stale")
        if connection.execute("PRAGMA quick_check").fetchone()[0] != "ok":
            raise ValueError("SQLite integrity check failed")
        alias_table = connection.execute("SELECT 1 FROM sqlite_master WHERE type = ? AND name = ?",
                                         ("table", "aliases")).fetchone()
        if aliases and not alias_table:
            raise ValueError("Read-only SQLite alias table is missing")
        if alias_table:
            alias_rows = connection.execute("SELECT alias,item_id,variant_id FROM aliases").fetchall()
            if ({row["alias"]: row["item_id"] for row in alias_rows} != aliases
                    or len(alias_rows) != len(aliases)
                    or any(row["variant_id"] != row["alias"] for row in alias_rows)):
                raise ValueError("Read-only SQLite aliases do not match the direct static alias map")
    for legacy_id, canonical in aliases.items():
        source = source_by_id[legacy_id]
        resolved = catalog.get(legacy_id)
        parent = by_id[canonical]
        role = parent["consolidation"]["variantRoles"][legacy_id]
        if (not isinstance(resolved, dict) or resolved.get("canonicalId") != canonical
                or resolved.get("variantRole") != role
                or any(resolved.get(key) != value for key, value in source.items() if key != "analysis")):
            raise ValueError(f"Legacy get lost original fields, arrays, notice or canonical target: {legacy_id}")
    for kind, count in full["stats"]["kinds"].items():
        result = catalog.search(kind=kind, limit=100, offset=max(0, count - 100))
        if result["total"] != count or not result["items"]:
            raise ValueError("Search filtering or last-page offset failed")
    for domain, count in full["stats"].get("domains", {}).items():
        result = catalog.search(domain=domain, limit=100)
        expected_count = sum(entry["analysis"]["domain"] == domain for entry in entries)
        if result["total"] != expected_count or any(entry["analysis"]["domain"] != domain for entry in result["items"]):
            raise ValueError("Domain search filtering failed")
    for entry in entries:
        if entry["kind"] == "image":
            from motionlab.image_assets import validate_image
            validate_image(entry["image"], root / "dist")
    return {"verifiedAt": full["updatedAt"], "total": len(entries), "storedAssets": len(stored_entries),
            "domains": domains, "minimumStored": minimum_stored, "originalIdentities": original_total,
            "mergedGroups": len(groups), "aliases": len(aliases),
            "variantRecords": sum(len(entry["variants"]) for entry in groups),
            "repairedCompositions": sum(entry["consolidation"]["mode"] == "component" for entry in groups),
            "added": added,
            "inputCounts": input_counts, "excluded": len(excluded), "kinds": full["stats"]["kinds"],
            "codeLanguages": dict(Counter(entry["language"] for entry in entries if entry["kind"] == "code")),
            "checks": ["minimum", "stored-minimum-and-domain-counts", "schema", "unique-ids", "full-source-fields-and-notices",
                       "palette-code-equals-colors", "all-original-input-identities", "reviewed-consolidation-policy",
                       "pinned-source-component-repairs", "full-web-json", "compact-index", "static-alias-map",
                       "all-category-collections", "domain-collections", "image-files-and-digests",
                       "read-only-sqlite-records", "sqlite-aliases",
                       "legacy-get-preserves-original-source", "sqlite-integrity", "search-last-page", "domain-search"],
            "catalogSha256": hashlib.sha256((root / "dist/catalog.json").read_bytes()).hexdigest()}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--minimum", type=int, default=5000)
    parser.add_argument("--minimum-stored", type=int, default=0, help="Minimum stored assets, excluding reference links")
    options = parser.parse_args()
    try:
        result = verify(options.root, options.minimum, options.minimum_stored)
        (options.root / "data/verification-report.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n")
        print(json.dumps(result))
    except (OSError, ValueError, KeyError) as error:
        print(f"Catalog verification failed: {error}", file=sys.stderr)
        sys.exit(1)
