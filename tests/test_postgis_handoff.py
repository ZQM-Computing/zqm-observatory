from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "run_postgis_handoff.py"
FIXTURE = ROOT / "tests" / "fixtures" / "synthetic-places.geojson"


class PostGISHandoffContractTests(unittest.TestCase):
    def test_fixture_is_small_stable_and_synthetic(self):
        document = json.loads(FIXTURE.read_text(encoding="utf-8"))
        self.assertEqual(document["type"], "FeatureCollection")
        features = document["features"]
        self.assertEqual(len(features), 3)
        identifiers = [item["properties"]["id"] for item in features]
        self.assertEqual(len(identifiers), len(set(identifiers)))
        self.assertTrue(all(item["geometry"]["type"] == "Point" for item in features))

    def test_handoff_fails_closed_and_marks_publication_unauthorized(self):
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertIn('SCHEMA = "observatory_handoff_ci"', source)
        self.assertIn("refusing to reuse existing schema", source)
        self.assertIn('"publication_authorized": False', source)
        self.assertIn('"extent_matches_input"', source)
        self.assertIn('"geometry_srid_is_4326"', source)
        self.assertIn('"stable_ids_unique"', source)
        self.assertIn('"DROP SCHEMA IF EXISTS {} CASCADE"', source)

    def test_database_values_are_parameterized_and_schema_is_identifier_quoted(self):
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertIn("sql.Identifier(SCHEMA)", source)
        self.assertIn("(props[\"id\"], props[\"name\"], props[\"category\"], lon, lat)", source)
        self.assertIn("VALUES (%s, %s, %s, ST_SetSRID(ST_MakePoint(%s, %s), 4326))", source)

    def test_handoff_does_not_target_live_services_or_use_source_records(self):
        source = SCRIPT.read_text(encoding="utf-8").lower()
        self.assertIn("disposable ci database", source)
        self.assertIn("synthetic fixture", source)
        self.assertNotIn("requests.get(", source)
        self.assertNotIn("http://", source)
        self.assertNotIn("https://", source)


if __name__ == "__main__":
    unittest.main()
