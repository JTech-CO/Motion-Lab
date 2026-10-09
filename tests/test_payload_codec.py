"""Compressed payload compatibility, alias preservation and corruption bounds."""

from contextlib import closing
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
import zlib

from motionlab.catalog import Catalog, CatalogUnavailable
from motionlab.payload_codec import MAGIC, MAX_DECODED_BYTES, MAX_PACKED_BYTES, PayloadError, decode_payload, encode_payload
from scripts.build import build


def record(identifier="fixture"):
    return {"id": identifier, "title": "한글 Motion", "description": "Original source and complete notice preserved",
            "category": "animation", "kind": "code", "language": "css", "access": "public", "tags": ["motion"], "colors": [],
            "sourceName": "Fixture", "sourceUrl": "https://example.org/" + identifier, "license": "MIT",
            "licenseText": "Full permission notice\n" * 100, "verifiedAt": "2026-10-09", "verification": "fixture",
            "code": ".motion-sample{animation:wave 1s infinite}@keyframes wave{from{transform:translateX(0)}to{transform:translateX(40px)}}",
            "preview": {"type": "css", "variant": "source"}}


class PayloadCodecTest(unittest.TestCase):
    def test_roundtrip_and_legacy_text_preserve_all_original_fields(self):
        original = record()
        original["variants"] = [record("former")]
        original["aliases"] = ["former"]
        compressed = encode_payload(original)
        self.assertTrue(compressed.startswith(MAGIC))
        self.assertLess(len(compressed), len(json.dumps(original)))
        self.assertEqual(decode_payload(compressed), original)
        self.assertEqual(decode_payload(json.dumps(original, ensure_ascii=False)), original)

    def test_corruption_unknown_format_and_trailing_stream_are_rejected(self):
        encoded = encode_payload(record())
        for value in (None, 3, b"{\"id\":\"x\"}", b"MLZ0\0broken", encoded[:-2], encoded + b"trailing",
                      encoded + zlib.compress(b"{}"), MAGIC + b"not-zlib", "[]", "{", '{"id":1,"id":2}', '{"value":NaN}'):
            with self.assertRaises(PayloadError, msg=repr(value)[:60]):
                decode_payload(value)

    def test_compression_bomb_and_input_limits_are_rejected(self):
        bomb = MAGIC + zlib.compress(b"x" * (MAX_DECODED_BYTES + 1))
        self.assertLess(len(bomb), 100_000)
        with self.assertRaises(PayloadError):
            decode_payload(bomb)
        with self.assertRaises(PayloadError):
            decode_payload(b"x" * (MAX_PACKED_BYTES + 1))
        with self.assertRaises(PayloadError):
            decode_payload("x" * (MAX_DECODED_BYTES + 1))
        with self.assertRaises(PayloadError):
            encode_payload({"value": "x" * MAX_DECODED_BYTES})
        with self.assertRaises(PayloadError):
            encode_payload({"value": float("nan")})

    def test_json_exponent_overflow_is_rejected_in_text_and_compressed_payloads(self):
        for body in (b'{"value":1e309}', b'{"nested":[-1e309]}'):
            for payload in (body.decode("ascii"), MAGIC + zlib.compress(body)):
                with self.assertRaises(PayloadError):
                    decode_payload(payload)
        self.assertEqual(decode_payload('{"value":1.25e2,"source":"1e309"}'),
                         {"value": 125.0, "source": "1e309"})

    def test_sqlite_search_get_export_alias_and_old_text_compatibility(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "data").mkdir()
            (root / "data/imported-items.json").write_text(json.dumps([record()]), encoding="utf-8")
            build(root)
            database = root / "data/motionlab.sqlite"
            catalog = Catalog(root)
            parent = catalog.get("fixture")
            variant = {**record("former"), "code": ".original{opacity:.7}"}
            parent.update({"variants": [variant], "aliases": ["former"],
                           "consolidation": {"variantRoles": {"former": "motion-variant"}}})
            with closing(sqlite3.connect(database)) as connection, connection:
                connection.execute("UPDATE items SET payload=? WHERE id=?", (encode_payload(parent), "fixture"))
                connection.execute("CREATE TABLE IF NOT EXISTS aliases (alias TEXT PRIMARY KEY, item_id TEXT NOT NULL, variant_id TEXT NOT NULL)")
                connection.execute("INSERT INTO aliases VALUES (?,?,?)", ("former", "fixture", "former"))
            self.assertEqual(catalog.get("fixture"), parent)
            self.assertEqual(catalog.search(query="motion")["items"][0], parent)
            self.assertEqual(catalog.export(), [parent])
            alias = catalog.get("former")
            self.assertEqual(alias["id"], "former")
            self.assertEqual(alias["code"], variant["code"])
            self.assertEqual(alias["licenseText"], variant["licenseText"])
            self.assertEqual(alias["canonicalId"], "fixture")
            with closing(sqlite3.connect(database)) as connection, connection:
                connection.execute("UPDATE items SET payload=? WHERE id=?", (json.dumps(parent), "fixture"))
            self.assertEqual(catalog.get("fixture"), parent)
            self.assertEqual(catalog.get("former")["code"], variant["code"])
            with closing(catalog.connection()) as connection:
                with self.assertRaises(sqlite3.OperationalError):
                    connection.execute("DELETE FROM items")
            with closing(sqlite3.connect(database)) as connection, connection:
                connection.execute("UPDATE items SET payload=? WHERE id=?", (MAGIC + b"corrupt", "fixture"))
            for read in (lambda: catalog.get("fixture"), lambda: catalog.get("former"), catalog.export, catalog.search):
                with self.assertRaises(CatalogUnavailable):
                    read()


if __name__ == "__main__":
    unittest.main()
