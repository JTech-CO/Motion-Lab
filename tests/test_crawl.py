"""Offline license-cache integrity regression; no network or source-data writes."""

import hashlib
import importlib.util
from pathlib import Path
import unittest


SPEC = importlib.util.spec_from_file_location(
    "motionlab_crawl_under_test", Path(__file__).resolve().parent.parent / "scripts" / "crawl.py"
)
CRAWL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CRAWL)


class CachedLicenseTest(unittest.TestCase):
    def test_cached_license_integrity(self):
        valid = (
            b"The MIT License (MIT)\n\n"
            b"Copyright (c) Motion Lab test fixture\n\n"
            b"Permission is hereby granted, free of charge, to any person obtaining a copy\n"
            b"of this software and associated documentation files.\n"
        )
        valid_digest = hashlib.sha256(valid).hexdigest()
        self.assertEqual(CRAWL.verified_mit_license(valid, valid_digest, offline=True), valid.decode("utf-8"))

        non_mit = b"All rights reserved. Redistribution prohibited.\n"
        false_heading = b"NOT AN MIT LICENSE.\nPermission is hereby granted, free of charge.\n"
        cases = (
            ("tampered bytes retaining MIT text", valid + b"\nChanged copyright notice\n", valid_digest,
             "Cached license hash mismatch"),
            ("missing digest", valid, None, "missing licenseSha256"),
            ("non-MIT terms with matching digest", non_mit, hashlib.sha256(non_mit).hexdigest(),
             "MIT license not verified"),
            ("MIT substring without a declaration", false_heading, hashlib.sha256(false_heading).hexdigest(),
             "MIT license not verified"),
        )
        for name, body, digest, expected_error in cases:
            with self.subTest(case=name):
                with self.assertRaisesRegex(ValueError, expected_error):
                    CRAWL.verified_mit_license(body, digest, offline=True)


if __name__ == "__main__":
    unittest.main()
