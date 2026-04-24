"""Tests for the native trechos/ponto subpackage.

Covers helpers, compute_trechos_stats, compute_ponto_stats, and stage integration.
"""
from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pandas as pd

SRC = Path(__file__).resolve().parent.parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from pipeline_newgen_rev1.runtime.trechos_ponto.helpers import (
    find_b_etanol_col,
    get_resolution_for_key,
    has_instrument_key,
    normalize_repeated_stat_tokens,
    res_to_std,
)
from pipeline_newgen_rev1.runtime.trechos_ponto.core import (
    compute_ponto_stats,
    compute_trechos_stats,
)
from pipeline_newgen_rev1.runtime.trechos_ponto.constants import (
    GROUP_COLS_PONTO,
    GROUP_COLS_TRECHOS,
    MIN_SAMPLES_PER_WINDOW,
)
from pipeline_newgen_rev1.runtime.stages.compute_trechos_ponto import (
    ComputeTrechosPontoStage,
)


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #

def _make_instruments(key: str = "balance_kg", resolution: float = 0.001):
    return [{"key": key, "resolution": resolution}]


def _make_lv_raw(n_samples: int = 30, n_windows: int = 2, b_start: float = 10.0, b_step: float = -0.001):
    rows = []
    for w in range(n_windows):
        b = b_start
        for i in range(n_samples):
            rows.append({
                "BaseName": "file1",
                "Load_kW": 50.0,
                "DIES_pct": 0.0,
                "BIOD_pct": 0.0,
                "EtOH_pct": 100.0,
                "H2O_pct": 0.0,
                "WindowID": w,
                "Index": i,
                "B_Etanol": b,
                "RPM": 2000.0 + w * 100,
                "Torque_Nm": 150.0,
            })
            b += b_step
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

class TestFindBEtanolCol(unittest.TestCase):
    def test_found(self):
        df = pd.DataFrame({"B_ETANOL": [1], "RPM": [2]})
        self.assertEqual(find_b_etanol_col(df), "B_ETANOL")

    def test_found_variant(self):
        df = pd.DataFrame({"B_Etanol (kg)": [1]})
        self.assertEqual(find_b_etanol_col(df), "B_Etanol (kg)")

    def test_missing_raises(self):
        df = pd.DataFrame({"RPM": [1]})
        with self.assertRaises(KeyError):
            find_b_etanol_col(df)


class TestResToStd(unittest.TestCase):
    def test_positive(self):
        self.assertAlmostEqual(res_to_std(1.0), 1.0 / math.sqrt(12), places=10)

    def test_zero(self):
        self.assertEqual(res_to_std(0.0), 0.0)

    def test_negative(self):
        self.assertEqual(res_to_std(-1.0), 0.0)


class TestNormalizeRepeatedStatTokens(unittest.TestCase):
    def test_mean_mean_of_windows(self):
        self.assertEqual(
            normalize_repeated_stat_tokens("RPM_mean_mean_of_windows"),
            "RPM_mean_of_windows",
        )

    def test_mean_sd_of_windows(self):
        self.assertEqual(
            normalize_repeated_stat_tokens("RPM_mean_sd_of_windows"),
            "RPM_sd_of_windows",
        )

    def test_no_change(self):
        self.assertEqual(
            normalize_repeated_stat_tokens("RPM_mean"),
            "RPM_mean",
        )

    def test_double_underscore(self):
        self.assertEqual(
            normalize_repeated_stat_tokens("RPM__mean"),
            "RPM_mean",
        )


class TestHasInstrumentKey(unittest.TestCase):
    def test_found(self):
        instruments = _make_instruments("balance_kg", 0.001)
        self.assertTrue(has_instrument_key(instruments, "balance_kg"))

    def test_not_found(self):
        instruments = _make_instruments("other_key", 0.001)
        self.assertFalse(has_instrument_key(instruments, "balance_kg"))

    def test_empty(self):
        self.assertFalse(has_instrument_key([], "balance_kg"))


class TestGetResolutionForKey(unittest.TestCase):
    def test_valid(self):
        instruments = _make_instruments("balance_kg", 0.001)
        self.assertAlmostEqual(get_resolution_for_key(instruments, "balance_kg"), 0.001)

    def test_missing_key(self):
        self.assertIsNone(get_resolution_for_key([], "balance_kg"))

    def test_missing_resolution(self):
        instruments = [{"key": "balance_kg"}]
        self.assertIsNone(get_resolution_for_key(instruments, "balance_kg"))

    def test_multiple_rows_takes_max(self):
        instruments = [
            {"key": "balance_kg", "resolution": 0.001},
            {"key": "balance_kg", "resolution": 0.005},
        ]
        self.assertAlmostEqual(get_resolution_for_key(instruments, "balance_kg"), 0.005)


# --------------------------------------------------------------------------- #
# compute_trechos_stats
# --------------------------------------------------------------------------- #

