from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.build_synthetic_product import build


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


if __name__ == "__main__":
    unittest.main()
