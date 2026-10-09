"""Critical source-integrity and novelty gates for static design ingestion."""
import importlib.util
import io
import json
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import import_phase2_design as design


class DesignSafetyTests(unittest.TestCase):
    def test_registered_path_boundary(self):
        for value in ("../escape.svg","C:/outside.svg","safe/../escape.svg","/absolute.svg","safe\\escape.svg"):
            with self.assertRaises(ValueError):
                design.safe_path(value)
        self.assertEqual(str(design.safe_path("icons/outline/acorn.svg")),"icons/outline/acorn.svg")

    def test_source_url_allowlist_and_no_redirect(self):
        collector=design.Collector()
        for url in ("http://codeload.github.com/tabler/tabler-icons/tar.gz/main","https://evil.example/x","https://codeload.github.com@evil.example/x","https://codeload.github.com/tabler/tabler-icons/tar.gz/main","https://heropatterns.com/js/app.js?next=evil"):
            with self.subTest(url=url):
                try:
                    allowed=collector.allowed(url)
                except ValueError:
                    allowed=False
                self.assertFalse(allowed)
        valid="https://codeload.github.com/tabler/tabler-icons/tar.gz/"+design.SOURCES["tabler"]["commit"]
        self.assertTrue(collector.allowed(valid))
        self.assertIsNone(design.NoRedirect().redirect_request(None,None,None,None,None,None))

    def test_active_or_external_svg_is_rejected(self):
        payloads=(
            '<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>',
            '<!DOCTYPE svg [<!ENTITY boom SYSTEM "file:///secret">]><svg/>',
            '<svg><path onclick="steal()" d="M0 0L1 1"/></svg>',
            '<svg><image href="https://example.com/tracker"/></svg>',
            '<svg><path fill="url(https://example.com/paint)" d="M0 0L1 1"/></svg>',
        )
        for payload in payloads:
            with self.subTest(payload=payload),self.assertRaises(ValueError):
                design.svg_root(payload)

    def test_archive_symlink_and_path_escape_are_rejected(self):
        source=design.SOURCES["coolshapes"]
        prefix=source["repo"].split("/")[-1]+"-"+source["commit"]+"/"
        for name,kind in (("LICENSE",tarfile.SYMTYPE),("../LICENSE",tarfile.REGTYPE)):
            buffer=io.BytesIO()
            with tarfile.open(fileobj=buffer,mode="w:gz") as archive:
                info=tarfile.TarInfo(prefix+name);info.type=kind
                if kind==tarfile.SYMTYPE:
                    info.linkname="/outside"
                    archive.addfile(info)
                else:
                    info.size=1;archive.addfile(info,io.BytesIO(b"x"))
            with self.assertRaises(ValueError):
                design.archive_members("coolshapes",buffer.getvalue())

    def test_offline_hash_tampering(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(design,"LOCAL",Path(tmp)):
                artifact=design.record_artifact("coolshapes","LICENSE",b"real notice","https://example.com/")
                source={"slug":"coolshapes","artifacts":[artifact]}
                self.assertEqual(design.verified_bytes(source,"LICENSE"),b"real notice")
                (Path(tmp)/"coolshapes/LICENSE").write_bytes(b"tampered")
                with self.assertRaises(ValueError):
                    design.verified_bytes(source,"LICENSE")

    def test_motion_css_revision_preserves_svg_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);local=root/"data/upstream/phase2-design";local.mkdir(parents=True)
            source=root/"data/phase2-motion-items.json"
            svg={"id":"motion-a","kind":"code","language":"svg","code":"<svg viewBox=\"0 0 24 24\"><circle r=\"4\"/></svg>","codePath":"original/a.svg"}
            css={"id":"motion-b","kind":"code","language":"css","code":".loader{}"}
            with patch.object(design,"ROOT",root),patch.object(design,"LOCAL",local):
                source.write_text(json.dumps([svg,css]),encoding="utf-8")
                before,metadata=design.motion_comparison_records()
                source.write_text(json.dumps([svg]),encoding="utf-8")
                after,revised=design.motion_comparison_records()
                self.assertEqual(before,after)
                self.assertEqual(revised["inputCount"],1)
                self.assertEqual(metadata["sha256"],revised["sha256"])
                changed={**svg,"code":"<svg viewBox=\"0 0 24 24\"><circle r=\"9\"/></svg>"}
                source.write_text(json.dumps([changed]),encoding="utf-8")
                with self.assertRaises(ValueError):
                    design.motion_comparison_records()


