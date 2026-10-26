from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.validate_products import validate_data_dir, validate_product


class ProductValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.data = self.root / "data"
        self.data.mkdir()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def make_product(self) -> Path:
        folder = "2026-10-25-volusia-community-brief"
        product_dir = self.data / folder
        product_dir.mkdir()
        product = {
            "schema_version": 1,
            "product_id": folder,
            "title": "Volusia community brief",
            "publication_date": "2026-10-25",
            "geographic_scope": "Named public area, Volusia County, Florida",
            "summary": "A dated example product summary with scope and limitations.",
            "license": "CC BY 4.0; upstream terms remain applicable.",
            "source_ids": ["local-open-data"],
            "data_files": ["brief.csv"],
            "field_verification": {"status": "not_verified", "notes": "No field visit has occurred; this limitation is explicit."},
            "privacy_review": {
                "reviewed": True,
                "reviewed_by": "Test reviewer",
                "review_date": "2026-10-25",
                "individual_level_data": False,
                "personal_data": False,
                "children_identifiable_data": False,
            },
        }
        sources = [{
            "id": "local-open-data",
            "title": "Example public dataset",
            "publisher": "Example public agency",
            "url": "https://example.gov/dataset",
            "retrieval_date": "2026-10-24",
            "license": "Public data; confirm terms before publication",
            "supports": ["The mapped feature locations in the brief"],
        }]
        (product_dir / "product.json").write_text(json.dumps(product), encoding="utf-8")
        (product_dir / "sources.json").write_text(json.dumps(sources), encoding="utf-8")
        (product_dir / "method.md").write_text("# Method\n\n" + "Repeatable processing step. " * 8, encoding="utf-8")
        (product_dir / "brief.csv").write_text("id,value\n1,example\n", encoding="utf-8")
        return product_dir

    def test_empty_data_directory_is_valid_before_first_product(self) -> None:
        self.assertEqual(validate_data_dir(self.data), [])

    def test_complete_bundle_passes_structural_gate(self) -> None:
        product_dir = self.make_product()
        self.assertEqual(validate_product(product_dir), [])

    def test_duplicate_json_keys_are_rejected(self) -> None:
        product_dir = self.make_product()
        path = product_dir / "product.json"
        text = path.read_text(encoding="utf-8")
        text = text.replace('"title": "Volusia community brief",', '"title": "First title", "title": "Second title",')
        path.write_text(text, encoding="utf-8")
        errors = validate_product(product_dir)
        self.assertTrue(any("duplicate JSON object key" in error for error in errors))

    def test_invalid_utf8_json_fails_without_crashing(self) -> None:
        product_dir = self.make_product()
        (product_dir / "product.json").write_bytes(b'{"title":"\\xff"}')
        errors = validate_product(product_dir)
        self.assertTrue(any("cannot read valid JSON" in error for error in errors))

    def test_windows_style_path_is_rejected(self) -> None:
        product_dir = self.make_product()
        path = product_dir / "product.json"
        product = json.loads(path.read_text(encoding="utf-8"))
        product["data_files"] = ["..\\outside.csv"]
        path.write_text(json.dumps(product), encoding="utf-8")
        errors = validate_product(product_dir)
        self.assertTrue(any("unsafe data_files entry" in error for error in errors))

    def test_windows_drive_prefixed_paths_are_rejected(self) -> None:
        product_dir = self.make_product()
        path = product_dir / "product.json"
        for unsafe_path in ("C:/outside.csv", "C:outside.csv", "z:/nested/file.csv"):
            with self.subTest(path=unsafe_path):
                product = json.loads(path.read_text(encoding="utf-8"))
                product["data_files"] = [unsafe_path]
                path.write_text(json.dumps(product), encoding="utf-8")
                errors = validate_product(product_dir)
                self.assertTrue(any("unsafe data_files entry" in error for error in errors))

    def test_dot_and_empty_path_segments_are_rejected(self) -> None:
        product_dir = self.make_product()
        path = product_dir / "product.json"
        product = json.loads(path.read_text(encoding="utf-8"))
        product["data_files"] = ["./brief.csv"]
        path.write_text(json.dumps(product), encoding="utf-8")
        errors = validate_product(product_dir)
        self.assertTrue(any("unsafe data_files entry" in error for error in errors))

    def test_malformed_ipv6_url_fails_without_crashing(self) -> None:
        product_dir = self.make_product()
        path = product_dir / "sources.json"
        sources = json.loads(path.read_text(encoding="utf-8"))
        sources[0]["url"] = "https://[not-an-ipv6-address]/dataset"
        path.write_text(json.dumps(sources), encoding="utf-8")
        errors = validate_product(product_dir)
        self.assertTrue(any("valid HTTPS URL" in error for error in errors))

    def test_missing_data_file_fails(self) -> None:
        product_dir = self.make_product()
        (product_dir / "brief.csv").unlink()
        errors = validate_product(product_dir)
        self.assertTrue(any("listed data file does not exist" in error for error in errors))

    def test_private_or_identifying_data_flags_fail(self) -> None:
        product_dir = self.make_product()
        path = product_dir / "product.json"
        product = json.loads(path.read_text(encoding="utf-8"))
        product["privacy_review"]["children_identifiable_data"] = True
        path.write_text(json.dumps(product), encoding="utf-8")
        errors = validate_product(product_dir)
        self.assertTrue(any("children_identifiable_data must be false" in error for error in errors))

    def test_path_traversal_is_rejected(self) -> None:
        product_dir = self.make_product()
        path = product_dir / "product.json"
        product = json.loads(path.read_text(encoding="utf-8"))
        product["data_files"] = ["../outside.csv"]
        path.write_text(json.dumps(product), encoding="utf-8")
        errors = validate_product(product_dir)
        self.assertTrue(any("unsafe data_files entry" in error for error in errors))

    def test_https_url_requires_a_real_hostname(self) -> None:
        product_dir = self.make_product()
        path = product_dir / "sources.json"
        sources = json.loads(path.read_text(encoding="utf-8"))
        sources[0]["url"] = "https://"
        path.write_text(json.dumps(sources), encoding="utf-8")
        errors = validate_product(product_dir)
        self.assertTrue(any("valid HTTPS URL" in error for error in errors))

    def test_duplicate_declared_sources_fail(self) -> None:
        product_dir = self.make_product()
        path = product_dir / "product.json"
        product = json.loads(path.read_text(encoding="utf-8"))
        product["source_ids"] = ["local-open-data", "local-open-data"]
        path.write_text(json.dumps(product), encoding="utf-8")
        errors = validate_product(product_dir)
        self.assertTrue(any("source_ids must be unique" in error for error in errors))

    def test_symlink_data_file_is_rejected(self) -> None:
        product_dir = self.make_product()
        outside = self.root / "outside.csv"
        outside.write_text("sensitive,example\\n", encoding="utf-8")
        link = product_dir / "linked.csv"
        link.symlink_to(outside)
        path = product_dir / "product.json"
        product = json.loads(path.read_text(encoding="utf-8"))
        product["data_files"] = ["linked.csv"]
        path.write_text(json.dumps(product), encoding="utf-8")
        errors = validate_product(product_dir)
        self.assertTrue(any("symlinks are not allowed inside product bundles" in error for error in errors))

    def test_malformed_url_port_fails(self) -> None:
        product_dir = self.make_product()
        path = product_dir / "sources.json"
        sources = json.loads(path.read_text(encoding="utf-8"))
        sources[0]["url"] = "https://example.gov:bad/dataset"
        path.write_text(json.dumps(sources), encoding="utf-8")
        errors = validate_product(product_dir)
        self.assertTrue(any("valid port" in error for error in errors))

    def test_undeclared_sidecar_file_fails(self) -> None:
        product_dir = self.make_product()
        (product_dir / "private-notes.txt").write_text("unreviewed sidecar", encoding="utf-8")
        errors = validate_product(product_dir)
        self.assertTrue(any("undeclared file" in error and "private-notes.txt" in error for error in errors))

    def test_nested_undeclared_file_fails(self) -> None:
        product_dir = self.make_product()
        nested = product_dir / "supporting"
        nested.mkdir()
        (nested / "extra.csv").write_text("id,value\\n1,unreviewed\\n", encoding="utf-8")
        errors = validate_product(product_dir)
        self.assertTrue(any("undeclared file" in error and "supporting/extra.csv" in error for error in errors))

    def test_symlinked_method_file_is_rejected_before_reading(self) -> None:
        product_dir = self.make_product()
        method = product_dir / "method.md"
        method.unlink()
        outside = self.root / "outside-method.md"
        outside.write_text("# Method\\n" + "external content " * 10, encoding="utf-8")
        method.symlink_to(outside)
        errors = validate_product(product_dir)
        self.assertTrue(any("symlinks are not allowed" in error for error in errors))

    def test_symlinked_product_directory_is_rejected(self) -> None:
        real_product = self.make_product()
        linked_product = self.data / "2026-10-25-linked-product"
        linked_product.symlink_to(real_product, target_is_directory=True)
        errors = validate_product(linked_product)
        self.assertTrue(any("product directory must not be a symlink" in error for error in errors))

    def test_directory_and_publication_dates_must_match(self) -> None:
        product_dir = self.make_product()
        path = product_dir / "product.json"
        product = json.loads(path.read_text(encoding="utf-8"))
        product["publication_date"] = "2026-10-24"
        path.write_text(json.dumps(product), encoding="utf-8")
        errors = validate_product(product_dir)
        self.assertTrue(any("publication_date must match directory date" in error for error in errors))

    def test_boolean_schema_version_is_rejected(self) -> None:
        product_dir = self.make_product()
        path = product_dir / "product.json"
        product = json.loads(path.read_text(encoding="utf-8"))
        product["schema_version"] = True
        path.write_text(json.dumps(product), encoding="utf-8")
        errors = validate_product(product_dir)
        self.assertTrue(any("schema_version must be integer 1" in error for error in errors))

    def test_source_retrieval_after_publication_date_is_rejected(self) -> None:
        product_dir = self.make_product()
        path = product_dir / "sources.json"
        sources = json.loads(path.read_text(encoding="utf-8"))
        sources[0]["retrieval_date"] = "2026-10-26"
        path.write_text(json.dumps(sources), encoding="utf-8")
        errors = validate_product(product_dir)
        self.assertTrue(any("retrieval_date must not be after product publication_date" in error for error in errors))

    def test_privacy_review_after_publication_date_is_rejected(self) -> None:
        product_dir = self.make_product()
        path = product_dir / "product.json"
        product = json.loads(path.read_text(encoding="utf-8"))
        product["privacy_review"]["review_date"] = "2026-10-26"
        path.write_text(json.dumps(product), encoding="utf-8")
        errors = validate_product(product_dir)
        self.assertTrue(any("privacy_review.review_date must not be after product publication_date" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
