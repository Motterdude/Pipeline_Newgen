"""Tests for _delta_vs_ref metrics in final_table."""
from __future__ import annotations

import math
import unittest

import numpy as np
import pandas as pd


def _make_df(fuels=("D85B15", "E75H25"), loads=(25.0, 50.0)):
    rows = []
    for fuel in fuels:
        for load in loads:
            base_nth = 30.0 if fuel == "D85B15" else 31.0
            base_bsfc = 250.0 if fuel == "D85B15" else 240.0
            rows.append({
                "Fuel_Label": fuel,
                "Load_kW": load,
                "n_th_pct": base_nth + load * 0.1,
                "uA_n_th_pct": 0.2,
                "uB_n_th_pct": 0.3,
                "uc_n_th_pct": 0.36,
                "U_n_th_pct": 0.72,
                "BSFC_g_kWh": base_bsfc + load * 0.5,
                "uA_BSFC_g_kWh": 2.0,
                "uB_BSFC_g_kWh": 3.0,
                "uc_BSFC_g_kWh": 3.6,
                "U_BSFC_g_kWh": 7.2,
                "DIES_pct": 85.0 if fuel == "D85B15" else 0.0,
                "BIOD_pct": 15.0 if fuel == "D85B15" else 0.0,
                "EtOH_pct": 0.0 if fuel == "D85B15" else 75.0,
                "H2O_pct": 0.0 if fuel == "D85B15" else 25.0,
            })
    return pd.DataFrame(rows)


class TestAttachDeltaVsRef(unittest.TestCase):
    def test_creates_columns(self):
        from pipeline_newgen_rev1.runtime.final_table._delta_vs_ref import (
            _attach_delta_vs_ref_metrics,
        )
        df = _make_df()
        out = _attach_delta_vs_ref_metrics(df)
        self.assertIn("Delta_pp_n_th_pct_vs_D85B15", out.columns)
        self.assertIn("U_Delta_pp_n_th_pct_vs_D85B15", out.columns)
        self.assertIn("Ref_D85B15_n_th_pct", out.columns)
        self.assertIn("Delta_pct_BSFC_g_kWh_vs_D85B15", out.columns)
        self.assertIn("U_Delta_pct_BSFC_g_kWh_vs_D85B15", out.columns)
        self.assertIn("Ref_D85B15_BSFC_g_kWh", out.columns)

    def test_diff_mode_delta_is_absolute(self):
        from pipeline_newgen_rev1.runtime.final_table._delta_vs_ref import (
            _attach_delta_vs_ref_metrics,
        )
        df = _make_df(fuels=("D85B15", "E75H25"), loads=(25.0,))
        out = _attach_delta_vs_ref_metrics(df)
        e75 = out[out["Fuel_Label"] == "E75H25"].iloc[0]
        ref_nth = out[out["Fuel_Label"] == "D85B15"]["n_th_pct"].iloc[0]
        expected = e75["n_th_pct"] - ref_nth
        self.assertAlmostEqual(e75["Delta_pp_n_th_pct_vs_D85B15"], expected, places=6)

    def test_ratio_mode_delta_is_percentage(self):
        from pipeline_newgen_rev1.runtime.final_table._delta_vs_ref import (
            _attach_delta_vs_ref_metrics,
        )
        df = _make_df(fuels=("D85B15", "E75H25"), loads=(25.0,))
        out = _attach_delta_vs_ref_metrics(df)
        e75 = out[out["Fuel_Label"] == "E75H25"].iloc[0]
        ref_bsfc = out[out["Fuel_Label"] == "D85B15"]["BSFC_g_kWh"].iloc[0]
        expected = 100.0 * (e75["BSFC_g_kWh"] / ref_bsfc - 1.0)
        self.assertAlmostEqual(e75["Delta_pct_BSFC_g_kWh_vs_D85B15"], expected, places=4)

    def test_ref_fuel_gets_zero_delta(self):
        from pipeline_newgen_rev1.runtime.final_table._delta_vs_ref import (
            _attach_delta_vs_ref_metrics,
        )
        df = _make_df()
        out = _attach_delta_vs_ref_metrics(df)
        ref_rows = out[out["Fuel_Label"] == "D85B15"]
        for _, row in ref_rows.iterrows():
            self.assertAlmostEqual(row["Delta_pp_n_th_pct_vs_D85B15"], 0.0, places=8)

    def test_missing_ref_fuel_skips_gracefully(self):
        from pipeline_newgen_rev1.runtime.final_table._delta_vs_ref import (
            _attach_delta_vs_ref_metrics,
        )
        df = _make_df(fuels=("E75H25",), loads=(25.0,))
        out = _attach_delta_vs_ref_metrics(df)
        self.assertIn("Delta_pp_n_th_pct_vs_D85B15", out.columns)
        self.assertTrue(out["Delta_pp_n_th_pct_vs_D85B15"].isna().all())

    def test_uncertainty_propagation_diff(self):
        from pipeline_newgen_rev1.runtime.final_table._delta_vs_ref import (
            _attach_delta_vs_ref_metrics,
        )
        df = _make_df(fuels=("D85B15", "E75H25"), loads=(25.0,))
        out = _attach_delta_vs_ref_metrics(df)
        e75 = out[out["Fuel_Label"] == "E75H25"].iloc[0]
        uc_delta = e75["uc_Delta_pp_n_th_pct_vs_D85B15"]
        self.assertTrue(np.isfinite(uc_delta))
        self.assertGreater(uc_delta, 0.0)
        self.assertAlmostEqual(uc_delta, 0.51, places=1)
        self.assertAlmostEqual(e75["U_Delta_pp_n_th_pct_vs_D85B15"], 2.0 * uc_delta, places=4)

    def test_uncertainty_propagation_ratio(self):
        from pipeline_newgen_rev1.runtime.final_table._delta_vs_ref import (
            _attach_delta_vs_ref_metrics,
        )
        df = _make_df(fuels=("D85B15", "E75H25"), loads=(25.0,))
        out = _attach_delta_vs_ref_metrics(df)
        e75 = out[out["Fuel_Label"] == "E75H25"].iloc[0]
        self.assertTrue(np.isfinite(e75["uc_Delta_pct_BSFC_g_kWh_vs_D85B15"]))
        self.assertGreater(e75["U_Delta_pct_BSFC_g_kWh_vs_D85B15"], 0.0)

    def test_preserves_row_count(self):
        from pipeline_newgen_rev1.runtime.final_table._delta_vs_ref import (
            _attach_delta_vs_ref_metrics,
        )
        df = _make_df()
        out = _attach_delta_vs_ref_metrics(df)
        self.assertEqual(len(out), len(df))


if __name__ == "__main__":
    unittest.main()
