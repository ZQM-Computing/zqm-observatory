from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

try:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
except ImportError:
    serialization = None
    Ed25519PrivateKey = None

from scripts.release_history import GENESIS, append_entry, canonical_json, load_entries, main as history_main, sha256_bytes
from scripts.sign_release_attestation import sign, verify


@unittest.skipIf(Ed25519PrivateKey is None, "optional cryptography dependency is not installed")
class ReleaseAttestationTests(unittest.TestCase):
    def _fixture(self, root: Path):
        bundle = root / "bundle"
        bundle.mkdir()
        roles = ("normalized_dataset", "qa_report", "provenance", "before_dataset", "after_dataset",
                 "baseline_registry", "change_report", "release_gate_report", "release_policy", "human_reviews")
        artifacts = {}
        for role in roles:
            name = role + ".json"
            (bundle / name).write_text(json.dumps({"role": role}), encoding="utf-8")
            import hashlib
            digest = hashlib.sha256((bundle / name).read_bytes()).hexdigest()
            artifacts[role] = {"bundle_file": name, "sha256": digest}
        # A minimal valid non-authorizing evidence bundle is intentionally blocked.
        policy = {"block_on_severity": ["critical"], "max_removed": 0, "require_run_ids": True}
        reviews = {"schema_version": 1, "review_type": "zqm_observatory_release_reviews", "gates": {}}
        change = {"report_type": "geojson_feature_change_impact", "inputs": {
            "before": {"sha256": artifacts["before_dataset"]["sha256"], "run_id": "base"},
            "after": {"sha256": artifacts["after_dataset"]["sha256"], "run_id": "candidate"}}, "summary": {}, "changed_features": []}
        gate = {"decision": "eligible_for_human_release_review", "policy": policy, "violations": []}
        provenance = {"publication_authorized": False}
        qa = {"status": "passed"}
        for role, value in (("release_policy", policy), ("human_reviews", reviews), ("change_report", change),
                            ("release_gate_report", gate), ("provenance", provenance), ("qa_report", qa)):
            path = bundle / artifacts[role]["bundle_file"]
            path.write_text(json.dumps(value, sort_keys=True), encoding="utf-8")
            import hashlib
            artifacts[role]["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        # Ensure manifest data inputs match their hashes and keep authorization blocked.
        manifest = {"schema_version": 1, "manifest_type": "zqm_observatory_release_evidence", "decision": "blocked",
                    "publication_authorized_by_manifest": False, "artifacts": artifacts}
        # verifier also recomputes gate and validates QA/provenance/review type and artifact hashes.
        (bundle / "manifest.json").write_text(json.dumps(manifest, sort_keys=True), encoding="utf-8")
        # Build a realistic self-contained bundle via a small test seam: tests below focus on signing
        # mechanics; monkeypatch bundle verification to isolate envelope integrity tests.
        return bundle / "manifest.json"

    def test_sign_verify_wrong_key_and_manifest_tampering(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = self._fixture(root)
            private = Ed25519PrivateKey.generate()
            wrong = Ed25519PrivateKey.generate()
            private_path, public_path, wrong_path = root / "private.pem", root / "public.pem", root / "wrong.pem"
            private_path.write_bytes(private.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
            public_path.write_bytes(private.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo))
            wrong_path.write_bytes(wrong.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo))
            attestation = root / "attestation.json"
            with patch("scripts.sign_release_attestation.verify_manifest", return_value=[]):
                sign(manifest, private_path, attestation, "test-issuer", None)
                self.assertEqual(verify(attestation, public_path, manifest), [])
                attestation.write_text('{"schema_version":1,"schema_version":1}', encoding="utf-8")
                self.assertTrue(any("duplicate JSON object key" in error for error in verify(attestation, public_path, manifest)))
                sign(manifest, private_path, attestation, "test-issuer", None)
                self.assertEqual(verify(attestation, public_path, manifest), [])
                envelope = json.loads(attestation.read_text(encoding="utf-8"))
                envelope["schema_version"] = True
                attestation.write_text(json.dumps(envelope), encoding="utf-8")
                self.assertTrue(any("attestation envelope schema is invalid" in error for error in verify(attestation, public_path, manifest)))
                sign(manifest, private_path, attestation, "test-issuer", None)
                self.assertEqual(verify(attestation, public_path, manifest), [])
                self.assertTrue(verify(attestation, wrong_path, manifest))
                manifest.write_text(manifest.read_text(encoding="utf-8") + " ", encoding="utf-8")
                self.assertTrue(any("manifest SHA-256" in error for error in verify(attestation, public_path, manifest)))

    def test_verify_rejects_malformed_signed_payload_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = self._fixture(root)
            private = Ed25519PrivateKey.generate()
            private_path = root / "private.pem"
            public_path = root / "public.pem"
            attestation = root / "attestation.json"
            private_path.write_bytes(private.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8,
                serialization.NoEncryption(),
            ))
            public_path.write_bytes(private.public_key().public_bytes(
                serialization.Encoding.PEM,
                serialization.PublicFormat.SubjectPublicKeyInfo,
            ))
            with patch("scripts.sign_release_attestation.verify_manifest", return_value=[]):
                sign(manifest, private_path, attestation, "test-issuer", None)
            envelope = json.loads(attestation.read_text(encoding="utf-8"))
            envelope["payload"]["issued_at"] = "2026-99-99T25:61:00"
            envelope["payload"]["manifest_file"] = "../other-manifest.json"
            attestation.write_text(json.dumps(envelope), encoding="utf-8")
            errors = verify(attestation, public_path, manifest)
            self.assertTrue(any("valid ISO-8601 timestamp" in error for error in errors))
            self.assertTrue(any("manifest_file does not match" in error for error in errors))
            self.assertTrue(any("signature verification failed" in error for error in errors))

    def test_sign_refuses_bundle_rejected_by_independent_verifier(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = self._fixture(root)
            private = Ed25519PrivateKey.generate()
            private_path = root / "private.pem"
            private_path.write_bytes(private.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8,
                serialization.NoEncryption(),
            ))
            output = root / "must-not-exist.json"
            # No verifier patch: the signing entry point must enforce the real
            # evidence policy, not merely sign a syntactically plausible bundle.
            with self.assertRaisesRegex(ValueError, "evidence bundle verification failed"):
                sign(manifest, private_path, output, "test-issuer", None)
            self.assertFalse(output.exists())

    def test_history_rejects_duplicate_json_keys(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            history = root / "history.jsonl"
            history.write_text('{"sequence":1,"sequence":2,"previous_entry_sha256":"' + "0" * 64 + '","attestation_file":"attestation.json","attestation_sha256":"' + "a" * 64 + '","entry_sha256":"' + "b" * 64 + '"}\n', encoding="utf-8")
            _, errors = load_entries(history)
            self.assertTrue(any("duplicate JSON object key" in error for error in errors))

    def test_history_verify_rejects_traversal_filename_without_traceback(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            history = root / "history.jsonl"
            body = {
                "sequence": 1,
                "previous_entry_sha256": GENESIS,
                "attestation_file": "..",
                "attestation_sha256": "a" * 64,
            }
            entry = {**body, "entry_sha256": sha256_bytes(canonical_json(body))}
            history.write_text(json.dumps(entry) + "\n", encoding="utf-8")
            stderr = io.StringIO()
            with patch("sys.argv", ["release_history.py", "verify", "--history", str(history)]), contextlib.redirect_stderr(stderr):
                result = history_main()
            self.assertEqual(result, 1)
            self.assertIn("unsafe attestation_file", stderr.getvalue())
            self.assertNotIn("Traceback", stderr.getvalue())

    def test_history_chain_detects_edit_and_duplicate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            attestation = root / "attestation.json"
            attestation.write_text('{"signed":true}', encoding="utf-8")
            history = root / "history.jsonl"
            self.assertEqual(append_entry(history, attestation), [])
            entries, errors = load_entries(history)
            self.assertEqual(errors, [])
            self.assertEqual(len(entries), 1)
            self.assertTrue(append_entry(history, attestation))
            history.write_text(history.read_text(encoding="utf-8").replace('"sequence":1', '"sequence":2'), encoding="utf-8")
            _, errors = load_entries(history)
            self.assertTrue(errors)


if __name__ == "__main__":
    unittest.main()
