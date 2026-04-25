"""Tests for the special_load_plots subpackage."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pandas as pd

from _path import ROOT  # noqa: F401

from pipeline_newgen_rev1.runtime.special_load_plots.ethanol_equivalent import (
    _blend_mask,
    plot_ethanol_equivalent_consumption_overlay,
    plot_ethanol_equivalent_ratio,
)
from pipeline_newgen_rev1.runtime.special_load_plots.machine_scenarios import (
    _prepare_machine_scenario_plot_df,
    plot_machine_scenario_suite,
)
from pipeline_newgen_rev1.runtime.final_table.constants import (
    MACHINE_SCENARIO_SPECS,
    SCENARIO_REFERENCE_FUEL_LABEL,
)
from pipeline_newgen_rev1.runtime.final_table._machine_scenarios import _scenario_machine_col


class TestBlendMask(unittest.TestCase):
    def test_exact_match(self) -> None:
        df = pd.DataFrame({"EtOH_pct": [94.0, 75.0], "H2O_pct": [6.0, 25.0]})
        mask = _blend_mask(df, etoh_pct=94.0, h2o_pct=6.0)
        self.assertTrue(mask.iloc[0])
        self.assertFalse(mask.iloc[1])

    def test_within_tolerance(self) -> None:
        df = pd.DataFrame({"EtOH_pct": [94.5], "H2O_pct": [5.5]})
        mask = _blend_mask(df, etoh_pct=94.0, h2o_pct=6.0, tol=0.6)
        self.assertTrue(mask.iloc[0])

    def test_outside_tolerance(self) -> None:
        df = pd.DataFrame({"EtOH_pct": [90.0], "H2O_pct": [6.0]})
        mask = _blend_mask(df, etoh_pct=94.0, h2o_pct=6.0, tol=0.6)
        self.assertFalse(mask.iloc[0])

    def test_missing_columns(self) -> None:
        df = pd.DataFrame({"X": [1.0]})
        mask = _blend_mask(df, etoh_pct=94.0, h2o_pct=6.0)
        self.assertFalse(mask.iloc[0])


class TestEthanolOverlay(unittest.TestCase):
    def test_missing_columns_returns_none(self) -> None:
        df = pd.DataFrame({"X": [1.0]})
        with tempfile.TemporaryDirectory() as td:
            result = plot_ethanol_equivalent_consumption_overlay(df, plot_dir=Path(td))
            self.assertIsNone(result)

    def test_with_data_generates_png(self) -> None:
        df = pd.DataFrame({
            "UPD_Power_Bin_kW": [10.0, 20.0, 10.0],
            "Fuel_E94H6_eq_kg_h": [1.0, 2.0, 1.5],
            "EtOH_pct": [94.0, 94.0, 75.0],
            "H2O_pct": [6.0, 6.0, 25.0],
        })
        with tempfile.TemporaryDirectory() as td:
            result = plot_ethanol_equivalent_consumption_overlay(df, plot_dir=Path(td))
            self.assertIsNotNone(result)
            self.assertTrue(result.exists())


class TestEthanolRatio(unittest.TestCase):
    def test_missing_columns_returns_none(self) -> None:
        df = pd.DataFrame({"X": [1.0]})
        with tempfile.TemporaryDirectory() as td:
            result = plot_ethanol_equivalent_ratio(df, plot_dir=Path(td))
            self.assertIsNone(result)

    def test_with_data_generates_png(self) -> None:
        df = pd.DataFrame({
            "Load_kW": [10.0, 20.0, 10.0, 20.0],
            "UPD_Power_Bin_kW": [10.0, 20.0, 10.0, 20.0],
            "Fuel_E94H6_eq_kg_h": [1.0, 2.0, 1.1, 2.1],
            "EtOH_pct": [94.0, 94.0, 75.0, 75.0],
            "H2O_pct": [6.0, 6.0, 25.0, 25.0],
        })
        with tempfile.TemporaryDirectory() as td:
            result = plot_ethanol_equivalent_ratio(df, plot_dir=Path(td))
            self.assertIsNotNone(result)
            self.assertTrue(result.exists())


class TestPrepareMachineScenario(unittest.TestCase):
    def test_filters_by_fuel_label(self) -> None:
        df = pd.DataFrame({
            "Load_kW": [10.0, 20.0],
            "Fuel_Label": [SCENARIO_REFERENCE_FUEL_LABEL, "D85B15"],
        })
        out, x_col, x_label = _prepare_machine_scenario_plot_df(df)
        self.assertEqual(len(out), 1)
        self.assertEqual(x_col, "Load_kW")

    def test_empty_df(self) -> None:
        out, x_col, x_label = _prepare_machine_scenario_plot_df(pd.DataFrame())
        self.assertTrue(out.empty)
        self.assertIsNone(x_col)


class TestMachineScenarioSuite(unittest.TestCase):
    def test_empty_df_no_crash(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            count = plot_machine_scenario_suite(pd.DataFrame(), plot_dir=Path(td))
            self.assertEqual(count, 0)

    def test_with_data_generates_pngs(self) -> None:
        rows = []
        for load in [10.0, 20.0, 30.0]:
            row = {
                "Load_kW": load,
                "Fuel_Label": SCENARIO_REFERENCE_FUEL_LABEL,
            }
            for spec in MACHINE_SCENARIO_SPECS:
                for suffix in [
                    "Diesel_Custo_R_h", "E94H6_Custo_R_h", "U_E94H6_Custo_R_h",
                    "Economia_R_h", "U_Economia_R_h",
                    "Diesel_L_h", "E94H6_L_h", "U_E94H6_L_h",
                    "E94H6_L_ano", "U_E94H6_L_ano",
                    "Diesel_Custo_R_ano", "E94H6_Custo_R_ano", "U_E94H6_Custo_R_ano",
                    "Economia_R_ano", "U_Economia_R_ano",
                ]:
                    row[_scenario_machine_col(spec["key"], suffix)] = load * 0.5
            rows.append(row)
        df = pd.DataFrame(rows)
        with tempfile.TemporaryDirectory() as td:
            count = plot_machine_scenario_suite(df, plot_dir=Path(td))
            self.assertEqual(count, 6)
            pngs = list(Path(td).glob("*.png"))
            self.assertEqual(len(pngs), 6)


if __name__ == "__main__":
    unittest.main()
