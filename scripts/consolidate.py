"""Apply reviewed, hash-pinned asset groups while preserving every original record."""

from collections import Counter
from copy import deepcopy
import hashlib
import json

from motionlab.validation import validate_id
from scripts.analyze import analyze_items

MODES = {"exact": "exact-source", "motion": "motion-variant",
         "palette": "palette-variant", "component": "motion-variant"}


def code_sha(item):
    return hashlib.sha256((item.get("code") or "").encode("utf-8")).hexdigest()


def record_sha(item):
    """Pin original preview context, colors and notices as well as source code."""
    original = {key: value for key, value in item.items() if key != "analysis"}
    return hashlib.sha256(json.dumps(original, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


def apply_consolidation(items, policy, repairs=None):
    """Return canonical entries, direct legacy aliases and deterministic accounting.

    The policy is an explicit review artifact, never a fuzzy match at build time.
    Palette groups are connected exploration families; colors/order/alpha stay exact.
    Component repairs are verified against pinned source files by the build caller.
    """
    if not isinstance(policy, dict) or policy.get("version") != 1:
        raise ValueError("Unsupported consolidation policy")
    groups = policy.get("groups")
    if not isinstance(groups, list) or len(groups) > 10_000:
        raise ValueError("Invalid consolidation groups")
    by_id = {validate_id(item.get("id")): item for item in items}
    if len(by_id) != len(items) or any("variants" in item or "consolidation" in item for item in items):
        raise ValueError("Consolidation requires unique, original input records")
    repairs = repairs or {"version": 1, "repairs": []}
    if (not isinstance(repairs, dict) or repairs.get("version") != 1
            or not isinstance(repairs.get("repairs"), list) or len(repairs["repairs"]) > 10_000):
        raise ValueError("Invalid component repairs")
    repair_map = {}
    for repair in repairs["repairs"]:
        if not isinstance(repair, dict):
            raise ValueError("Each component repair must be an object")
        identifier = validate_id(repair.get("id"))
        if identifier in repair_map:
            raise ValueError("Duplicate component repair")
        repair_map[identifier] = repair
    positions = {item["id"]: index for index, item in enumerate(items)}
    claimed, aliases, parents, summaries, applied_repairs = set(), {}, {}, [], set()
    removed = Counter()
    for group in groups:
        if not isinstance(group, dict) or group.get("mode") not in MODES:
            raise ValueError("Invalid consolidation mode")
        ids = group.get("ids")
        if not isinstance(ids, list) or not 2 <= len(ids) <= 64:
            raise ValueError("Each group needs 2 to 64 original IDs")
        for identifier in ids:
            validate_id(identifier)
        if len(set(ids)) != len(ids) or claimed.intersection(ids) or any(identifier not in by_id for identifier in ids):
            raise ValueError("Overlapping, repeated or missing consolidation IDs")
        ordered = sorted(ids, key=positions.__getitem__)
        canonical = validate_id(group.get("id"))
        if canonical != ordered[0]:
            raise ValueError("Canonical ID must be the first original catalog record")
        fingerprints = group.get("expectedCodeSha256")
        if not isinstance(fingerprints, dict) or set(fingerprints) != set(ids) or any(
                fingerprints[identifier] != code_sha(by_id[identifier]) for identifier in ids):
            raise ValueError("Consolidation source body changed; review the group again")
        record_fingerprints = group.get("expectedRecordSha256")
        if not isinstance(record_fingerprints, dict) or set(record_fingerprints) != set(ids) or any(
                record_fingerprints[identifier] != record_sha(by_id[identifier]) for identifier in ids):
            raise ValueError("Consolidation source context or notice changed; review the group again")
        if len({by_id[identifier]["kind"] for identifier in ids}) != 1:
            raise ValueError("A group cannot combine different asset kinds")
        if group["mode"] == "palette" and any(by_id[identifier]["kind"] != "palette" for identifier in ids):
            raise ValueError("Palette groups require palette records")
        base = deepcopy(by_id[canonical])
        roles = {identifier: MODES[group["mode"]] for identifier in ordered}
        if group["mode"] == "component":
            repair = repair_map.get(canonical)
            if repair is None or repair.get("expectedCodeSha256") != code_sha(base):
                raise ValueError("Missing or stale complete-component repair")
            if set(repair.get("absorbedIds", [])) != set(ids) - {canonical} or repair.get("expectedAbsorbedCodeSha256") != {
                    identifier: code_sha(by_id[identifier]) for identifier in ids if identifier != canonical}:
                raise ValueError("Component repair does not cover the exact original parts")
            replacement = repair.get("replacement")
            if not isinstance(replacement, dict) or set(replacement) != {"code", "preview", "description", "licenseText", "colors"}:
                raise ValueError("Component repair may only replace approved asset fields")
            base.update(deepcopy(replacement))
            base = analyze_items([base])[0]
            roles.update({identifier: "component-part" for identifier in ids if identifier != canonical})
            applied_repairs.add(canonical)
        variants = [deepcopy(base if identifier == canonical else by_id[identifier]) for identifier in ordered]
        parent = deepcopy(base)
        parent["aliases"] = [identifier for identifier in ordered if identifier != canonical]
        parent["variants"] = variants
        parent["consolidation"] = {
            "version": 1, "mode": group["mode"], "memberIds": ordered,
            "variantCount": sum(role != "component-part" for role in roles.values()),
            "variantRoles": roles, "relations": deepcopy(group.get("relations", [])),
            "originalCodeSha256": deepcopy(fingerprints),
            "groupingBasis": "reviewed-connected-family" if group["mode"] == "palette" else "reviewed-source-structure",
            "allMembersPairwiseEquivalent": False,
        }
        if group["mode"] == "component":
            parent["repair"] = {key: deepcopy(value) for key, value in repair.items()
                                if key not in ("replacement", "absorbedIds")}
            parent["repair"]["originalRecord"] = deepcopy(by_id[canonical])
        for identifier in parent["aliases"]:
            aliases[identifier] = canonical
        parents[canonical] = parent
        claimed.update(ids)
        removed[group["mode"]] += len(ids) - 1
        summaries.append({"id": canonical, "mode": group["mode"], "memberIds": ordered,
                          "removedCards": len(ids) - 1, "variantCount": parent["consolidation"]["variantCount"]})
    if applied_repairs != set(repair_map):
        raise ValueError("A component repair was not included in the reviewed policy")
    output = [parents.get(item["id"], item) for item in items if item["id"] not in aliases]
    report = {"version": 1, "before": len(items), "after": len(output), "removedCards": len(aliases),
              "removedByMode": dict(sorted(removed.items())), "groups": summaries,
              "mergedGroups": len(parents), "repairedCompositions": len(applied_repairs),
              "variantRecords": sum(len(item["variants"]) for item in parents.values()),
              "renderableVariants": sum(item["consolidation"]["variantCount"] for item in parents.values()),
              "aliases": aliases, "originalIdentitiesPreserved": len(output) + len(aliases),
              "originalRecordsPreserved": True, "originalPaletteArraysPreserved": True,
              "sourceNoticesPreserved": True, "browserExecutionVerified": False}
    return output, aliases, report
