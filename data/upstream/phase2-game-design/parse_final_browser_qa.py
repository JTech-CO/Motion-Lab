"""Motion Lab authored parser for the completed trusted loopback QA report."""
import hashlib
import json
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path.cwd().resolve()
LOCAL = ROOT / "data/upstream/phase2-game-design"
class ResultParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.capture = False
        self.parts = []
        self.complete = False
    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == "pre" and values.get("id") == "result":
            self.capture = True
            self.complete = values.get("data-complete") == "true"
    def handle_endtag(self, tag):
        if tag == "pre": self.capture = False
    def handle_data(self, text):
        if self.capture: self.parts.append(text)

raw = (LOCAL / "final-http.html").read_bytes()
parser = ResultParser()
parser.feed(raw.decode("utf-8"))
assert parser.complete, "Actual trusted HTTP QA never completed"
report = json.loads("".join(parser.parts))
metadata = json.loads((LOCAL / "final-http.meta.json").read_text(encoding="utf-8"))
input_path = ROOT / "data/phase2-game-design-items.json"
items = json.loads(input_path.read_text(encoding="utf-8"))
assert metadata["inputSha256"] == hashlib.sha256(input_path.read_bytes()).hexdigest()
assert metadata["rendererSha256"] == hashlib.sha256((ROOT / "dist/preview.js").read_bytes()).hexdigest()
assert metadata["browserOutputSha256"] == hashlib.sha256(raw).hexdigest()
assert report["complete"] and report["total"] == report["ready"] == len(items)
assert report["byRenderer"] == {"svg": {"total": len(items), "ready": len(items)}}
assert not report["failures"] and all(report["security"].values())
assert len(report["security"]) >= 18
assert report["shaderEndpointChecks"] == 0
assert all(value == 0 for value in report["diagnostics"].values())
result = {**report, **metadata, "securityCheckCount": len(report["security"]),
          "qaFixtureJavaScriptSha256": hashlib.sha256((ROOT / "dist/_preview-qa.js").read_bytes()).hexdigest(),
          "scope": "All retained static originals used the actual browser renderer; independent 191-original DOM/attribute inventory and source composition review are separate evidence. No universal visual or temporal frame uniqueness claim."}
(LOCAL / "final-renderer-qa.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n")
print(json.dumps({key: result[key] for key in ("total", "ready", "securityCheckCount", "inputSha256", "rendererSha256")}))
