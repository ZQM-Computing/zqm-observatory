from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from scripts.verify_release_evidence import REQUIRED_ARTIFACTS, verify_manifest
from scripts.build_release_evidence import validate_non_authorizing_provenance



class ReleaseEvidencePathTests(unittest.TestCase):
    def test_verifier_rejects_artifact_symlink_even_when_target_hash_matches(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "bundle"
            root.mkdir()
            outside = Path(temporary) / "outside.json"
            outside.write_text('{"external": true}\n', encoding="utf-8")
            artifacts = {}
            for role in sorted(REQUIRED_ARTIFACTS):
                filename = f"{role}.json"
                artifact_path = root / filename
                if role == "qa_report":
                    artifact_path.symlink_to(outside)
                    content = outside.read_bytes()
                else:
                    content = b"{}\n"
                    artifact_path.write_bytes(content)
                artifacts[role] = {
                    "bundle_file": filename,
                    "sha256": hashlib.sha256(content).hexdigest(),
                }
            manifest = {
                "schema_version": 1,
                "manifest_type": "zqm_observatory_release_evidence",
                "artifacts": artifacts,
                "publication_authorized_by_manifest": False,
                "decision": "blocked",
            }
            manifest_path = root / "manifest.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

            errors = verify_manifest(manifest_path)

            self.assertTrue(
                any("artifact qa_report must not be a symlink" in error for error in errors),
                errors,
            )

    def test_release_evidence_rejects_authorizing_provenance(self) -> None:
        errors = validate_non_authorizing_provenance({"publication_authorized": True})
        self.assertTrue(any("publication_authorized=false" in error for error in errors), errors)

    def test_release_evidence_requires_explicit_false_authorization(self) -> None:
        self.assertEqual(validate_non_authorizing_provenance({"publication_authorized": False}), [])
        self.assertTrue(validate_non_authorizing_provenance({}))


if __name__ == "__main__":
    unittest.main()
