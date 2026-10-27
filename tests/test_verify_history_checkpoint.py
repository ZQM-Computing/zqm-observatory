from __future__ import annotations

import base64
import hashlib
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

try:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
except ImportError:
    serialization = None
    Ed25519PrivateKey = None

from scripts.release_history import append_entry, load_entries, canonical_json
from scripts.verify_history_checkpoint import verify_checkpoint, verify_and_update_state


@unittest.skipIf(Ed25519PrivateKey is None, "optional cryptography dependency is not installed")
class HistoryCheckpointTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.history = self.root / "history.jsonl"
        self.attestation = self.root / "attestation.json"
        self.attestation.write_text('{"synthetic":true}\n', encoding="utf-8")
        self.assertEqual(append_entry(self.history, self.attestation), [])
        self.entries, errors = load_entries(self.history)
        self.assertEqual(errors, [])
        self.private = Ed25519PrivateKey.generate()
        self.public = self.private.public_key()
        self.public_path = self.root / "trusted-public.pem"
        self.public_path.write_bytes(self.public.public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        ))
        der = self.public.public_bytes(
            serialization.Encoding.DER,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        self.fingerprint = hashlib.sha256(der).hexdigest()
        self.now = datetime(2026, 10, 26, 12, 0, tzinfo=timezone.utc)
        self.checkpoint_path = self.root / "checkpoint.json"
        self._write_checkpoint()

    def _write_checkpoint(self, *, sequence=1, entry_hash=None, issued_at=None, key=None, fingerprint=None):
        payload = {
            "schema_version": 1,
            "checkpoint_type": "zqm_observatory_history_checkpoint",
            "history_id": "test-history-01",
            "sequence": sequence,
            "entry_sha256": entry_hash or self.entries[sequence - 1]["entry_sha256"],
            "issued_at": (issued_at or self.now).isoformat().replace("+00:00", "Z"),
            "issuer": "test-anchor",
            "algorithm": "Ed25519",
            "key_fingerprint": fingerprint or self.fingerprint,
        }
        signer = key or self.private
        envelope = {
            "payload": payload,
            "signature": base64.b64encode(signer.sign(canonical_json(payload))).decode("ascii"),
        }
        self.checkpoint_path.write_text(json.dumps(envelope), encoding="utf-8")

    def test_valid_signature_and_matching_history(self):
        self.assertEqual(verify_checkpoint(
            self.history, self.checkpoint_path, self.public_path,
            now=self.now, expected_history_id="test-history-01",
        ), [])

    def test_modified_payload_fails_signature(self):
        envelope = json.loads(self.checkpoint_path.read_text(encoding="utf-8"))
        envelope["payload"]["issuer"] = "attacker"
        self.checkpoint_path.write_text(json.dumps(envelope), encoding="utf-8")
        self.assertTrue(any("signature verification failed" in e for e in verify_checkpoint(
            self.history, self.checkpoint_path, self.public_path, now=self.now,
        )))

    def test_wrong_trusted_key_fails(self):
        other = Ed25519PrivateKey.generate()
        other_path = self.root / "other-public.pem"
        other_path.write_bytes(other.public_key().public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo,
        ))
        self.assertTrue(verify_checkpoint(self.history, self.checkpoint_path, other_path, now=self.now))

    def test_stale_checkpoint_fails_closed(self):
        self._write_checkpoint(issued_at=self.now - timedelta(days=2))
        self.assertTrue(any("stale" in e for e in verify_checkpoint(
            self.history, self.checkpoint_path, self.public_path, now=self.now, max_age_seconds=3600,
        )))

    def test_future_checkpoint_fails_closed(self):
        self._write_checkpoint(issued_at=self.now + timedelta(minutes=10))
        self.assertTrue(any("future" in e for e in verify_checkpoint(
            self.history, self.checkpoint_path, self.public_path, now=self.now,
        )))

    def test_sequence_high_water_mark_prevents_rollback(self):
        self.assertTrue(any("regressed" in e for e in verify_checkpoint(
            self.history, self.checkpoint_path, self.public_path,
            now=self.now, minimum_sequence=2,
        )))

    def test_history_mismatch_fails(self):
        self._write_checkpoint(entry_hash="f" * 64)
        self.assertTrue(any("does not match" in e for e in verify_checkpoint(
            self.history, self.checkpoint_path, self.public_path, now=self.now,
        )))

    def test_checkpoint_ahead_of_history_fails(self):
        self._write_checkpoint(sequence=2, entry_hash="a" * 64)
        self.assertTrue(any("ahead of local history" in e for e in verify_checkpoint(
            self.history, self.checkpoint_path, self.public_path, now=self.now,
        )))

    def test_state_file_persists_accepted_checkpoint(self):
        state = self.root / "rollback-state.json"
        self.assertEqual(verify_and_update_state(self.history, self.checkpoint_path, self.public_path, state, now=self.now, expected_history_id="test-history-01"), [])
        persisted = json.loads(state.read_text(encoding="utf-8"))
        self.assertEqual(persisted["sequence"], 1)
        self.assertEqual(persisted["entry_sha256"], self.entries[0]["entry_sha256"])
        self.assertTrue((self.root / "rollback-state.json.lock").exists())

    def test_state_file_rejects_checkpoint_sequence_rollback(self):
        state = self.root / "rollback-state.json"
        second_attestation = self.root / "attestation-2.json"
        second_attestation.write_text('{"synthetic":2}\\n', encoding="utf-8")
        self.assertEqual(append_entry(self.history, second_attestation), [])
        self.entries, errors = load_entries(self.history)
        self.assertEqual(errors, [])
        self._write_checkpoint(sequence=2)
        self.assertEqual(verify_and_update_state(self.history, self.checkpoint_path, self.public_path, state, now=self.now, expected_history_id="test-history-01"), [])
        self._write_checkpoint(sequence=1)
        errors = verify_and_update_state(self.history, self.checkpoint_path, self.public_path, state, now=self.now, expected_history_id="test-history-01")
        self.assertTrue(any("regressed" in error for error in errors))
        self.assertEqual(json.loads(state.read_text(encoding="utf-8"))["sequence"], 2)

    def test_state_file_rejects_corrupt_existing_state(self):
        state = self.root / "rollback-state.json"
        state.write_text('{"sequence":999}\\n', encoding="utf-8")
        errors = verify_and_update_state(self.history, self.checkpoint_path, self.public_path, state, now=self.now, expected_history_id="test-history-01")
        self.assertTrue(any("schema" in error for error in errors))
        self.assertEqual(state.read_text(encoding="utf-8"), '{"sequence":999}\\n')

    def test_state_file_rejects_symlink(self):
        state = self.root / "rollback-state.json"
        target = self.root / "actual-state.json"
        target.write_text('{}\\n', encoding="utf-8")
        state.symlink_to(target)
        errors = verify_and_update_state(self.history, self.checkpoint_path, self.public_path, state, now=self.now, expected_history_id="test-history-01")
        self.assertTrue(any("symlinks" in error for error in errors))
        self.assertEqual(target.read_text(encoding="utf-8"), '{}\\n')

    def test_expected_history_identifier_is_enforced(self):
        self.assertTrue(any("history_id" in e for e in verify_checkpoint(
            self.history, self.checkpoint_path, self.public_path,
            now=self.now, expected_history_id="different-history",
        )))


if __name__ == "__main__":
    unittest.main()
