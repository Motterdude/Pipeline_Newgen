from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pandas as pd

from _path import ROOT  # noqa: F401
from pipeline_newgen_rev1.adapters import InputFileMeta
from pipeline_newgen_rev1.runtime.plot_point_filter import (
    apply_plot_point_filter,
    prompt_plot_point_filter,
    prompt_plot_point_filter_from_metas,
)


class PlotPointFilterTests(unittest.TestCase):
    def test_prompt_plot_point_filter_from_metas_uses_prompt_override(self) -> None:
        meta = InputFileMeta(
            path=Path("C:/tmp/50KW_D85B15.xlsx"),
            basename="sample",
            source_type="LABVIEW",
            load_kw=50.0,
            dies_pct=85.0,
            biod_pct=15.0,
            etoh_pct=0.0,
            h2o_pct=0.0,
        )

        selected = prompt_plot_point_filter_from_metas(
            [meta],
            prompt_func=lambda fuel_labels, load_values, counts: {("D85B15", 50.0)},
        )

        self.assertEqual(selected, {("D85B15", 50.0)})

    def test_apply_plot_point_filter_keeps_selected_rows(self) -> None:
        frame = pd.DataFrame(
            [
                {"Fuel_Label": "D85B15", "Load_kW": 50.0, "Value": 1},
                {"Fuel_Label": "E75H25", "Load_kW": 45.0, "Value": 2},
            ]
        )

        filtered = apply_plot_point_filter(frame, {("E75H25", 45.0)})

        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered.iloc[0]["Fuel_Label"], "E75H25")

    def test_prompt_plot_point_filter_uses_dataframe_fallback(self) -> None:
        frame = pd.DataFrame(
            [
                {"DIES_pct": 85.0, "BIOD_pct": 15.0, "EtOH_pct": 0.0, "H2O_pct": 0.0, "Load_kW": 50.0},
            ]
        )

        selected = prompt_plot_point_filter(
            frame,
            prompt_func=lambda fuel_labels, load_values, counts: {("D85B15", 50.0)},
        )

        self.assertEqual(selected, {("D85B15", 50.0)})


if __name__ == "__main__":
    unittest.main()
