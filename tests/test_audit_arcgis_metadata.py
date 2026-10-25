from __future__ import annotations

import unittest

from scripts.audit_arcgis_metadata import audit_metadata


class ArcGISMetadataAuditTests(unittest.TestCase):
    def setUp(self) -> None:
        self.layer = {
            "id": 32,
            "name": "Trails",
            "displayField": "Name",
            "description": "",
            "copyrightText": "",
            "geometryType": "esriGeometryPolyline",
            "maxRecordCount": 2000,
            "spatialReference": {"wkid": 2881},
            "advancedQueryCapabilities": {"supportsPagination": True},
            "fields": [
                {"name": "OBJECTID", "type": "esriFieldTypeOID"},
                {"name": "Name", "type": "esriFieldTypeString"},
                {"name": "Shape", "type": "esriFieldTypeGeometry"},
            ],
        }

    def test_metadata_only_report_flags_missing_terms_and_description(self) -> None:
        report = audit_metadata(self.layer, "https://example.gov/FeatureServer/32", "BLOCKED_PENDING_REVIEW")
        self.assertEqual(report["inspection_mode"], "saved_layer_metadata_only")
        self.assertFalse(report["feature_records_requested"])
        self.assertIn("missing_description", report["warnings"])
        self.assertIn("missing_copyright_text", report["warnings"])
        self.assertIn("collection_and_publication_not_approved", report["warnings"])
        self.assertTrue(report["supports_pagination"])
        self.assertEqual(report["field_count"], 3)

    def test_approved_state_does_not_hide_quality_warnings(self) -> None:
        self.layer["description"] = "A documented layer."
        self.layer["copyrightText"] = "Publisher attribution."
        report = audit_metadata(self.layer, "https://example.gov/FeatureServer/32", "APPROVED")
        self.assertNotIn("collection_and_publication_not_approved", report["warnings"])
        self.assertIn("record_limit_requires_pagination_review", report["warnings"])
        self.assertIn("no_global_id_field_observed", report["warnings"])

    def test_non_object_metadata_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "JSON object"):
            audit_metadata([], "https://example.gov/layer", "BLOCKED_PENDING_REVIEW")

    def test_unknown_rights_state_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "rights_state"):
            audit_metadata(self.layer, "https://example.gov/layer", "MAYBE")

    def test_empty_fields_are_flagged(self) -> None:
        self.layer["fields"] = []
        report = audit_metadata(self.layer, "https://example.gov/layer", "BLOCKED_PENDING_REVIEW")
        self.assertIn("missing_or_unreadable_fields", report["warnings"])


if __name__ == "__main__":
    unittest.main()
