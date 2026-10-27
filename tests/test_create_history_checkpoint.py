from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

try:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
except ImportError:
    serialization = None
    Ed25519PrivateKey = None

from scripts.create_history_checkpoint import create_checkpoint
from scripts.release_history import append_entry
from scripts.verify_history_checkpoint import verify_checkpoint


@unittest.skipIf(Ed25519PrivateKey is None, "optional cryptography dependency is not installed")
class CreateHistoryCheckpointTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.history = self.root / "history.jsonl"
        self.attestation = self.root / "attestation.json"
        self.attestation.write_text('{"synthetic":true}\n', encoding="utf-8")
        self.private = Ed25519PrivateKey.generate()
        self.private_path = self.root / "anchor-private.pem"
        self.private_path.write_bytes(self.private.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ))
        self.public_path = self.root / "anchor-public.pem"
        self.public_path.write_bytes(self.private.public_key().public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        ))
        self.output = self.root / "checkpoint.json"
        self.now = datetime(2026, 10, 26, 12, 0, tzinfo=timezone.utc)

    def test_create_and_verify_checkpoint(self):
        self.assertEqual(append_entry(self.history, self.attestation), [])
        self.assertEqual(create_checkpoint(
            self.history, self.private_path, self.output,
            history_id="test-history", issuer="test-anchor", issued_at=self.now,
        ), [])
        self.assertEqual(verify_checkpoint(
            self.history, self.output, self.public_path,
            now=self.now, expected_history_id="test-history",
        ), [])

    def test_empty_history_is_rejected(self):
        errors = create_checkpoint(
            self.history, self.private_path, self.output,
            history_id="test-history", issuer="test-anchor", issued_at=self.now,
        )
        self.assertTrue(any("empty history" in error for error in errors))
        self.assertFalse(self.output.exists())

    def test_existing_checkpoint_is_never_overwritten(self):
        self.assertEqual(append_entry(self.history, self.attestation), [])
        self.output.write_text('{"existing":true}\n', encoding="utf-8")
        errors = create_checkpoint(
            self.history, self.private_path, self.output,
            history_id="test-history", issuer="test-anchor", issued_at=self.now,
        )
        self.assertTrue(any("refusing to overwrite" in error for error in errors))
        self.assertEqual(self.output.read_text(encoding="utf-8"), '{"existing":true}\n')

    def test_invalid_history_is_rejected(self):
        self.assertEqual(append_entry(self.history, self.attestation), [])
        self.history.write_text('{"broken":true}\n', encoding="utf-8")
        errors = create_checkpoint(
            self.history, self.private_path, self.output,
            history_id="test-history", issuer="test-anchor", issued_at=self.now,
        )
        self.assertTrue(any("history is invalid" in error for error in errors))
        self.assertFalse(self.output.exists())


if __name__ == "__main__":
    unittest.main()