class DesignNoveltyTests(unittest.TestCase):
    def test_style_direction_and_tiny_toggle_groups(self):
        for name in ("user","account-add","user-circle","user-check","user-2","person-filled"):
            self.assertEqual(design.icon_family(name),"user")
        self.assertEqual(design.icon_family("arrow-up"),design.icon_family("chevron-left"))
        self.assertEqual(design.icon_family("brand-github"),design.icon_family("github-logo"))
        self.assertEqual(design.icon_family("brand-github"),design.icon_family("github-loop"))
        self.assertEqual(design.icon_family("temperature-celsius"),design.icon_family("thermometer-raindrop"))
        self.assertEqual(design.icon_family("bolt"),design.icon_family("lightning-bolt"))
        self.assertEqual(design.icon_family("drop"),design.icon_family("raindrop"))
        self.assertNotEqual(design.icon_family("acorn"),design.icon_family("anchor"))

    def test_rotation_and_reversal_contour_gate(self):
        if not importlib.util.find_spec("fontTools") or not importlib.util.find_spec("PIL"):
            self.skipTest("Optional importer geometry libraries are unavailable")
        a=design.svg_root('<svg viewBox="0 0 24 24"><path d="M4 4L20 4L4 20Z"/></svg>')
        b=design.svg_root('<svg viewBox="0 0 24 24"><path d="M20 20L4 20L20 4Z"/></svg>')
        c=design.svg_root('<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="8"/></svg>')
        self.assertTrue(design.raster_near(design.geometry_rasters(a),design.geometry_rasters(b)))
        self.assertFalse(design.raster_near(design.geometry_rasters(a),design.geometry_rasters(c)))

    def test_close_then_relative_curve_remains_bounded(self):
        if not importlib.util.find_spec("fontTools") or not importlib.util.find_spec("PIL"):
            self.skipTest("Optional importer geometry libraries are unavailable")
        root=design.svg_root('<svg viewBox="0 0 24 24"><path d="M2 2L8 2L8 8Zc2 0 4 2 6 4"/></svg>')
        self.assertTrue(design.geometry_rasters(root))

    def test_all_256_original_samples_are_preserved(self):
        values=[(i/255,(255-i)/255,0.5) for i in range(256)]
        code=design.gradient_code(values)
        root=design.svg_root(code)
        stops=[n for n in root.iter() if n.tag.split("}")[-1]=="stop"]
        self.assertEqual(len(stops),256)
        self.assertEqual(stops[0].get("stop-color"),"rgb(0% 100% 50%)")
        self.assertEqual(stops[-1].get("offset"),"1")

    def test_categorical_palette_keeps_every_original_swatch(self):
        values=[(i/255,(255-i)/255,0.5) for i in range(256)]
        root=design.svg_root(design.categorical_code(values))
        rectangles=[node for node in root.iter() if node.tag.split("}")[-1]=="rect"]
        self.assertEqual(len(rectangles),256)
        self.assertEqual(root.get("viewBox"),"0 0 16 16")
        self.assertEqual(rectangles[-1].get("x"),"15")
        self.assertEqual(rectangles[-1].get("y"),"15")
        self.assertEqual(rectangles[-1].get("fill"),"rgb(100% 0% 50%)")

    def test_continuous_map_reverse_and_resampling(self):
        a=design.resample([(0,0,0),(1,1,1)])
        b=design.resample([(i/255,)*3 for i in range(256)])
        self.assertTrue(design.continuous_near(a,b))
        self.assertTrue(design.continuous_near(a,list(reversed(b))))
        self.assertFalse(design.continuous_near(a,design.resample([(0,0,1),(1,0,0)])))

    def test_alpha_compared_on_both_backgrounds(self):
        opaque=design.resample([(1,0,0,1),(0,0,1,1)])
        transparent=design.resample([(1,0,0,0),(0,0,1,0)])
        self.assertFalse(design.continuous_near(opaque,transparent))

    def test_wes_nba_spurs_exact_collision(self):
        colors=("#9a8822ff","#f5cdb4ff","#f8afa8ff","#fddda0ff","#74a089ff")
        self.assertTrue(design.discrete_near(colors,colors))
        self.assertTrue(design.discrete_near(colors,tuple(reversed(colors))))


if __name__=="__main__":
    unittest.main()
