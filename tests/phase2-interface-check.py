"""Compare real qualified records through CLI, loopback HTTP and MCP stdio."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from urllib.parse import urlencode
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parents[1]
MAX_RESPONSE = 8 * 1024 * 1024


def cli(*arguments):
    completed = subprocess.run([sys.executable, "-m", "motionlab", *arguments],
                               cwd=ROOT, capture_output=True, timeout=60, check=True)
    if len(completed.stdout) > MAX_RESPONSE:
        raise ValueError("CLI response exceeds test bound")
    return json.loads(completed.stdout)


def http(origin, path):
    with urlopen(origin + path, timeout=30) as response:
        body = response.read(MAX_RESPONSE + 1)
    if len(body) > MAX_RESPONSE:
        raise ValueError("HTTP response exceeds test bound")
    return json.loads(body)


def run(port):
    if not 1 <= port <= 65535:
        raise ValueError("Invalid loopback port")
    raw = (ROOT / "data/catalog.json").read_bytes()
    catalog = json.loads(raw)
    items = catalog["items"]
    prefixes = ("phase2-motion-", "phase2-design-", "phase2-material-", "phase2-game-design-")
    selected = []
    for prefix in prefixes:
        # The source collectors use different IDs, so input membership is authoritative.
        filename = {"phase2-motion-": "phase2-motion-items.json",
                    "phase2-design-": "phase2-design-items.json",
                    "phase2-material-": "phase2-material-items.json",
                    "phase2-game-design-": "phase2-game-design-items.json"}[prefix]
        path = ROOT / "data" / filename
        if not path.exists():
            continue
        qualified = json.loads(path.read_bytes())
        if qualified:
            identifier = qualified[0]["id"]
            selected.append(next(item for item in items if item["id"] == identifier))
    if not selected:
        raise ValueError("No qualified source records")
    checks = []
    origin = f"http://127.0.0.1:{port}"
    for interface, stats in (("CLI", cli("stats")), ("HTTP", http(origin, "/api/stats"))):
        if stats["storedAssets"] != catalog["stats"]["storedAssets"] or stats["domains"] != catalog["stats"]["domains"]:
            raise ValueError(interface + " stats differ from the final catalog")
        checks.append(interface + " final domain counts")
    for domain, count in catalog["stats"]["domains"].items():
        arguments = {"domain": domain, "limit": 1}
        for interface, result in (("CLI", cli("search", "--domain", domain, "--limit", "1", "--json")),
                                  ("HTTP", http(origin, "/api/search?" + urlencode(arguments)))):
            if result["total"] != count or any(item["analysis"]["domain"] != domain for item in result["items"]):
                raise ValueError(interface + " domain filter differs")
            checks.append(interface + " " + domain + " filter")
    for item in selected:
        if cli("get", item["id"], "--json") != item or http(origin, "/api/items/" + item["id"]) != item:
            raise ValueError("Original fields or license differ: " + item["id"])
        checks.append("CLI/HTTP complete source and notice: " + item["id"])
    requests = [{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
        "protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "motionlab-phase2-qa", "version": "1"}}}]
    requests.extend({"jsonrpc": "2.0", "id": index + 2, "method": "tools/call", "params": {
        "name": "get_motion", "arguments": {"id": item["id"]}}} for index, item in enumerate(selected))
    requests.extend({"jsonrpc": "2.0", "id": len(selected) + index + 2, "method": "tools/call", "params": {
        "name": "search_motion", "arguments": {"domain": domain, "limit": 1}}}
        for index, domain in enumerate(catalog["stats"]["domains"]))
    wire = b"".join(json.dumps(request).encode("utf-8") + b"\n" for request in requests)
    completed = subprocess.run([sys.executable, "-m", "motionlab", "mcp"], cwd=ROOT,
                               input=wire, capture_output=True, timeout=60, check=True)
    if len(completed.stdout) > MAX_RESPONSE:
        raise ValueError("MCP response exceeds test bound")
    replies = [json.loads(line) for line in completed.stdout.splitlines()]
    if len(replies) != len(requests) or any("error" in reply for reply in replies):
        raise ValueError("MCP protocol failure")
    for reply, item in zip(replies[1:1 + len(selected)], selected):
        if reply["result"].get("isError") or reply["result"]["structuredContent"] != item:
            raise ValueError("MCP original fields or notice differ")
        checks.append("MCP complete source and notice: " + item["id"])
    for reply, (domain, count) in zip(replies[1 + len(selected):], catalog["stats"]["domains"].items()):
        result = reply["result"]["structuredContent"]
        if result["total"] != count or any(item["analysis"]["domain"] != domain for item in result["items"]):
            raise ValueError("MCP domain filter differs")
        checks.append("MCP " + domain + " filter")
    if (ROOT / "data/catalog.json").read_bytes() != raw:
        raise ValueError("Catalog changed during interface checks")
    report = {"complete": True, "catalogSha256": hashlib.sha256(raw).hexdigest(),
              "storedAssets": catalog["stats"]["storedAssets"], "domains": catalog["stats"]["domains"],
              "checks": checks, "selectedIds": [item["id"] for item in selected],
              "scope": "Actual final catalog through separate CLI/MCP processes and existing loopback HTTP server; no external AI-client configuration."}
    (ROOT / "data/phase2-interface-qa.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(report))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8791)
    run(parser.parse_args().port)