class TestComputeTrechosStats(unittest.TestCase):
    def test_basic_grouping(self):
        lv = _make_lv_raw(n_samples=30, n_windows=2)
        instruments = _make_instruments("balance_kg", 0.001)
        result = compute_trechos_stats(lv, instruments=instruments)
        self.assertEqual(len(result), 2)
        self.assertIn("RPM_mean", result.columns)
        self.assertIn("Consumo_kg_h", result.columns)
        self.assertIn("N_samples", result.columns)
        self.assertTrue((result["N_samples"] == 30).all())

    def test_filters_small_windows(self):
        lv = _make_lv_raw(n_samples=29, n_windows=1)
        instruments = _make_instruments("balance_kg", 0.001)
        result = compute_trechos_stats(lv, instruments=instruments)
        self.assertEqual(len(result), 0)

    def test_consumption_formula(self):
        lv = _make_lv_raw(n_samples=31, n_windows=1, b_start=10.0, b_step=-0.01)
        instruments = []
        result = compute_trechos_stats(lv, instruments=instruments)
        self.assertEqual(len(result), 1)
        row = result.iloc[0]
        delta_b = 10.0 - (10.0 + 30 * (-0.01))  # first - last
        delta_t = (31 - 1) * 1.0
        expected = (delta_b / delta_t) * 3600.0
        self.assertAlmostEqual(row["Consumo_kg_h"], expected, places=6)

    def test_uB_with_valid_resolution(self):
        lv = _make_lv_raw(n_samples=31, n_windows=1)
        res = 0.001
        instruments = _make_instruments("balance_kg", res)
        result = compute_trechos_stats(lv, instruments=instruments)
        self.assertEqual(len(result), 1)
        row = result.iloc[0]
        u_read = res / math.sqrt(12)
        u_delta = math.sqrt(2) * u_read
        delta_t = (31 - 1) * 1.0
        expected = (u_delta / delta_t) * 3600.0
        self.assertAlmostEqual(row["uB_Consumo_kg_h"], expected, places=10)

    def test_uB_without_instrument(self):
        lv = _make_lv_raw(n_samples=30, n_windows=1)
        result = compute_trechos_stats(lv, instruments=[])
        self.assertEqual(len(result), 1)
        self.assertTrue(pd.isna(result.iloc[0]["uB_Consumo_kg_h"]))

    def test_empty_input(self):
        lv = pd.DataFrame()
        result = compute_trechos_stats(lv, instruments=[])
        self.assertEqual(len(result), 0)
        for c in GROUP_COLS_TRECHOS + ["N_samples", "Consumo_kg_h", "uB_Consumo_kg_h"]:
            self.assertIn(c, result.columns)


# --------------------------------------------------------------------------- #
# compute_ponto_stats
# --------------------------------------------------------------------------- #

class TestComputePontoStats(unittest.TestCase):
    def test_aggregation(self):
        lv = _make_lv_raw(n_samples=30, n_windows=2)
        instruments = _make_instruments("balance_kg", 0.001)
        trechos = compute_trechos_stats(lv, instruments=instruments)
        ponto = compute_ponto_stats(trechos)
        self.assertEqual(len(ponto), 1)
        self.assertIn("N_trechos_validos", ponto.columns)
        self.assertEqual(ponto.iloc[0]["N_trechos_validos"], 2)

    def test_sd_ddof1(self):
        lv = _make_lv_raw(n_samples=30, n_windows=3)
        instruments = []
        trechos = compute_trechos_stats(lv, instruments=instruments)
        ponto = compute_ponto_stats(trechos)
        rpm_mean_col = [c for c in trechos.columns if c == "RPM_mean"]
        self.assertTrue(len(rpm_mean_col) > 0)
        sd_col = "RPM_sd_of_windows"
        if sd_col in ponto.columns:
            values = trechos["RPM_mean"].values
            expected_sd = float(pd.Series(values).std(ddof=1))
            self.assertAlmostEqual(ponto.iloc[0][sd_col], expected_sd, places=6)

    def test_uB_propagation(self):
        lv = _make_lv_raw(n_samples=31, n_windows=2)
        instruments = _make_instruments("balance_kg", 0.001)
        trechos = compute_trechos_stats(lv, instruments=instruments)
        ponto = compute_ponto_stats(trechos)
        uB_col = "uB_Consumo_kg_h_mean_of_windows"
        self.assertIn(uB_col, ponto.columns)
        uB_values = trechos["uB_Consumo_kg_h"].values
        expected = math.sqrt(sum(v**2 for v in uB_values)) / len(uB_values)
        self.assertAlmostEqual(float(ponto.iloc[0][uB_col]), expected, places=10)

    def test_empty_input(self):
        ponto = compute_ponto_stats(pd.DataFrame())
        self.assertEqual(len(ponto), 0)

    def test_suffix_normalization(self):
        lv = _make_lv_raw(n_samples=30, n_windows=2)
        instruments = []
        trechos = compute_trechos_stats(lv, instruments=instruments)
        ponto = compute_ponto_stats(trechos)
        for col in ponto.columns:
            self.assertNotIn("_mean_mean_of_windows", col)
            self.assertNotIn("_mean_sd_of_windows", col)


# --------------------------------------------------------------------------- #
# Stage integration
# --------------------------------------------------------------------------- #

class TestComputeTrechosPontoStage(unittest.TestCase):
    def test_feature_key(self):
        stage = ComputeTrechosPontoStage()
        self.assertEqual(stage.feature_key, "compute_trechos_ponto")

    def test_skips_no_frames(self):
        ctx = MagicMock()
        ctx.labview_frames = []
        ctx.trechos = None
        ctx.ponto = None
        stage = ComputeTrechosPontoStage()
        stage.run(ctx)
        self.assertIsNone(ctx.trechos)
        self.assertIsNone(ctx.ponto)

    def test_populates_ctx(self):
        ctx = MagicMock()
        ctx.labview_frames = [_make_lv_raw(n_samples=30, n_windows=2)]
        ctx.bundle = MagicMock()
        ctx.bundle.instruments = _make_instruments("balance_kg", 0.001)
        ctx.trechos = None
        ctx.ponto = None

        stage = ComputeTrechosPontoStage()
        stage.run(ctx)

        self.assertIsInstance(ctx.trechos, pd.DataFrame)
        self.assertIsInstance(ctx.ponto, pd.DataFrame)
        self.assertGreater(len(ctx.trechos), 0)
        self.assertGreater(len(ctx.ponto), 0)


if __name__ == "__main__":
    unittest.main()
