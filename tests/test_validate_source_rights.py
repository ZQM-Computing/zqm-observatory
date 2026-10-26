import copy
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from validate_source_rights import main, validate_document

REGISTER = json.loads((ROOT / "config" / "source-rights.json").read_text(encoding="utf-8"))


class SourceRightsValidatorTests(unittest.TestCase):
    def test_cli_rejects_duplicate_json_keys(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "source-rights.json"
            path.write_text(
                '{"sources":[],"sources":[{"decision":"APPROVED"}]}',
                encoding="utf-8",
            )
            stderr = io.StringIO()
            with patch.object(sys, "argv", ["validate_source_rights.py", str(path)]), redirect_stderr(stderr):
                result = main()
            self.assertEqual(result, 2)
            self.assertIn("duplicate JSON object key: 'sources'", stderr.getvalue())

    def test_current_register_is_valid_and_fail_closed(self):
        self.assertEqual(validate_document(REGISTER), [])
        self.assertTrue(all(s["decision"] in {"BLOCKED_PENDING_REVIEW", "REJECTED"} for s in REGISTER["sources"]))

    def test_duplicate_ids_are_rejected(self):
        document = copy.deepcopy(REGISTER)
        document["sources"].append(copy.deepcopy(document["sources"][0]))
        self.assertTrue(any("duplicates" in error for error in validate_document(document)))

    def test_unknown_is_not_approval(self):
        document = copy.deepcopy(REGISTER)
        source = document["sources"][0]
        source["decision"] = "APPROVED"
        source["terms_url"] = "https://example.gov/terms"
        source["terms_evidence"] = ["captured terms evidence"]
        source["required_attribution"] = "Example source"
        source["unresolved_questions"] = []
        self.assertTrue(any("APPROVED requires explicit true" in error for error in validate_document(document)))

    def test_approval_requires_retained_terms(self):
        document = copy.deepcopy(REGISTER)
        source = document["sources"][0]
        source["decision"] = "APPROVED"
        source["permitted_uses"] = {key: True for key in source["permitted_uses"]}
        source["required_attribution"] = "None stated"
        source["unresolved_questions"] = []
        self.assertTrue(any("requires a terms_url" in error for error in validate_document(document)))

    def test_internal_only_cannot_enable_publication(self):
        document = copy.deepcopy(REGISTER)
        source = document["sources"][0]
        source["decision"] = "INTERNAL_ONLY"
        source["terms_url"] = "https://example.gov/terms"
        source["terms_evidence"] = ["captured terms evidence"]
        source["required_attribution"] = "Example source"
        source["unresolved_questions"] = []
        source["permitted_uses"]["public_display"] = True
        self.assertTrue(any("INTERNAL_ONLY cannot permit" in error for error in validate_document(document)))

    def test_layer_id_must_match_service_url(self):
        document = copy.deepcopy(REGISTER)
        source = next(s for s in document["sources"] if s["id"] == "volusia-trails-layer-32")
        source["layer_id"] = 31
        self.assertTrue(any("layer_id must match the numeric layer" in error for error in validate_document(document)))

    def test_layer_id_is_required_in_every_source_record(self):
        document = copy.deepcopy(REGISTER)
        del document["sources"][0]["layer_id"]
        self.assertTrue(any("missing fields: layer_id" in error for error in validate_document(document)))

    def test_non_layer_source_requires_null_layer_id(self):
        document = copy.deepcopy(REGISTER)
        source = next(s for s in document["sources"] if s["id"] == "votran-official-gtfs")
        source["layer_id"] = 33
        self.assertTrue(any("layer_id must be null for a non-layer service URL" in error for error in validate_document(document)))

    def test_invalid_url_is_rejected(self):
        document = copy.deepcopy(REGISTER)
        document["sources"][0]["service_url"] = "http://example.gov/data"
        self.assertTrue(any("service_url must be a valid HTTPS URL" in error for error in validate_document(document)))

    def test_blocked_source_needs_open_questions(self):
        document = copy.deepcopy(REGISTER)
        document["sources"][0]["unresolved_questions"] = []
        self.assertTrue(any("blocked source must state unresolved questions" in error for error in validate_document(document)))

    def test_blocked_source_cannot_permit_any_use(self):
        document = copy.deepcopy(REGISTER)
        source = document["sources"][0]
        source["decision"] = "BLOCKED_PENDING_REVIEW"
        source["unresolved_questions"] = ["Terms evidence still needs review"]
        source["metadata_review_only"] = True
        source["permitted_uses"]["public_display"] = True
        self.assertTrue(any(
            "blocked/rejected source cannot permit any use" in error
            for error in validate_document(document)
        ))

    def test_rejected_source_cannot_permit_any_use(self):
        document = copy.deepcopy(REGISTER)
        source = document["sources"][0]
        source["decision"] = "REJECTED"
        source["unresolved_questions"] = ["Source is outside the permitted scope"]
        source["metadata_review_only"] = True
        source["permitted_uses"]["automated_capture"] = True
        self.assertTrue(any(
            "blocked/rejected source cannot permit any use" in error
            for error in validate_document(document)
        ))

    def test_metadata_review_only_must_be_boolean(self):
        document = copy.deepcopy(REGISTER)
        document["sources"][0]["metadata_review_only"] = "true"
        self.assertTrue(any(
            "metadata_review_only must be a boolean" in error
            for error in validate_document(document)
        ))

    def test_malformed_decision_is_rejected_without_crashing(self):
        for invalid in ([], {}, None, 7):
            with self.subTest(invalid=invalid):
                document = copy.deepcopy(REGISTER)
                document["sources"][0]["decision"] = invalid
                errors = validate_document(document)
                self.assertTrue(any("decision is not an allowed decision" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
