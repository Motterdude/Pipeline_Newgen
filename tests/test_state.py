from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from _path import ROOT  # noqa: F401
from pipeline_newgen_rev1.workflows.load_sweep.state import load_feature_state, save_feature_state


class StateTests(unittest.TestCase):
    def test_state_roundtrip_keeps_boolean_selection(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "feature_state.json"
            save_feature_state(path, "sweep", {"apply_sweep_binning": True, "run_compare_plots": False})
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertIn("saved_at", payload)
            loaded = load_feature_state(path, "sweep")
            self.assertTrue(loaded["apply_sweep_binning"])
            self.assertFalse(loaded["run_compare_plots"])


if __name__ == "__main__":
    unittest.main()
