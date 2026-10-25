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

    def test_directory_and_publication_dates_must_match(self) -> None:
        product_dir = self.make_product()
        path = product_dir / "product.json"
        product = json.loads(path.read_text(encoding="utf-8"))
        product["publication_date"] = "2026-10-24"
        path.write_text(json.dumps(product), encoding="utf-8")
        errors = validate_product(product_dir)
        self.assertTrue(any("publication_date must match directory date" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
