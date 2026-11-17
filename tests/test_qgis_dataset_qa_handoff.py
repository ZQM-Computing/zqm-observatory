from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.run_qgis_dataset_qa_handoff import load_feature_count, validate_report


class QgisDatasetQaHandoffTests(unittest.TestCase):
    def _report(self, *, errors=0, warnings=0, findings=None, feature_count=3):
        return {
            "schema_version": 1,
            "dataset_count": 1,
            "datasets": [{
                "kind": "vector",
                "layers": [{"feature_count": feature_count, "fields": [
                    {"name": "id", "type": "String"},
                    {"name": "name", "type": "String"},
                ]}],
            }],
            "findings": findings or [],
            "summary": {"error": errors, "warning": warnings, "info": 0,
                        "total": len(findings or [])},
        }

    def test_accepts_clean_single_layer_fixture(self):
        self.assertEqual(validate_report(self._report(), 3), [])

    def test_rejects_errors_warnings_and_findings(self):
        report = self._report(errors=1, warnings=1, findings=[
            {"rule_id": "EXAMPLE", "severity": "warning"}
        ])
        errors = validate_report(report, 3)
        self.assertTrue(any("contains errors" in item for item in errors))
        self.assertTrue(any("contains warnings" in item for item in errors))
        self.assertTrue(any("no findings" in item for item in errors))

    def test_rejects_wrong_dataset_and_feature_counts(self):
        report = self._report(feature_count=2)
        errors = validate_report(report, 3)
        self.assertTrue(any("feature count" in item for item in errors))
        report["dataset_count"] = 2
        self.assertTrue(any("exactly one" in item for item in validate_report(report, 3)))

    def test_rejects_unrecognized_report_contract(self):
        self.assertTrue(validate_report([], 3))
        report = self._report()
        report["schema_version"] = 2
        self.assertTrue(validate_report(report, 3))

    def test_fixture_contract_requires_feature_collection_and_stable_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "fixture.geojson"
            path.write_text(json.dumps({
                "type": "FeatureCollection",
                "features": [{"type": "Feature", "properties": {"id": "a", "name": "A"}}],
            }), encoding="utf-8")
            self.assertEqual(load_feature_count(path), 1)
            path.write_text(json.dumps({"type": "FeatureCollection", "features": [
                {"type": "Feature", "properties": {"id": "", "name": "A"}}
            ]}), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_feature_count(path)


if __name__ == "__main__":
    unittest.main()
