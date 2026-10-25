from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.build_synthetic_product import build, write_draft_bundle
from scripts.verify_synthetic_provenance import verify
from scripts.compare_product_runs import compare
from scripts.validate_products import validate_product
from scripts.evaluate_change_release import evaluate


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

    def test_failed_rerun_removes_stale_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output = root / "out"
            self.assertEqual(build(FIXTURE, output), 0)
            broken = root / "broken.geojson"
            broken.write_text("{not json", encoding="utf-8")
            self.assertEqual(build(broken, output), 1)
            self.assertTrue((output / "qa-report.json").exists())
            self.assertFalse((output / "normalized.geojson").exists())
            self.assertFalse((output / "provenance.json").exists())

    def test_non_string_required_property_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            raw = json.loads(FIXTURE.read_text(encoding="utf-8"))
            raw["features"][0]["properties"]["name"] = 17
            source = root / "bad-property.geojson"
            source.write_text(json.dumps(raw), encoding="utf-8")
            output = root / "out"
            self.assertEqual(build(source, output), 1)
            qa = json.loads((output / "qa-report.json").read_text(encoding="utf-8"))
            self.assertTrue(any("properties.name must be a non-empty string" in e for e in qa["errors"]))
            self.assertFalse((output / "normalized.geojson").exists())

    def test_draft_bundle_matches_product_contract_but_fails_closed_for_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            artifacts = root / "artifacts"
            bundle_root = root / "bundles"
            self.assertEqual(build(FIXTURE, artifacts), 0)
            bundle = write_draft_bundle(artifacts, bundle_root)
            expected = {
                "product.json", "sources.json", "method.md",
                "normalized.geojson", "qa-report.json", "provenance.json",
            }
            self.assertEqual({item.name for item in bundle.iterdir()}, expected)
            product = json.loads((bundle / "product.json").read_text(encoding="utf-8"))
            self.assertEqual(set(product["data_files"]), {"normalized.geojson", "qa-report.json", "provenance.json"})
            self.assertFalse(product["privacy_review"]["reviewed"])
            errors = validate_product(bundle)
            self.assertTrue(any("privacy_review.reviewed must be true" in error for error in errors))
            self.assertTrue(any("privacy_review.reviewed_by must be a non-empty string" in error for error in errors))
            self.assertEqual(len(errors), 2, errors)


    def test_provenance_verifier_accepts_unchanged_run_and_detects_output_tampering(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output = root / "out"
            self.assertEqual(build(FIXTURE, output), 0)
            self.assertEqual(verify(FIXTURE, output), [])
            normalized = output / "normalized.geojson"
            normalized.write_bytes(normalized.read_bytes() + b" ")
            errors = verify(FIXTURE, output)
            self.assertTrue(any("normalized output: SHA-256 mismatch" in error for error in errors), errors)

    def test_provenance_verifier_detects_input_drift(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output = root / "out"
            self.assertEqual(build(FIXTURE, output), 0)
            changed_input = root / "changed.geojson"
            changed_input.write_bytes(FIXTURE.read_bytes() + b" ")
            errors = verify(changed_input, output)
            self.assertTrue(any("input: SHA-256 mismatch" in error for error in errors), errors)

    def test_provenance_verifier_rejects_missing_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            errors = verify(FIXTURE, Path(tmp))
            self.assertTrue(any("provenance.json cannot be read" in error for error in errors), errors)


    def test_change_report_identifies_added_removed_changed_and_extent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            before_input = root / "before-input.geojson"
            after_input = root / "after-input.geojson"
            before_input.write_bytes(FIXTURE.read_bytes())
            source = json.loads(FIXTURE.read_text(encoding="utf-8"))
            source["features"] = source["features"][:-1]
            source["features"][0]["properties"]["name"] += " revised"
            source["features"][0]["geometry"]["coordinates"] = [12.5, 22.5]
            source["features"].append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [40.0, 45.0]},
                "properties": {"id": "synthetic-added", "name": "Added fixture", "category": "demo"},
            })
            after_input.write_text(json.dumps(source), encoding="utf-8")
            before_dir, after_dir = root / "before", root / "after"
            self.assertEqual(build(before_input, before_dir), 0)
            self.assertEqual(build(after_input, after_dir), 0)
            report, errors = compare(before_dir / "normalized.geojson", after_dir / "normalized.geojson")
            self.assertEqual(errors, [])
            self.assertIsNotNone(report)
            assert report is not None
            summary = report["summary"]
            self.assertEqual(summary["added_count"], 1)
            self.assertEqual(summary["removed_count"], 1)
            self.assertEqual(summary["changed_count"], 1)
            self.assertEqual(summary["unchanged_count"], 1)
            self.assertTrue(summary["extent_changed"])
            self.assertEqual(report["added_ids"], ["synthetic-added"])
            self.assertEqual(len(report["removed_ids"]), 1)
            changed = report["changed_features"][0]
            self.assertTrue(changed["geometry_changed"])
            self.assertIn("name", changed["changed_properties"])
            self.assertEqual(len(report["inputs"]["before"]["sha256"]), 64)

    def test_change_report_ignores_feature_order(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            original = json.loads(FIXTURE.read_text(encoding="utf-8"))
            reordered = dict(original)
            reordered["features"] = list(reversed(original["features"]))
            before = root / "before.geojson"
            after = root / "after.geojson"
            before.write_text(json.dumps(original), encoding="utf-8")
            after.write_text(json.dumps(reordered), encoding="utf-8")
            before_dir, after_dir = root / "before-out", root / "after-out"
            self.assertEqual(build(before, before_dir), 0)
            self.assertEqual(build(after, after_dir), 0)
            report, errors = compare(before_dir / "normalized.geojson", after_dir / "normalized.geojson")
            self.assertEqual(errors, [])
            self.assertIsNotNone(report)
            assert report is not None
            self.assertEqual(report["summary"]["added_count"], 0)
            self.assertEqual(report["summary"]["removed_count"], 0)
            self.assertEqual(report["summary"]["changed_count"], 0)
            self.assertFalse(report["summary"]["extent_changed"])

    def test_change_report_rejects_duplicate_ids_and_malformed_input(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            raw = json.loads(FIXTURE.read_text(encoding="utf-8"))
            raw["features"][1]["properties"]["id"] = raw["features"][0]["properties"]["id"]
            duplicate = root / "duplicate.geojson"
            duplicate.write_text(json.dumps(raw), encoding="utf-8")
            malformed = root / "malformed.geojson"
            malformed.write_text("{broken", encoding="utf-8")
            report, errors = compare(duplicate, malformed)
            self.assertIsNone(report)
            self.assertTrue(any("duplicate feature id" in error for error in errors), errors)
            self.assertTrue(any("after: cannot read valid UTF-8 JSON" in error for error in errors), errors)


    def test_change_report_classifies_coordinate_movement_with_configurable_threshold(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            before = json.loads(FIXTURE.read_text(encoding="utf-8"))
            after = json.loads(FIXTURE.read_text(encoding="utf-8"))
            after["features"][0]["geometry"]["coordinates"] = [
                before["features"][0]["geometry"]["coordinates"][0] + 0.0013,
                before["features"][0]["geometry"]["coordinates"][1],
            ]
            before_path, after_path = root / "before.geojson", root / "after.geojson"
            before_path.write_text(json.dumps(before), encoding="utf-8")
            after_path.write_text(json.dumps(after), encoding="utf-8")
            report, errors = compare(before_path, after_path, movement_threshold_m=200)
            self.assertEqual(errors, [])
            assert report is not None
            changed = report["changed_features"][0]
            self.assertTrue(changed["geometry_changed"])
            self.assertGreater(changed["movement_meters"], 100)
            self.assertLess(changed["movement_meters"], 150)
            self.assertFalse(changed["movement_exceeds_threshold"])
            self.assertEqual(changed["change_class"], "geometry_moved_at_or_below_threshold")
            report, errors = compare(before_path, after_path, movement_threshold_m=50)
            self.assertEqual(errors, [])
            assert report is not None
            self.assertTrue(report["changed_features"][0]["movement_exceeds_threshold"])
            self.assertEqual(report["summary"]["geometry_movement_over_threshold_count"], 1)

    def test_change_report_distance_handles_antimeridian_and_rejects_bad_threshold(self) -> None:
        from scripts.compare_product_runs import distance_meters
        distance = distance_meters([179.999, 0], [-179.999, 0])
        self.assertGreater(distance, 200)
        self.assertLess(distance, 230)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "input.geojson"
            source.write_bytes(FIXTURE.read_bytes())
            report, errors = compare(source, source, movement_threshold_m=float("nan"))
            self.assertIsNone(report)
            self.assertTrue(any("finite non-negative" in error for error in errors))


    def test_change_report_applies_attribute_review_rules_and_hashes_configuration(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            before = json.loads(FIXTURE.read_text(encoding="utf-8"))
            after = json.loads(FIXTURE.read_text(encoding="utf-8"))
            after["features"][0]["properties"]["category"] = "updated-category"
            before_path, after_path = root / "before.geojson", root / "after.geojson"
            rules_path = root / "rules.json"
            before_path.write_text(json.dumps(before), encoding="utf-8")
            after_path.write_text(json.dumps(after), encoding="utf-8")
            rules_path.write_text(json.dumps({"default": "low", "geometry": "medium", "properties": {"category": "critical", "name": "high"}}), encoding="utf-8")
            report, errors = compare(before_path, after_path, rules_path=rules_path)
            self.assertEqual(errors, [])
            assert report is not None
            self.assertEqual(report["changed_features"][0]["review_severity"], "critical")
            self.assertEqual(len(report["review_configuration"]["rules_sha256"]), 64)

    def test_change_report_rejects_invalid_review_rules(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source, rules = root / "input.geojson", root / "rules.json"
            source.write_bytes(FIXTURE.read_bytes())
            rules.write_text(json.dumps({"default": "urgent"}), encoding="utf-8")
            report, errors = compare(source, source, rules_path=rules)
            self.assertIsNone(report)
            self.assertTrue(any("severities must be" in error for error in errors), errors)


    def test_release_gate_requires_run_ids_and_blocks_critical_changes(self) -> None:
        report = {"inputs": {"before": {"run_id": "baseline-v1"}, "after": {"run_id": "candidate-v2"}}, "summary": {"removed_count": 0, "added_count": 0}, "changed_features": [{"id": "p1", "review_severity": "critical"}]}
        rules = {"block_on_severity": ["critical"], "max_removed": 0, "require_run_ids": True}
        result, errors = evaluate(report, rules)
        self.assertEqual(errors, [])
        self.assertEqual(result["decision"], "blocked")
        report["changed_features"] = []
        result, errors = evaluate(report, rules)
        self.assertEqual(errors, [])
        self.assertEqual(result["decision"], "eligible_for_human_release_review")
        del report["inputs"]["before"]["run_id"]
        result, errors = evaluate(report, rules)
        self.assertEqual(errors, [])
        self.assertEqual(result["decision"], "blocked")

    def test_release_gate_rejects_invalid_policy(self) -> None:
        result, errors = evaluate({"inputs": {}, "summary": {}, "changed_features": []}, {"max_removed": -1})
        self.assertIsNone(result)
        self.assertTrue(any("non-negative integer" in e for e in errors))


    def test_baseline_registry_immutability_and_hash_drift(self) -> None:
        from scripts.baseline_registry import main as registry_main, verify_entry
        from unittest.mock import patch
        import contextlib, io
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); registry = root / "registry.json"; dataset = root / "data.geojson"
            dataset.write_bytes(FIXTURE.read_bytes())
            argv = ["baseline_registry.py", "register", "--registry", str(registry), "--run-id", "places-v1", "--dataset", str(dataset), "--pipeline-version", "0.1.0", "--description", "reviewed fixture"]
            with patch("sys.argv", argv), contextlib.redirect_stdout(io.StringIO()): self.assertEqual(registry_main(), 0)
            entry, errors = verify_entry(registry, "places-v1", dataset)
            self.assertEqual(errors, []); self.assertEqual(entry["run_id"], "places-v1")
            with patch("sys.argv", argv), contextlib.redirect_stderr(io.StringIO()): self.assertEqual(registry_main(), 1)
            dataset.write_text(dataset.read_text(encoding="utf-8") + " ", encoding="utf-8")
            entry, errors = verify_entry(registry, "places-v1", dataset)
            self.assertIsNone(entry); self.assertTrue(any("hash mismatch" in e for e in errors))

    def test_change_comparison_rejects_unregistered_candidate(self) -> None:
        from scripts.baseline_registry import main as registry_main
        from unittest.mock import patch
        import contextlib, io
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); registry = root / "registry.json"; before = root / "before.geojson"; after = root / "after.geojson"
            before.write_bytes(FIXTURE.read_bytes()); after.write_bytes(FIXTURE.read_bytes())
            argv = ["baseline_registry.py", "register", "--registry", str(registry), "--run-id", "baseline-v1", "--dataset", str(before), "--pipeline-version", "0.1.0", "--description", "baseline"]
            with patch("sys.argv", argv), contextlib.redirect_stdout(io.StringIO()): self.assertEqual(registry_main(), 0)
            report, errors = compare(before, after, before_id="baseline-v1", after_id="candidate-v1", registry_path=registry)
            self.assertIsNone(report); self.assertTrue(any("not registered" in e for e in errors))

    def test_release_evidence_manifest_is_deterministic_and_fails_closed_without_approval(self) -> None:
        from scripts.build_release_evidence import build_manifest
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product"
            self.assertEqual(build(FIXTURE, product), 0)
            dataset = product / "normalized.geojson"
            registry = root / "registry.json"
            from scripts.baseline_registry import main as registry_main
            from unittest.mock import patch
            import contextlib, io
            for run_id in ("baseline-v1", "candidate-v1"):
                argv = ["baseline_registry.py", "register", "--registry", str(registry), "--run-id", run_id, "--dataset", str(dataset), "--pipeline-version", "0.1.0", "--description", "synthetic test run"]
                with patch("sys.argv", argv), contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(registry_main(), 0)
            change, errors = compare(dataset, dataset, before_id="baseline-v1", after_id="candidate-v1", registry_path=registry)
            self.assertEqual(errors, [])
            change_path = root / "change.json"
            change_path.write_text(json.dumps(change), encoding="utf-8")
            gate, errors = evaluate(change, {"block_on_severity": ["critical"], "max_removed": 0, "require_run_ids": True})
            self.assertEqual(errors, [])
            gate_path = root / "gate.json"
            gate_path.write_text(json.dumps(gate), encoding="utf-8")
            reviews = {"schema_version": 1, "review_type": "zqm_observatory_release_reviews", "gates": {}}
            for name in ("source_rights", "privacy", "factual_quality", "product_owner"):
                reviews["gates"][name] = {"decision": "approved", "reviewer": "reviewer-example", "reviewed_on": "2026-10-25", "evidence": "test-only evidence"}
            reviews_path = root / "reviews.json"
            reviews_path.write_text(json.dumps(reviews), encoding="utf-8")
            policy_path = root / "policy.json"
            policy = {"block_on_severity": ["critical"], "max_removed": 0, "require_run_ids": True}
            policy_path.write_text(json.dumps(policy), encoding="utf-8")
            args = (product, dataset, dataset, registry, change_path, gate_path, reviews_path, policy_path)
            manifest_a, errors = build_manifest(*args)
            self.assertEqual(errors, [])
            manifest_b, errors = build_manifest(*args)
            self.assertEqual(errors, [])
            self.assertEqual(manifest_a, manifest_b)
            self.assertEqual(manifest_a["decision"], "blocked")
            self.assertFalse(manifest_a["publication_authorized_by_manifest"])
            from scripts.build_release_evidence import canonical_json
            from scripts.verify_release_evidence import verify_manifest
            bundle = root / "bundle"
            bundle.mkdir()
            source_map = {
                "normalized_dataset": product / "normalized.geojson",
                "qa_report": product / "qa-report.json",
                "provenance": product / "provenance.json",
                "before_dataset": dataset,
                "after_dataset": dataset,
                "baseline_registry": registry,
                "change_report": change_path,
                "release_gate_report": gate_path,
                "release_policy": policy_path,
                "human_reviews": reviews_path,
            }
            for role, source in source_map.items():
                (bundle / manifest_a["artifacts"][role]["bundle_file"]).write_bytes(source.read_bytes())
            manifest_path = bundle / "manifest.json"
            manifest_path.write_bytes(canonical_json(manifest_a))
            self.assertEqual(verify_manifest(manifest_path), [])
            (bundle / manifest_a["artifacts"]["release_policy"]["bundle_file"]).write_text('{"block_on_severity":[],"max_removed":99,"require_run_ids":false}', encoding="utf-8")
            self.assertTrue(any("SHA-256 mismatch" in error for error in verify_manifest(manifest_path)))
            reviews["gates"]["privacy"]["decision"] = "pending"
            reviews_path.write_text(json.dumps(reviews), encoding="utf-8")
            manifest, errors = build_manifest(*args)
            self.assertIsNone(manifest)
            self.assertTrue(any("privacy is not approved" in error for error in errors), errors)

    def test_release_evidence_detects_change_report_hash_drift(self) -> None:
        from scripts.build_release_evidence import build_manifest
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product"
            self.assertEqual(build(FIXTURE, product), 0)
            dataset = product / "normalized.geojson"
            registry = root / "registry.json"
            registry.write_text(json.dumps({"schema_version": 1, "registry_type": "zqm_observatory_baseline_registry", "runs": [
                {"run_id": "base-v1", "dataset_sha256": __import__("hashlib").sha256(dataset.read_bytes()).hexdigest(), "pipeline_version": "0.1.0", "description": "baseline"},
                {"run_id": "candidate-v1", "dataset_sha256": __import__("hashlib").sha256(dataset.read_bytes()).hexdigest(), "pipeline_version": "0.1.0", "description": "candidate"}
            ]}), encoding="utf-8")
            change, _ = compare(dataset, dataset, before_id="base-v1", after_id="candidate-v1")
            change["inputs"]["after"]["sha256"] = "0" * 64
            change_path = root / "change.json"
            change_path.write_text(json.dumps(change), encoding="utf-8")
            gate_path = root / "gate.json"
            gate_path.write_text(json.dumps({"decision": "eligible_for_human_release_review", "violations": []}), encoding="utf-8")
            policy_path = root / "policy.json"
            policy_path.write_text(json.dumps({"block_on_severity": ["critical"], "max_removed": 0, "require_run_ids": True}), encoding="utf-8")
            reviews_path = root / "reviews.json"
            reviews_path.write_text(json.dumps({"schema_version": 1, "review_type": "zqm_observatory_release_reviews", "gates": {
                name: {"decision": "approved", "reviewer": "reviewer", "reviewed_on": "2026-10-25", "evidence": "record"}
                for name in ("source_rights", "privacy", "factual_quality", "product_owner")
            }}), encoding="utf-8")
            manifest, errors = build_manifest(product, dataset, dataset, registry, change_path, gate_path, reviews_path, policy_path)
            self.assertIsNone(manifest)
            self.assertTrue(any("hash does not match supplied file" in error for error in errors), errors)

if __name__ == "__main__":
    unittest.main()
