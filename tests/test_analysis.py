"""Behavioral regression tests for source-derived analysis, not name matching."""

from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from motionlab.catalog import Catalog
from motionlab.mcp import MCPServer
from motionlab.validation import ValidationError
from scripts.analyze import analyze_item, analyze_items
from scripts.build import build


PROJECT = Path(__file__).resolve().parent.parent


def asset(code, language="css", category="animation", **extra):
    return {"id": "structural-asset", "title": "Plain unnamed component", "description": "An inspected asset.",
            "sourceName": "Fixture", "sourceUrl": "https://example.org/component", "license": "MIT",
            "licenseText": "A complete fixture notice", "verifiedAt": "2026-10-08",
            "verification": "source-and-license-reviewed", "access": "public", "tags": [], "colors": [],
            "category": category, "kind": "code", "language": language, "code": code,
            "preview": {"type": "svg" if language == "svg" else "css" if language == "css" else "reference", "variant": "source"}, **extra}


class AnalysisTest(unittest.TestCase):
    def test_reviewed_raster_shapes_keep_their_facet_without_inferred_motion(self):
        image = {"path": "assets/materials/reviewed-illustration.jpg", "mime": "image/jpeg",
                 "width": 1024, "height": 640, "sha256": "a" * 64, "sourceSha256": "b" * 64}
        item = asset(None, "image", "shape", kind="image", image=image,
                     title="Rotating particle shader", tags=["rotate", "glsl", "stroke"])
        result = analyze_item(item)
        self.assertEqual(result["assetType"], "shape")
        self.assertEqual(result["domain"], "design")
        self.assertEqual(result["components"], ["shape", "image"])
        self.assertEqual(result["effects"], [])
        self.assertEqual(result["preview"]["renderer"], "image")
        self.assertEqual(result["evidence"]["basis"], "image")
        self.assertNotIn("stroke", result["properties"])
        self.assertNotIn("svg-geometry", result["techniques"])
        self.assertEqual(analyze_item({**item, "category": "material"})["assetType"], "material")
        invalid = {**item, "image": {**image, "sha256": "<script>"}}
        self.assertEqual(analyze_item(invalid)["preview"]["renderer"], "none")

    def test_decorative_content_is_shape_and_does_not_relabel_a_loader(self):
        for initial, final in [('""', '" "'), ('"⚽"', '"🏀"'), ('"\\2022"', '"\\263a"')]:
            result = analyze_item(asset('@keyframes a {from {content:' + initial + ';transform:translateX(0)} to {content:' + final + ';transform:translateX(20px)}} .part{animation:a 1s}', category="loader"))
            self.assertEqual(result["assetType"], "loader")
            self.assertNotIn("text", result["effects"])
            self.assertNotIn("text", result["components"])
        result = analyze_item(asset('@keyframes a {from{content:"LOADING"}to{content:"READY"}} .part{animation:a 1s}', category="loader"))
        self.assertEqual(result["assetType"], "loader")
        self.assertIn("text", result["components"])

    def test_function_names_inside_content_are_text_not_operations(self):
        result = analyze_item(asset('''@keyframes a {from {content:"translateX(5px) blur(3px)"}
          to {content:"rotate(90deg) linear-gradient(#fff,#000)"}}
          .motion-sample::after {content:"begin";animation:a 1s}'''))
        self.assertEqual(result["effects"], ["text"])
        self.assertNotIn("gradient", result["techniques"])
        self.assertNotIn("blur", result["effects"])

    def test_grouped_frames_are_sorted_and_centering_is_not_a_grid_component(self):
        result = analyze_item(asset('''@keyframes a {0%,100% {opacity:1} 50%{opacity:.3}}
          .motion-sample {display:grid;place-items:center;animation:a 1s infinite}'''))
        self.assertIn("pulse", result["effects"])
        self.assertNotIn("grid", result["components"])

    def test_animated_gradient_is_code_and_textured_background_is_a_grid(self):
        result = analyze_item(asset('''@keyframes a {from{background-position:0 0}to{background-position:50px 50px}}
          .motion-sample {background:repeating-conic-gradient(#123 0% 25%,#456 0% 50%) 0 0 / 50px 50px;
          animation:a 1s infinite}''', category="gradient", colors=["#112233", "#445566"]))
        self.assertEqual(result["evidence"]["basis"], "code")
        self.assertIn("slide", result["effects"])
        self.assertIn("pixel", result["effects"])
        self.assertIn("grid", result["components"])
        self.assertIn("ambient", result["useCases"])

    def test_css_properties_ignore_brand_names_comments_and_fallback(self):
        item = asset('''/* fade zoom blur title is not a declaration */
            @keyframes a { from {transform:translateX(-40px)} to {transform:translateX(0px)} }
            .part {animation:a 1s ease; width:20px; height:20px}
            @media (prefers-reduced-motion: reduce) {.part {opacity:1;filter:blur(0);clip-path:none}}
            ''', title="FADE ZOOM BLUR")
        result = analyze_item(item)
        self.assertEqual(result["effects"], ["slide"])
        self.assertNotIn("clip-path", result["properties"])
        self.assertNotIn("mask", result["components"])
        self.assertIn("keyframes", result["techniques"])
        self.assertEqual(result["evidence"]["basis"], "code")
        self.assertEqual(result["preview"]["selectors"], [".part"])

    def test_css_interaction_text_stagger_and_overshoot(self):
        result = analyze_item(asset('''@keyframes a {0% {letter-spacing:0;transform:scale(.8)}
            60% {letter-spacing:5px;transform:scale(1.2)} 100% {letter-spacing:1px;transform:scale(1)}}
            .motion-sample {animation:a 1s cubic-bezier(.3,1.3,.5,1);animation-delay:0s}
            .motion-sample::after {content:"READY";animation-delay:.3s}
            .motion-sample:hover {opacity:.5;transform:translateY(-2px)}'''))
        self.assertEqual(result["assetType"], "interaction")
        for effect in ("text", "spring", "stagger", "scale", "slide", "fade"):
            self.assertIn(effect, result["effects"])
        self.assertIn("feedback", result["useCases"])
        self.assertIn("pseudo-element", result["techniques"])
        self.assertEqual(result["preview"]["dom"], {"tag": "div", "className": "motion-sample"})

    def test_multi_dom_structure_is_bounded_and_preserved(self):
        dom = {"tag": "div", "className": "ball-pulse", "children": [{"tag": "div"}] * 3}
        item = asset('.ball-pulse > div {width:12px;animation:part 1s infinite}', category="loader",
                     preview={"type": "css", "variant": "source", "dom": dom})
        original = deepcopy(item)
        analyzed = analyze_items([item])[0]
        self.assertEqual(analyzed["analysis"]["preview"]["dom"], dom)
        self.assertEqual({key: value for key, value in analyzed.items() if key != "analysis"}, original)
        self.assertEqual(item, original)
        item["preview"]["dom"] = {"tag": "script", "text": "bad"}
        self.assertNotIn("dom", analyze_item(item)["preview"])
        item["preview"]["dom"] = {"tag": "div", "children": [{"tag": "div"}] * 49}
        self.assertNotIn("dom", analyze_item(item)["preview"])

    def test_glsl_actual_operations_and_uniforms(self):
        code = '''// noise rotate in a comment is not an operation
          uniform float smoothness; uniform vec2 direction;
          vec4 transition(vec2 p) {
            float x=smoothstep(0.,1.,progress);
            return mix(getFromColor((p-.5)*(1.-x)+.5),getToColor((p-.5)*x+.5),x);
          }'''
        result = analyze_item(asset(code, "glsl", "transition", title="Unknown Example"))
        self.assertEqual(result["effects"], ["fade", "scale", "mask"])
        self.assertEqual(result["components"], ["image", "mask", "layer"])
        self.assertIn("texture-sampling", result["techniques"])
        self.assertNotIn("procedural-noise", result["techniques"])
        self.assertEqual(result["preview"]["uniforms"], [{"type": "float", "name": "smoothness"}, {"type": "vec2", "name": "direction"}])

    def test_svg_actual_elements_and_animation_attributes(self):
        code = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 50 50"><g>
          <circle cx="25" cy="25" r="20" stroke="#fff" stroke-dasharray="20 100">
          <animate attributeName="stroke-dashoffset" values="0;120" dur="1s" repeatCount="indefinite"/>
          <animateTransform attributeName="transform" type="rotate" from="0 25 25" to="360 25 25" dur="1s"/>
          </circle></g></svg>'''
        result = analyze_item(asset(code, "svg", "loader"))
        self.assertEqual(result["effects"], ["rotate", "mask"])
        self.assertEqual(result["components"], ["shape", "stroke", "layer"])
        self.assertEqual(result["preview"]["renderer"], "svg")
        self.assertEqual(result["preview"]["elements"]["circle"], 1)
        self.assertIn("status", result["useCases"])
        self.assertIn("svg-animation", result["techniques"])

    def test_procedural_fragment_is_ambient_shader_without_transition_images(self):
        code = 'vec4 transition(vec2 uv){return vec4(sin(progress+uv.x),0.,0.,1.);}'
        result = analyze_item(asset(code, "glsl", "shader", preview={"type":"reference","variant":"procedural-glsl","scene":"procedural"}))
        self.assertEqual(result["assetType"], "shader")
        self.assertEqual(result["useCases"], ["ambient"])
        self.assertIn("color", result["components"])
        self.assertEqual(result["preview"]["scene"], "procedural")
        self.assertNotIn("two input images", result["preview"]["limitations"][0])
        textured = analyze_item(asset('vec4 transition(vec2 uv){return getFromColor(uv);}', "glsl", "transition", preview={"type":"reference","variant":"procedural-glsl","scene":"procedural"}))
        self.assertEqual(textured["assetType"], "transition")

    def test_untrusted_xml_and_unbalanced_css_do_not_supply_code_evidence(self):
        for code, language in [("<!DOCTYPE svg [<!ENTITY x 'value'>]><svg>&x;</svg>", "svg"),
                               (".part {animation:x 1s;", "css"), ("/*never closed", "css")]:
            result = analyze_item(asset(code, language))
            self.assertNotEqual(result["evidence"]["basis"], "code")
            self.assertEqual(result["preview"]["renderer"], "none")
            self.assertEqual(result["effects"], [])

    def test_color_values_and_references_have_distinct_evidence(self):
        item = asset('{"colors":["#112233"]}', "json", "palette", kind="palette", colors=["#112233"])
        result = analyze_item(item)
        self.assertEqual(result["evidence"]["basis"], "color-values")
        self.assertEqual(result["effects"], [])
        self.assertEqual(result["useCases"], ["color-system"])
        reference = asset(None, "link", "reference", kind="reference", title="Zoom flip particles",
                          tags=["slide", "wave"], colors=["#112233"], verification="link-reviewed")
        result = analyze_item(reference)
        self.assertEqual(result["evidence"]["basis"], "metadata")
        self.assertEqual(result["evidence"]["confidence"], "low")
        self.assertEqual(result["effects"], [])
        self.assertEqual(result["components"], [])
        self.assertEqual(result["preview"]["renderer"], "none")

    def test_structural_search_facets_mcp_and_authoritative_expansion(self):
        with tempfile.TemporaryDirectory(dir=PROJECT / "tests") as directory:
            root = Path(directory)
            (root / "data").mkdir()
            first = asset('@keyframes a {from{clip-path:inset(0 100% 0 0)}to{clip-path:inset(0)}} .part{animation:a 1s}', category="transition")
            second = asset('<svg xmlns="http://www.w3.org/2000/svg"><circle r="10"/></svg>', "svg", "loader",
                           id="svg-part", sourceUrl="https://example.org/svg")
            (root / "data" / "imported-items.json").write_text(json.dumps([first]), encoding="utf-8")
            (root / "data" / "expanded-assets.json").write_text(json.dumps([second]), encoding="utf-8")
            self.assertEqual(build(root)["total"], 2)
            catalog = Catalog(root)
            self.assertEqual(catalog.search(query="clip-path", effect="mask", component="mask", basis="code")["total"], 1)
            self.assertEqual(catalog.search(asset_type="loader", component="shape")["total"], 1)
            self.assertEqual(catalog.search(use_case="scene-change")["total"], 1)
            self.assertEqual(catalog.search(effect="mask", component="image")["total"], 0)
            for arguments in ({"effect": "mask' OR 1=1 --"}, {"component": ["shape"]}, {"basis": "title"}):
                with self.assertRaises(ValidationError):
                    catalog.search(**arguments)
            server = MCPServer(catalog)
            payload = server.call_tool("search_motion", {"effect": "mask"})["structuredContent"]
            self.assertEqual(payload["items"][0]["analysis"]["effects"], ["mask"])
            self.assertEqual(catalog.get(first["id"])["licenseText"], first["licenseText"])
            (root / "data" / "expanded-assets.json").write_text("[]", encoding="utf-8")
            self.assertEqual(build(root)["total"], 1)
            self.assertIsNone(catalog.get("svg-part"))


if __name__ == "__main__":
    unittest.main()
