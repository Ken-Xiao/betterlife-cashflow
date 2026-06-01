#!/usr/bin/env python3
"""Database API policy tests for the local deployment server."""

from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SERVER_PY = ROOT / "deploy_server.py"


def load_server_module():
    spec = importlib.util.spec_from_file_location("cashflow_deploy_server", SERVER_PY)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class ServerApiPolicyTests(unittest.TestCase):
    def test_save_and_filter_keep_model_boundaries_explicit(self):
        server = load_server_module()
        rows = [
            {"id": "1", "modelId": "model_a", "asset_id": "alpha"},
            {"id": "2", "modelId": "model_b", "asset_id": "alpha"},
            {"id": "3", "modelId": "model_a", "asset_id": "beta"},
        ]

        with tempfile.TemporaryDirectory() as tmp:
            original_data_file = server.DATA_FILE
            try:
                server.DATA_FILE = Path(tmp) / "rows.json"
                server.save_rows(rows)
                loaded = server.load_rows()
                filtered = server.filter_asset_rows(loaded, model_id="model_a", q="alpha")
                self.assertEqual([row["id"] for row in filtered], ["1"])
            finally:
                server.DATA_FILE = original_data_file

    def test_validate_asset_row_rejects_rows_without_real_model_id(self):
        server = load_server_module()

        invalid, error = server.validate_asset_row({"asset_id": "orphan"})
        self.assertFalse(invalid)
        self.assertEqual(error, "modelId is required")

        invalid, error = server.validate_asset_row({"asset_id": "orphan", "modelId": "unknown"})
        self.assertFalse(invalid)
        self.assertEqual(error, "modelId is required")

        valid, error = server.validate_asset_row({"asset_id": "owned", "modelId": "model_a"})
        self.assertTrue(valid)
        self.assertEqual(error, "")


if __name__ == "__main__":
    unittest.main()
