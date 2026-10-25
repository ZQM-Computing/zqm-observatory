from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.build_synthetic_product import build, write_draft_bundle
from scripts.verify_synthetic_provenance import verify
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


    def test_provenance_verifier_accepts_unchanged_run_and_detects_output_tampering(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output = root / "out"
            self.assertEqual(build(FIXTURE, output), 0)
            self.assertEqual(verify(FIXTURE, output), [])
            normalized = output / "normalized.geojson"
            normalized.write_bytes(normalized.read_bytes() + b" ")
            errors = verify(FIXTURE, output)
            self.assertTrue(any("normalized output: SHA-256 mismatch" in error for error in errors), errors)

    def test_provenance_verifier_detects_input_drift(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output = root / "out"
            self.assertEqual(build(FIXTURE, output), 0)
            changed_input = root / "changed.geojson"
            changed_input.write_bytes(FIXTURE.read_bytes() + b" ")
            errors = verify(changed_input, output)
            self.assertTrue(any("input: SHA-256 mismatch" in error for error in errors), errors)

    def test_provenance_verifier_rejects_missing_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            errors = verify(FIXTURE, Path(tmp))
            self.assertTrue(any("provenance.json cannot be read" in error for error in errors), errors)


if __name__ == "__main__":
    unittest.main()
