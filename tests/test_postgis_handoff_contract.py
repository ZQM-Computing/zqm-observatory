"""Safety contract tests for the disposable PostGIS handoff adapter."""
from __future__ import annotations

import os
import subprocess
import sys
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "run_postgis_handoff.py"


class PostGISHandoffContractTests(unittest.TestCase):
    def test_refuses_without_explicit_disposable_opt_in(self) -> None:
        env = os.environ.copy()
        env.pop("OBSERVATORY_POSTGIS_DISPOSABLE", None)
        env["PGDATABASE"] = "observatory_test"
        result = subprocess.run(
            [sys.executable, str(SCRIPT)],
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Refusing database writes", result.stderr)

    def test_refuses_database_name_other_than_disposable_test_database(self) -> None:
        env = os.environ.copy()
        env["OBSERVATORY_POSTGIS_DISPOSABLE"] = "1"
        env["PGDATABASE"] = "production"
        result = subprocess.run(
            [sys.executable, str(SCRIPT)],
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("PGDATABASE must be exactly 'observatory_test'", result.stderr)

    def test_adapter_is_transactional_and_marks_publication_unauthorized(self) -> None:
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertIn("conn.rollback()", source)
        self.assertIn('"publication_authorized": False', source)
        self.assertIn("DROP SCHEMA IF EXISTS observatory_handoff_test CASCADE", source)
        self.assertIn("ST_SetSRID(ST_MakePoint", source)
        self.assertIn("aclexplode", source)
        self.assertIn("a.grantee = 0", source)
        self.assertIn('"role_boundary_checks": role_checks', source)
        self.assertIn('"connected_database": "observatory_test"', source)


if __name__ == "__main__":
    unittest.main()
