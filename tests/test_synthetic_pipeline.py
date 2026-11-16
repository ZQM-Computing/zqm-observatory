from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from scripts.build_synthetic_product import DEMO_PRODUCT_ID, build, write_draft_bundle
from scripts.validate_products import validate_product


FIXTURE = Path(__file__).parent / "fixtures" / "synthetic-places.geojson"


class SyntheticPipelineTests(unittest.TestCase):
    def test_build_is_deterministic_and_emits_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            out_a, out_b = root / "a", root / "b"
            self.assertEqual(build(FIXTURE, out_a), 0)
            self.assertEqual(build(FIXTURE, out_b), 0)
            for name in ("normalized.geojson", "qa-report.json", "provenance.json"):
                self.assertEqual((out_a / name).read_bytes(), (out_b / name).read_bytes())
            provenance = json.loads((out_a / "provenance.json").read_text(encoding="utf-8"))
            self.assertFalse(provenance["publication_authorized"])
            output = json.loads((out_a / "normalized.geojson").read_text(encoding="utf-8"))
            ids = [feature["properties"]["id"] for feature in output["features"]]
            self.assertEqual(ids, sorted(ids))
            qa = json.loads((out_a / "qa-report.json").read_text(encoding="utf-8"))
            self.assertEqual(qa["status"], "passed")
            self.assertEqual(qa["feature_count_output"], 3)

    def test_duplicate_ids_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            raw = json.loads(FIXTURE.read_text(encoding="utf-8"))
            raw["features"][1]["properties"]["id"] = raw["features"][0]["properties"]["id"]
            source = root / "duplicate.geojson"
            source.write_text(json.dumps(raw), encoding="utf-8")
            output = root / "out"
            self.assertEqual(build(source, output), 1)
            qa = json.loads((output / "qa-report.json").read_text(encoding="utf-8"))
            self.assertEqual(qa["status"], "failed")
            self.assertTrue(any("duplicate feature id" in e for e in qa["errors"]))
            self.assertFalse((output / "normalized.geojson").exists())
            self.assertFalse((output / "provenance.json").exists())

    def test_out_of_range_coordinates_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            raw = json.loads(FIXTURE.read_text(encoding="utf-8"))
            raw["features"][0]["geometry"]["coordinates"] = [220, 95]
            source = root / "invalid.geojson"
            source.write_text(json.dumps(raw), encoding="utf-8")
            output = root / "out"
            self.assertEqual(build(source, output), 1)
            self.assertFalse((output / "normalized.geojson").exists())

    def test_invalid_json_writes_failure_report_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "broken.geojson"
            source.write_text("{not json", encoding="utf-8")
            output = root / "out"
            self.assertEqual(build(source, output), 1)
            self.assertTrue((output / "qa-report.json").exists())
            self.assertFalse((output / "normalized.geojson").exists())
            self.assertFalse((output / "provenance.json").exists())

    def test_failed_rerun_removes_stale_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output = root / "out"
            self.assertEqual(build(FIXTURE, output), 0)
            broken = root / "broken.geojson"
            broken.write_text("{not json", encoding="utf-8")
            self.assertEqual(build(broken, output), 1)
            self.assertTrue((output / "qa-report.json").exists())
            self.assertFalse((output / "normalized.geojson").exists())
            self.assertFalse((output / "provenance.json").exists())

    def test_non_string_required_property_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            raw = json.loads(FIXTURE.read_text(encoding="utf-8"))
            raw["features"][0]["properties"]["name"] = 17
            source = root / "bad-property.geojson"
            source.write_text(json.dumps(raw), encoding="utf-8")
            output = root / "out"
            self.assertEqual(build(source, output), 1)
            qa = json.loads((output / "qa-report.json").read_text(encoding="utf-8"))
            self.assertTrue(any("properties.name must be a non-empty string" in e for e in qa["errors"]))
            self.assertFalse((output / "normalized.geojson").exists())

    def test_cli_rerun_clears_draft_and_rejects_noncanonical_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output, bundles = root / "out", root / "bundles"
            bundle = bundles / DEMO_PRODUCT_ID
            command = [sys.executable, str(FIXTURE.parents[2] / "scripts/build_synthetic_product.py"),
                       "--output-dir", str(output), "--bundle-dir", str(bundles)]
            for invalid in ("{not json", '{"type":"FeatureCollection","features":[]}',
                            '{"type":"FeatureCollection","features":[{}]}'):
                with self.subTest(invalid=invalid):
                    success = subprocess.run(command + ["--input", str(FIXTURE)], capture_output=True)
                    self.assertEqual(success.returncode, 0, success.stderr)
                    self.assertTrue((bundle / "product.json").exists())
                    source = root / "custom.geojson"
                    source.write_text(invalid, encoding="utf-8")
                    failed = subprocess.run(command + ["--input", str(source)], capture_output=True)
                    self.assertEqual(failed.returncode, 1, failed.stderr)
                    self.assertEqual(list(bundle.iterdir()), [])
                    qa = json.loads((output / "qa-report.json").read_bytes())
                    if qa["status"] == "failed":
                        self.assertFalse((output / "normalized.geojson").exists())
                        self.assertFalse((output / "provenance.json").exists())
                    else:
                        self.assertIn(b"canonical synthetic fixture", failed.stderr)
                        # Custom inputs remain supported for artifact-only builds.
                        artifact_only = command[:4] + ["--input", str(source)]
                        self.assertEqual(subprocess.run(artifact_only, capture_output=True).returncode, 0)

    def test_interrupted_bundle_rebuild_revokes_previous_approval(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output, bundles = root / "out", root / "bundles"
            self.assertEqual(build(FIXTURE, output), 0)
            bundle = write_draft_bundle(output, bundles)
            product_path = bundle / "product.json"
            product = json.loads(product_path.read_bytes())
            product["privacy_review"].update(reviewed=True, reviewed_by="Synthetic test reviewer")
            product_path.write_text(json.dumps(product), encoding="utf-8")
            self.assertEqual(validate_product(bundle), [])
            with patch("scripts.build_synthetic_product.shutil.copyfile", side_effect=OSError("interrupted")):
                with self.assertRaises(OSError):
                    write_draft_bundle(output, bundles)
            self.assertFalse(product_path.exists())
            self.assertTrue(validate_product(bundle))

    def test_draft_bundle_matches_product_contract_but_fails_closed_for_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            artifacts = root / "artifacts"
            bundle_root = root / "bundles"
            self.assertEqual(build(FIXTURE, artifacts), 0)
            bundle = write_draft_bundle(artifacts, bundle_root)
            expected = {
                "product.json", "sources.json", "method.md",
                "normalized.geojson", "qa-report.json", "provenance.json",
            }
            self.assertEqual({item.name for item in bundle.iterdir()}, expected)
            product = json.loads((bundle / "product.json").read_text(encoding="utf-8"))
            self.assertEqual(set(product["data_files"]), {"normalized.geojson", "qa-report.json", "provenance.json"})
            self.assertFalse(product["privacy_review"]["reviewed"])
            errors = validate_product(bundle)
            self.assertTrue(any("privacy_review.reviewed must be true" in error for error in errors))
            self.assertTrue(any("privacy_review.reviewed_by must be a non-empty string" in error for error in errors))
            self.assertEqual(len(errors), 2, errors)


if __name__ == "__main__":
    unittest.main()
