import hashlib
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from audit_source_metadata import build_report, capture_one, layer_metadata_url, summarize_metadata

REGISTER = json.loads((ROOT / "config" / "source-rights.json").read_text(encoding="utf-8"))


class FakeHeaders(dict):
    pass


class FakeResponse:
    def __init__(self, body, status=200, content_type="application/json"):
        self.body = body
        self.status = status
        self.headers = FakeHeaders({"Content-Type": content_type})

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, limit=-1):
        return self.body[:limit]


class FakeOpener:
    def __init__(self, response):
        self.response = response
        self.request = None
        self.timeout = None

    def open(self, request, timeout):
        self.request = request
        self.timeout = timeout
        return self.response


class MetadataPreflightTests(unittest.TestCase):
    def test_only_allowlisted_arcgis_layer_urls_are_eligible(self):
        url, reason = layer_metadata_url(
            "https://maps5.vcgov.org/arcgis/rest/services/Open_Data/Open_Data_4/FeatureServer/32"
        )
        self.assertIsNone(reason)
        self.assertIn("/FeatureServer/32?f=pjson", url)
        for invalid in (
            "https://www.votran.org/documents-data/",
            "https://example.com/FeatureServer/32",
            "http://maps5.vcgov.org/FeatureServer/32",
            "https://maps5.vcgov.org/FeatureServer/32?where=1%3D1",
            "https://maps5.vcgov.org:bad/arcgis/rest/services/Open_Data/Open_Data_4/FeatureServer/32",
            "https://maps5.vcgov.org/arcgis/rest/services/Other/FeatureServer/32",
        ):
            with self.subTest(invalid=invalid):
                self.assertIsNone(layer_metadata_url(invalid)[0])

    def test_metadata_summary_never_accepts_feature_payload(self):
        with self.assertRaisesRegex(ValueError, "feature records"):
            summarize_metadata({"features": [{"attributes": {"id": 1}}]})

    def test_metadata_summary_rejects_missing_layer_identity(self):
        with self.assertRaisesRegex(ValueError, "layer id or name"):
            summarize_metadata({})

    def test_capture_requests_metadata_and_records_hash_without_feature_data(self):
        raw = json.dumps({
            "id": 32, "name": "Trails", "geometryType": "esriGeometryPolyline",
            "description": "", "copyrightText": "", "maxRecordCount": 2000,
            "capabilities": "Query", "fields": [{"name": "OBJECTID", "type": "esriFieldTypeOID"}],
            "extent": {"spatialReference": {"wkid": 2881}},
        }).encode()
        opener = FakeOpener(FakeResponse(raw))
        source = next(s for s in REGISTER["sources"] if s["id"] == "volusia-trails-layer-32")
        result = capture_one(source, opener=opener)
        self.assertEqual(result["status"], "OK")
        self.assertEqual(result["response_sha256"], hashlib.sha256(raw).hexdigest())
        self.assertEqual(result["metadata"]["geometry_type"], "esriGeometryPolyline")
        self.assertEqual(result["collection_gate"], "BLOCKED_BY_REGISTER_DECISION")
        self.assertIn("f=pjson", opener.request.full_url)
        self.assertEqual(opener.timeout, 15)
        self.assertNotIn("where=", opener.request.full_url)
        self.assertNotIn("outFields=", opener.request.full_url)

    def test_oversized_response_fails_closed(self):
        from audit_source_metadata import MAX_RESPONSE_BYTES
        source = next(s for s in REGISTER["sources"] if s["id"] == "volusia-trails-layer-32")
        result = capture_one(source, opener=FakeOpener(FakeResponse(b"x" * (MAX_RESPONSE_BYTES + 1))))
        self.assertEqual(result["status"], "ERROR")
        self.assertIn("exceeds", result["reason"])

    def test_non_json_response_fails_closed(self):
        source = next(s for s in REGISTER["sources"] if s["id"] == "volusia-trails-layer-32")
        result = capture_one(source, opener=FakeOpener(FakeResponse(b"not json", content_type="text/html")))
        self.assertEqual(result["status"], "ERROR")
        self.assertIn("content type", result["reason"])

    def test_non_layer_gtfs_index_is_skipped_without_request(self):
        source = next(s for s in REGISTER["sources"] if s["id"] == "votran-official-gtfs")
        opener = FakeOpener(FakeResponse(b"{}"))
        result = capture_one(source, opener=opener)
        self.assertEqual(result["status"], "SKIPPED")
        self.assertIn("skipped without network request", result["reason"])
        self.assertIsNone(opener.request)

    def test_report_makes_no_collection_or_rights_claim(self):
        report = build_report(REGISTER, opener=FakeOpener(FakeResponse(b"{}")))
        self.assertFalse(report["safety_scope"]["feature_records_requested"])
        self.assertFalse(report["safety_scope"]["bulk_download_performed"])
        self.assertFalse(report["safety_scope"]["rights_approval_granted"])
        self.assertEqual(report["counts"]["total"], len(REGISTER["sources"]))


if __name__ == "__main__":
    unittest.main()
