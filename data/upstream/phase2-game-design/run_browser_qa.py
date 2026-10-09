"""Run only owned local SVG source review or final loopback QA."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import time

parser = argparse.ArgumentParser()
parser.add_argument("--offset", type=int)
parser.add_argument("--http", action="store_true")
parser.add_argument("--comparison", action="store_true")
args = parser.parse_args()
root = Path.cwd().resolve()
local = root / "data/upstream/phase2-game-design"
source = root / "data/phase2-game-design-items.json" if args.http else local / "candidates.json"
assert args.offset is None or 0 <= args.offset < 199
assert not args.comparison or (not args.http and args.offset is None)
name = "composition-comparison" if args.comparison else "final-http" if args.http else "game-review-all" if args.offset is None else f"game-review-{args.offset:03d}"
profile = root / ".cache/phase2-game-design-qa" / name
url = "http://127.0.0.1:8791/_preview-qa.html?prefix=phase2-game-design&renderer=svg" if args.http else (local / ("composition-comparison-qa.html" if args.comparison else "game-review-qa.html")).as_uri()
if args.offset is not None: url += f"?offset={args.offset}&count=24"
renderer = hashlib.sha256((root / "dist/preview.js").read_bytes()).hexdigest()
input_sha = hashlib.sha256(source.read_bytes()).hexdigest()
output, error = local / (name + ".html"), local / (name + ".stderr.txt")
command = ["C:/Program Files/Google/Chrome/Application/chrome.exe", "--headless=new", "--no-first-run", "--disable-background-networking", f"--user-data-dir={profile}", "--dump-dom", "--virtual-time-budget=" + ("40000" if args.http else "4000"), "--window-size=1040,1100"]
if args.offset is not None or args.comparison: command.append(f"--screenshot={local / (name + '.png')}")
command.append(url)
with output.open("wb") as out, error.open("wb") as err:
    process = subprocess.Popen(command, stdout=out, stderr=err)
    deadline = time.monotonic() + 30
    completed_dump = False
    while time.monotonic() < deadline:
        if output.exists() and output.stat().st_size > 0:
            raw = output.read_text(encoding="utf-8", errors="replace")
            completed_dump = 'data-complete="true"' in raw and '</html>' in raw
            if completed_dump: break
        if process.poll() is not None: break
        time.sleep(.1)
    natural_exit = process.poll() is not None
    if not natural_exit:
        # Only this Popen-owned headless process is terminated after the complete
        # trusted QA DOM has been dumped. Browser exit can stall on Windows.
        process.terminate()
    process.wait(timeout=10)
assert completed_dump, "No complete actual browser QA report was emitted"
assert renderer == hashlib.sha256((root / "dist/preview.js").read_bytes()).hexdigest() and input_sha == hashlib.sha256(source.read_bytes()).hexdigest(), "QA inputs changed during execution"
metadata = {"rendererSha256": renderer, "inputPath": source.relative_to(root).as_posix(), "inputSha256": input_sha, "browserOutputSha256": hashlib.sha256(output.read_bytes()).hexdigest(), "sourceJavaScriptExecuted": False, "temporalFramesCompared": False, "completeBrowserDomObserved": True, "browserExitWasNatural": natural_exit, "ownedProcessTerminatedAfterCompleteDump": not natural_exit}
output.with_suffix(".meta.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"output": output.relative_to(root).as_posix(), **metadata}))
