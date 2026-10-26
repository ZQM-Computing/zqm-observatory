from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from scripts.build_release_evidence import read_json as read_build_json, validate_reviews
from scripts.strict_json import loads_strict
from scripts.verify_release_evidence import REQUIRED_ARTIFACTS, verify_manifest
from scripts.baseline_registry import load_registry
from scripts.build_release_evidence import validate_non_authorizing_provenance



class ReleaseEvidencePathTests(unittest.TestCase):
    def test_strict_json_rejects_duplicate_keys_at_any_depth(self) -> None:
        for raw in (
            '{"decision":"blocked","decision":"approved"}',
            '{"outer":{"decision":"blocked","decision":"approved"}}',
        ):
            with self.subTest(raw=raw):
                with self.assertRaisesRegex(ValueError, "duplicate JSON object key"):
                    loads_strict(raw)

    def test_evidence_verifier_rejects_duplicate_manifest_keys(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            manifest = Path(temporary) / "manifest.json"
            manifest.write_text(
                '{"schema_version":1,"schema_version":1}',
                encoding="utf-8",
            )
            errors = verify_manifest(manifest)
            self.assertTrue(
                any("duplicate JSON object key: 'schema_version'" in error for error in errors),
                errors,
            )

    def test_evidence_verifier_rejects_boolean_schema_version(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            manifest = Path(temporary) / "manifest.json"
            manifest.write_text(
                '{"schema_version":true,"manifest_type":"zqm_observatory_release_evidence"}',
                encoding="utf-8",
            )
            errors = verify_manifest(manifest)
            self.assertTrue(any("manifest schema" in error for error in errors), errors)

    def test_baseline_registry_rejects_boolean_schema_version(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            registry = Path(temporary) / "registry.json"
            registry.write_text(
                '{"schema_version":true,"registry_type":"zqm_observatory_baseline_registry","runs":[]}',
                encoding="utf-8",
            )
            value, errors = load_registry(registry)
            self.assertIsNone(value)
            self.assertTrue(any("schema_version 1" in error for error in errors), errors)

    def test_release_reviews_reject_boolean_schema_version(self) -> None:
        reviews = {"schema_version": True, "review_type": "zqm_observatory_release_reviews", "gates": {}}
        errors = validate_reviews(reviews)
        self.assertTrue(any("schema_version 1" in error for error in errors), errors)

    def test_evidence_builder_rejects_duplicate_input_keys(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "policy.json"
            source.write_text('{"decision":"blocked","decision":"approved"}', encoding="utf-8")
            value, errors = read_build_json(source, "release policy")
            self.assertIsNone(value)
            self.assertTrue(any("duplicate JSON object key: 'decision'" in error for error in errors), errors)


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


    def _write_hash_consistent_bundle(self, root: Path, reviews: dict) -> Path:
        """Build a synthetic bundle whose hashes and summary fields are internally consistent."""
        import scripts.verify_release_evidence as verifier

        payloads = {
            "normalized_dataset": b'{"type":"FeatureCollection","features":[]}\n',
            "qa_report": json.dumps({"status": "passed"}, sort_keys=True).encode() + b"\n",
            "before_dataset": b"before synthetic dataset\n",
            "after_dataset": b"after synthetic dataset\n",
            "baseline_registry": b'{"runs":[]}\n',
        }
        policy = {"block_on_severity": ["critical"], "max_removed": 0, "require_run_ids": True}
        empty_hash = hashlib.sha256(b"").hexdigest()
        for role in ("change_report", "release_gate_report", "release_policy", "human_reviews", "provenance"):
            payloads.setdefault(role, b"{}\n")
        payloads["release_policy"] = json.dumps(policy, sort_keys=True).encode() + b"\n"
        hashes = {name: hashlib.sha256(value).hexdigest() for name, value in payloads.items()}
        change = {
            "report_type": "geojson_feature_change_impact",
            "inputs": {
                "before": {"sha256": hashes["before_dataset"], "run_id": "baseline"},
                "after": {"sha256": hashes["after_dataset"], "run_id": "candidate"},
            },
        }
        gate = {"decision": "blocked", "policy": policy, "violations": []}
        provenance = {
            "schema_version": 1,
            "publication_authorized": False,
            "output": {"sha256": hashes["normalized_dataset"]},
            "qa_report": {"sha256": hashes["qa_report"]},
        }
        payloads.update({
            "change_report": json.dumps(change, sort_keys=True).encode() + b"\n",
            "release_gate_report": json.dumps(gate, sort_keys=True).encode() + b"\n",
            "human_reviews": json.dumps(reviews, sort_keys=True).encode() + b"\n",
            "provenance": json.dumps(provenance, sort_keys=True).encode() + b"\n",
        })
        hashes = {name: hashlib.sha256(value).hexdigest() for name, value in payloads.items()}
        root.mkdir(parents=True, exist_ok=True)
        artifacts = {}
        for role, value in payloads.items():
            filename = f"{role}.json"
            (root / filename).write_bytes(value)
            artifacts[role] = {"bundle_file": filename, "sha256": hashes[role]}
        decisions = {
            gate_name: reviews.get("gates", {}).get(gate_name, {}).get("decision")
            for gate_name in ("source_rights", "privacy", "factual_quality", "product_owner")
        } if isinstance(reviews.get("gates"), dict) else {}
        manifest = {
            "schema_version": 1,
            "manifest_type": "zqm_observatory_release_evidence",
            "artifacts": artifacts,
            "review_decisions": decisions,
            "release_gate": {"decision": "blocked", "violations": []},
            "publication_authorized_by_manifest": False,
            "decision": "blocked",
        }
        manifest_path = root / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, sort_keys=True), encoding="utf-8")
        return manifest_path

    def _approved_synthetic_reviews(self) -> dict:
        return {
            "schema_version": 1,
            "review_type": "zqm_observatory_release_reviews",
            "gates": {
                gate: {
                    "decision": "approved",
                    "reviewer": "Synthetic Test Reviewer",
                    "reviewed_on": "2026-10-26",
                    "evidence": "synthetic-evidence.md",
                }
                for gate in ("source_rights", "privacy", "factual_quality", "product_owner")
            },
        }

    def test_verifier_rejects_hash_consistent_bundle_with_missing_review_gate(self) -> None:
        import scripts.verify_release_evidence as verifier
        reviews = self._approved_synthetic_reviews()
        del reviews["gates"]["source_rights"]
        with tempfile.TemporaryDirectory() as temporary:
            manifest = self._write_hash_consistent_bundle(Path(temporary) / "bundle", reviews)
            with unittest.mock.patch.object(verifier, "evaluate", return_value=({"decision": "blocked", "policy": {"block_on_severity": ["critical"], "max_removed": 0, "require_run_ids": True}, "violations": []}, [])):
                errors = verify_manifest(manifest)
        self.assertTrue(any("human review validation" in error and "source_rights" in error for error in errors), errors)

    def test_verifier_rejects_hash_consistent_bundle_with_invalid_review_decision(self) -> None:
        import scripts.verify_release_evidence as verifier
        reviews = self._approved_synthetic_reviews()
        reviews["gates"]["privacy"]["decision"] = "approve"
        with tempfile.TemporaryDirectory() as temporary:
            manifest = self._write_hash_consistent_bundle(Path(temporary) / "bundle", reviews)
            with unittest.mock.patch.object(verifier, "evaluate", return_value=({"decision": "blocked", "policy": {"block_on_severity": ["critical"], "max_removed": 0, "require_run_ids": True}, "violations": []}, [])):
                errors = verify_manifest(manifest)
        self.assertTrue(any("human review validation" in error and "privacy" in error for error in errors), errors)

    def test_verifier_rejects_hash_consistent_bundle_with_malformed_review_date(self) -> None:
        import scripts.verify_release_evidence as verifier
        reviews = self._approved_synthetic_reviews()
        reviews["gates"]["factual_quality"]["reviewed_on"] = "2026-02-30"
        with tempfile.TemporaryDirectory() as temporary:
            manifest = self._write_hash_consistent_bundle(Path(temporary) / "bundle", reviews)
            with unittest.mock.patch.object(verifier, "evaluate", return_value=({"decision": "blocked", "policy": {"block_on_severity": ["critical"], "max_removed": 0, "require_run_ids": True}, "violations": []}, [])):
                errors = verify_manifest(manifest)
        self.assertTrue(any("human review validation" in error and "reviewed_on" in error for error in errors), errors)

    def test_verifier_rejects_hash_consistent_bundle_with_wrong_provenance_hash(self) -> None:
        import scripts.verify_release_evidence as verifier
        reviews = self._approved_synthetic_reviews()
        with tempfile.TemporaryDirectory() as temporary:
            manifest = self._write_hash_consistent_bundle(Path(temporary) / "bundle", reviews)
            provenance_path = manifest.parent / "provenance.json"
            provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
            provenance["output"]["sha256"] = "0" * 64
            provenance_path.write_text(json.dumps(provenance, sort_keys=True) + "\n", encoding="utf-8")
            data = json.loads(manifest.read_text(encoding="utf-8"))
            data["artifacts"]["provenance"]["sha256"] = hashlib.sha256(provenance_path.read_bytes()).hexdigest()
            manifest.write_text(json.dumps(data, sort_keys=True), encoding="utf-8")
            with unittest.mock.patch.object(verifier, "evaluate", return_value=({"decision": "blocked", "policy": {"block_on_severity": ["critical"], "max_removed": 0, "require_run_ids": True}, "violations": []}, [])):
                errors = verify_manifest(manifest)
        self.assertTrue(any("provenance output hash does not match" in error for error in errors), errors)

    def test_release_reviews_reject_missing_required_gate(self) -> None:
        reviews = {
            "schema_version": 1,
            "review_type": "zqm_observatory_release_reviews",
            "gates": {},
        }
        errors = validate_reviews(reviews)
        self.assertTrue(any("review gate source_rights is missing" in error for error in errors), errors)

    def test_release_reviews_reject_invalid_decision(self) -> None:
        reviews = {
            "schema_version": 1,
            "review_type": "zqm_observatory_release_reviews",
            "gates": {
                gate: {"decision": "approved", "reviewer": "Reviewer", "reviewed_on": "2026-10-26", "evidence": "evidence.md"}
                for gate in ("source_rights", "privacy", "factual_quality", "product_owner")
            },
        }
        reviews["gates"]["privacy"]["decision"] = "approve"
        errors = validate_reviews(reviews)
        self.assertTrue(any("review gate privacy is not approved" in error for error in errors), errors)

    def test_release_reviews_reject_malformed_date_and_empty_evidence(self) -> None:
        reviews = {
            "schema_version": 1,
            "review_type": "zqm_observatory_release_reviews",
            "gates": {
                gate: {"decision": "approved", "reviewer": "Reviewer", "reviewed_on": "2026-10-26", "evidence": "evidence.md"}
                for gate in ("source_rights", "privacy", "factual_quality", "product_owner")
            },
        }
        reviews["gates"]["factual_quality"]["reviewed_on"] = "2026-02-30"
        reviews["gates"]["product_owner"]["evidence"] = "  "
        errors = validate_reviews(reviews)
        self.assertTrue(any("factual_quality requires reviewed_on" in error for error in errors), errors)
        self.assertTrue(any("product_owner requires an evidence reference" in error for error in errors), errors)

    def test_release_reviews_reject_empty_reviewer_and_wrong_gate_shape(self) -> None:
        reviews = {
            "schema_version": 1,
            "review_type": "zqm_observatory_release_reviews",
            "gates": {
                gate: {"decision": "approved", "reviewer": "Reviewer", "reviewed_on": "2026-10-26", "evidence": "evidence.md"}
                for gate in ("source_rights", "privacy", "factual_quality", "product_owner")
            },
        }
        reviews["gates"]["source_rights"]["reviewer"] = " "
        reviews["gates"]["privacy"] = None
        errors = validate_reviews(reviews)
        self.assertTrue(any("source_rights requires a non-empty reviewer" in error for error in errors), errors)
        self.assertTrue(any("review gate privacy is missing or not an object" in error for error in errors), errors)


if __name__ == "__main__":
    unittest.main()
