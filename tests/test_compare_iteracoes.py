"""Tests for the native compare_iteracoes subpackage."""
from __future__ import annotations

import math
import unittest

import numpy as np
import pandas as pd

from _path import ROOT  # noqa: F401

from pipeline_newgen_rev1.runtime.compare_iteracoes.specs import (
    COMPARE_ITER_METRIC_SPECS,
    COMPARE_ITER_METRIC_SPECS_BY_ID,
    COMPARE_ITER_SERIES_META,
    K_COVERAGE,
    compare_iter_pair_context,
    metric_spec_for_id,
)
from pipeline_newgen_rev1.runtime.compare_iteracoes.prepare import (
    campaign_from_basename,
    find_consumo_col,
    metric_uncertainty_cols,
    prepare_compare_points,
    prepare_consumo_points,
    sentido_from_row,
)
from pipeline_newgen_rev1.runtime.compare_iteracoes.aggregate import (
    aggregate_by_load_point,
    mean_subida_descida,
)
from pipeline_newgen_rev1.runtime.compare_iteracoes.delta import build_delta_table
from pipeline_newgen_rev1.runtime.compare_iteracoes.series import build_series_frames
from pipeline_newgen_rev1.runtime.compare_iteracoes.core import (
    CompareResult,
    compute_compare_iteracoes,
    resolve_requests,
)


# ---------------------------------------------------------------------------
# specs
# ---------------------------------------------------------------------------

class TestSpecs(unittest.TestCase):
    def test_k_coverage(self) -> None:
        self.assertEqual(K_COVERAGE, 2.0)

    def test_series_meta_has_6_entries(self) -> None:
        self.assertEqual(len(COMPARE_ITER_SERIES_META), 6)
        for key in ["baseline_media", "aditivado_descida"]:
            self.assertIn(key, COMPARE_ITER_SERIES_META)
            self.assertIn("label", COMPARE_ITER_SERIES_META[key])
            self.assertIn("slug", COMPARE_ITER_SERIES_META[key])

    def test_metric_specs_count(self) -> None:
        self.assertEqual(len(COMPARE_ITER_METRIC_SPECS), 11)

    def test_metric_specs_by_id_lookup(self) -> None:
        for mid in ["consumo", "co2", "n_th"]:
            self.assertIn(mid, COMPARE_ITER_METRIC_SPECS_BY_ID)

    def test_metric_spec_for_id(self) -> None:
        spec = metric_spec_for_id("co2")
        self.assertIsNotNone(spec)
        self.assertEqual(spec["metric_col"], "CO2_mean_of_windows")

    def test_pair_context(self) -> None:
        ctx = compare_iter_pair_context("baseline_media", "aditivado_media")
        self.assertEqual(ctx["pair_slug"], "baseline_media_vs_aditivado_media")
        self.assertIn("Negativo", ctx["note_text"])
        self.assertEqual(ctx["interpret_neg"], "aditivado_media_menor")


# ---------------------------------------------------------------------------
# prepare
# ---------------------------------------------------------------------------

class TestPrepare(unittest.TestCase):
    def test_campaign_from_basename(self) -> None:
        self.assertEqual(campaign_from_basename("baseline_1_subindo"), "baseline")
        self.assertEqual(campaign_from_basename("aditivado_1_descendo"), "aditivado")
        self.assertEqual(campaign_from_basename("BL_1_subindo"), "baseline")
        self.assertEqual(campaign_from_basename("ADTV_1_descendo"), "aditivado")
        self.assertEqual(campaign_from_basename("unknown"), "")

    def test_sentido_from_row(self) -> None:
        row_sub = pd.Series({"Sentido_Carga": "subindo", "BaseName": "test"})
        self.assertEqual(sentido_from_row(row_sub), "subida")
        row_des = pd.Series({"Sentido_Carga": "descendo", "BaseName": "test"})
        self.assertEqual(sentido_from_row(row_des), "descida")
        row_bn = pd.Series({"Sentido_Carga": "", "BaseName": "baseline_1_subindo_10kw"})
        self.assertEqual(sentido_from_row(row_bn), "subida")

    def test_find_consumo_col(self) -> None:
        df = pd.DataFrame({"Consumo_kg_h": [1.0], "Other": [2.0]})
        self.assertEqual(find_consumo_col(df), "Consumo_kg_h")
        df2 = pd.DataFrame({"consumo_special_mean_of_windows": [1.0]})
        self.assertEqual(find_consumo_col(df2), "consumo_special_mean_of_windows")

    def test_prepare_compare_points_basic(self) -> None:
        df = pd.DataFrame({
            "BaseName": ["baseline_1_subindo", "aditivado_1_descendo"],
            "Sentido_Carga": ["subindo", "descendo"],
            "Load_kW": [10.0, 20.0],
            "CO2_mean_of_windows": [5.0, 6.0],
            "U_CO2_mean_of_windows": [0.1, 0.2],
        })
        out = prepare_compare_points(df, metric_col="CO2_mean_of_windows", mappings={})
        self.assertEqual(len(out), 2)
        self.assertIn("_metric", out.columns)
        self.assertIn("_campaign_bl_adtv", out.columns)

    def test_prepare_compare_points_empty(self) -> None:
        out = prepare_compare_points(pd.DataFrame(), metric_col="X", mappings={})
        self.assertTrue(out.empty)

    def test_prepare_consumo_points(self) -> None:
        df = pd.DataFrame({
            "BaseName": ["baseline_1_subindo", "aditivado_1_descendo"],
            "Sentido_Carga": ["subindo", "descendo"],
            "Load_kW": [10.0, 20.0],
            "Consumo_kg_h": [1.5, 2.0],
            "DIES_pct": [100, 100],
        })
        out = prepare_consumo_points(df)
        self.assertEqual(len(out), 2)
        self.assertAlmostEqual(out.iloc[0]["_metric"], 1.5)

    def test_metric_uncertainty_cols(self) -> None:
        df = pd.DataFrame({"CO2_mean_of_windows": [1], "U_CO2_mean_of_windows": [0.1]})
        uA, uB, uc, U = metric_uncertainty_cols(df, "CO2_mean_of_windows", {})
        self.assertEqual(U, "U_CO2_mean_of_windows")
        self.assertEqual(uA, "uA_CO2_mean_of_windows")


# ---------------------------------------------------------------------------
# aggregate
# ---------------------------------------------------------------------------

def _make_prepared_df(n_per_group: int = 2) -> pd.DataFrame:
    rows = []
    for camp in ["baseline", "aditivado"]:
        for sent in ["subida", "descida"]:
            for i in range(n_per_group):
                rows.append({
                    "_campaign_bl_adtv": camp,
                    "_sentido_plot": sent,
                    "Load_kW": 10.0,
                    "_metric": 5.0 + i * 0.1,
                    "_uA": 0.1,
                    "_uB": 0.2,
                    "_uc": 0.2236,
                    "_U": 0.4472,
                })
    return pd.DataFrame(rows)


class TestAggregate(unittest.TestCase):
    def test_aggregate_by_load_point(self) -> None:
        df = _make_prepared_df(n_per_group=2)
        agg = aggregate_by_load_point(df, value_name="test_metric")
        self.assertEqual(len(agg), 4)  # 2 campaigns x 2 directions
        self.assertIn("test_metric", agg.columns)
        self.assertIn("uA_test_metric", agg.columns)
        self.assertIn("n_points", agg.columns)
        self.assertTrue((agg["n_points"] == 2).all())

    def test_aggregate_empty(self) -> None:
        agg = aggregate_by_load_point(pd.DataFrame(), value_name="x")
        self.assertTrue(agg.empty)

    def test_mean_subida_descida(self) -> None:
        df = _make_prepared_df(n_per_group=1)
        agg = aggregate_by_load_point(df, value_name="m")
        media = mean_subida_descida(agg, value_name="m")
        self.assertEqual(len(media), 2)  # baseline + aditivado

    def test_mean_subida_descida_uB_correlated(self) -> None:
        """uB must NOT shrink when averaging subida/descida (GUM §F.1.2.4)."""
        rows = [
            {"_campaign_bl_adtv": "baseline", "_sentido_plot": "subida", "Load_kW": 10.0,
             "m": 5.0, "uA_m": 0.1, "uB_m": 0.2, "uc_m": 0.2236, "U_m": 0.4472, "n_points": 1},
            {"_campaign_bl_adtv": "baseline", "_sentido_plot": "descida", "Load_kW": 10.0,
             "m": 6.0, "uA_m": 0.1, "uB_m": 0.2, "uc_m": 0.2236, "U_m": 0.4472, "n_points": 1},
        ]
        agg = pd.DataFrame(rows)
        media = mean_subida_descida(agg, value_name="m")
        self.assertEqual(len(media), 1)
        row = media.iloc[0]
        self.assertAlmostEqual(row["m"], 5.5)
        # uB: arithmetic mean (correlated) = (0.2 + 0.2) / 2 = 0.2
        self.assertAlmostEqual(row["uB_m"], 0.2)
        # uA: RSS / 2 = sqrt(0.01 + 0.01) / 2 = sqrt(0.02) / 2 ≈ 0.0707
        self.assertAlmostEqual(row["uA_m"], math.sqrt(0.02) / 2, places=4)

    def test_mean_subida_descida_uc_fallback(self) -> None:
        """When uA/uB are NaN (derived metric), uc treated as 100% systematic."""
        rows = [
            {"_campaign_bl_adtv": "baseline", "_sentido_plot": "subida", "Load_kW": 10.0,
             "m": 5.0, "uA_m": float("nan"), "uB_m": float("nan"), "uc_m": 0.3, "U_m": 0.6, "n_points": 1},
            {"_campaign_bl_adtv": "baseline", "_sentido_plot": "descida", "Load_kW": 10.0,
             "m": 6.0, "uA_m": float("nan"), "uB_m": float("nan"), "uc_m": 0.3, "U_m": 0.6, "n_points": 1},
        ]
        agg = pd.DataFrame(rows)
        media = mean_subida_descida(agg, value_name="m")
        row = media.iloc[0]
        # uc fallback: (0.3 + 0.3) / 2 = 0.3 (treated as correlated)
        self.assertAlmostEqual(row["uc_m"], 0.3)


# ---------------------------------------------------------------------------
# delta
# ---------------------------------------------------------------------------

class TestDelta(unittest.TestCase):
    def test_build_delta_table(self) -> None:
        left = pd.DataFrame({
            "Load_kW": [10.0, 20.0],
            "m": [5.0, 10.0],
            "uA_m": [0.1, 0.2],
            "uB_m": [0.2, 0.3],
            "uc_m": [0.224, 0.361],
            "U_m": [0.447, 0.721],
            "n_points": [1, 1],
        })
        right = pd.DataFrame({
            "Load_kW": [10.0, 20.0],
            "m": [5.5, 10.5],
            "uA_m": [0.1, 0.2],
            "uB_m": [0.2, 0.3],
            "uc_m": [0.224, 0.361],
            "U_m": [0.447, 0.721],
            "n_points": [1, 1],
        })
        delta = build_delta_table(
            left, right, value_name="m",
            label_left="BL", label_right="ADTV",
            interpret_neg="adtv_menor", interpret_pos="adtv_maior",
        )
        self.assertEqual(len(delta), 2)
        self.assertIn("delta_pct", delta.columns)
        self.assertIn("U_delta_pct", delta.columns)
        self.assertIn("significancia_95pct", delta.columns)
        # delta_pct at Load_kW=10: (5.5/5.0 - 1)*100 = 10%
        row10 = delta[delta["Load_kW"] == 10.0].iloc[0]
        self.assertAlmostEqual(row10["delta_pct"], 10.0, places=2)

    def test_delta_uc_propagation_derived_metric(self) -> None:
        """For derived metrics (only uc, no uA/uB), uc_delta must still be populated."""
        left = pd.DataFrame({
            "Load_kW": [10.0], "m": [30.0],
            "uA_m": [float("nan")], "uB_m": [float("nan")],
            "uc_m": [0.5], "U_m": [1.0], "n_points": [1],
        })
        right = pd.DataFrame({
            "Load_kW": [10.0], "m": [31.0],
            "uA_m": [float("nan")], "uB_m": [float("nan")],
            "uc_m": [0.5], "U_m": [1.0], "n_points": [1],
        })
        delta = build_delta_table(
            left, right, value_name="m",
            label_left="BL", label_right="ADTV",
            interpret_neg="neg", interpret_pos="pos",
        )
        self.assertEqual(len(delta), 1)
        self.assertTrue(np.isfinite(delta.iloc[0]["uc_delta_pct"]))
        self.assertTrue(np.isfinite(delta.iloc[0]["U_delta_pct"]))

    def test_delta_empty_inputs(self) -> None:
        delta = build_delta_table(
            pd.DataFrame(), pd.DataFrame(), value_name="m",
            label_left="L", label_right="R",
            interpret_neg="neg", interpret_pos="pos",
        )
        self.assertTrue(delta.empty)


# ---------------------------------------------------------------------------
# series
# ---------------------------------------------------------------------------

class TestSeries(unittest.TestCase):
    def test_build_series_frames_keys(self) -> None:
        df = _make_prepared_df(n_per_group=1)
        agg = aggregate_by_load_point(df, value_name="m")
        frames = build_series_frames(agg, value_name="m")
        expected = {"baseline_subida", "baseline_descida", "baseline_media",
                    "aditivado_subida", "aditivado_descida", "aditivado_media"}
        self.assertEqual(set(frames.keys()), expected)
        for key, frame in frames.items():
            self.assertIsInstance(frame, pd.DataFrame)


# ---------------------------------------------------------------------------
# core (request resolution + orchestrator)
# ---------------------------------------------------------------------------

class TestResolveRequests(unittest.TestCase):
    def test_fallback_when_no_config(self) -> None:
        requests, source = resolve_requests(None)
        self.assertEqual(source, "fallback_pairs")
        self.assertGreater(len(requests), 0)
        metric_ids = {r["metric_id"] for r in requests}
        self.assertIn("consumo", metric_ids)
        self.assertIn("co2", metric_ids)

    def test_enabled_rows_from_config(self) -> None:
        compare_df = pd.DataFrame({
            "enabled": ["1", "0"],
            "left_series": ["baseline_media", "baseline_subida"],
            "right_series": ["aditivado_media", "aditivado_subida"],
            "metric_id": ["co2", "nox"],
        })
        requests, source = resolve_requests(compare_df)
        self.assertEqual(source, "gui_compare_tab")
        self.assertEqual(len(requests), 1)  # only enabled row
        self.assertEqual(requests[0]["metric_id"], "co2")

    def test_invalid_series_skipped(self) -> None:
        compare_df = pd.DataFrame({
            "enabled": ["1"],
            "left_series": ["unknown_series"],
            "right_series": ["aditivado_media"],
            "metric_id": ["co2"],
        })
        requests, source = resolve_requests(compare_df)
        self.assertEqual(len(requests), 0)

    def test_same_series_skipped(self) -> None:
        compare_df = pd.DataFrame({
            "enabled": ["1"],
            "left_series": ["baseline_media"],
            "right_series": ["baseline_media"],
            "metric_id": ["co2"],
        })
        requests, source = resolve_requests(compare_df)
        self.assertEqual(len(requests), 0)


class TestComputeCompareIteracoes(unittest.TestCase):
    def _make_final_table(self) -> pd.DataFrame:
        rows = []
        for camp, prefix in [("baseline", "baseline_1"), ("aditivado", "aditivado_1")]:
            for sent, sent_label in [("subindo", "subindo"), ("descendo", "descendo")]:
                for load in [10.0, 20.0, 30.0]:
                    rows.append({
                        "BaseName": f"{prefix}_{sent}_{int(load)}kw",
                        "Sentido_Carga": sent_label,
                        "Load_kW": load,
                        "CO2_mean_of_windows": 5.0 + load * 0.1 + (0.2 if camp == "aditivado" else 0.0),
                        "uA_CO2_mean_of_windows": 0.05,
                        "uB_CO2_mean_of_windows": 0.1,
                        "uc_CO2_mean_of_windows": 0.112,
                        "U_CO2_mean_of_windows": 0.224,
                        "Consumo_kg_h": 2.0 + load * 0.05,
                        "uA_Consumo_kg_h": 0.02,
                        "uB_Consumo_kg_h": 0.03,
                        "uc_Consumo_kg_h": 0.036,
                        "U_Consumo_kg_h": 0.072,
                        "DIES_pct": 100,
                    })
        return pd.DataFrame(rows)

    def test_end_to_end_with_fallback(self) -> None:
        ft = self._make_final_table()
        result = compute_compare_iteracoes(ft, None, {})
        self.assertIsInstance(result, CompareResult)
        self.assertFalse(result.delta_table.empty)
        self.assertIn("co2", result.series_by_metric)
        self.assertIn("consumo", result.series_by_metric)
        self.assertIn("delta_pct", result.delta_table.columns)
        self.assertIn("significancia_95pct", result.delta_table.columns)
        self.assertIn("Metrica", result.delta_table.columns)

    def test_end_to_end_with_config(self) -> None:
        ft = self._make_final_table()
        compare_df = pd.DataFrame({
            "enabled": ["1"],
            "left_series": ["baseline_media"],
            "right_series": ["aditivado_media"],
            "metric_id": ["co2"],
        })
        result = compute_compare_iteracoes(ft, compare_df, {})
        self.assertFalse(result.delta_table.empty)
        metrics = result.delta_table["Metrica"].unique()
        self.assertEqual(len(metrics), 1)

    def test_empty_final_table(self) -> None:
        result = compute_compare_iteracoes(pd.DataFrame(), None, {})
        self.assertTrue(result.delta_table.empty)


# ---------------------------------------------------------------------------
# stage integration
# ---------------------------------------------------------------------------

class TestStageRegistry(unittest.TestCase):
    def test_compute_stage_in_registry(self) -> None:
        from pipeline_newgen_rev1.runtime.stages import STAGE_REGISTRY, PROCESSING_STAGE_ORDER
        self.assertIn("compute_compare_iteracoes", STAGE_REGISTRY)
        self.assertIn("compute_compare_iteracoes", PROCESSING_STAGE_ORDER)

    def test_plot_stage_in_registry(self) -> None:
        from pipeline_newgen_rev1.runtime.stages import STAGE_REGISTRY, PLOTTING_STAGE_ORDER
        self.assertIn("plot_compare_iteracoes", STAGE_REGISTRY)
        self.assertIn("plot_compare_iteracoes", PLOTTING_STAGE_ORDER)

    def test_plot_time_diagnostics_in_registry(self) -> None:
        from pipeline_newgen_rev1.runtime.stages import STAGE_REGISTRY, PLOTTING_STAGE_ORDER
        self.assertIn("plot_time_diagnostics", STAGE_REGISTRY)
        self.assertIn("plot_time_diagnostics", PLOTTING_STAGE_ORDER)

    def test_three_phase_order(self) -> None:
        from pipeline_newgen_rev1.runtime.stages import (
            CONFIG_STAGE_ORDER, PROCESSING_STAGE_ORDER, PLOTTING_STAGE_ORDER, STAGE_PIPELINE_ORDER,
        )
        self.assertEqual(
            STAGE_PIPELINE_ORDER,
            CONFIG_STAGE_ORDER + PROCESSING_STAGE_ORDER + PLOTTING_STAGE_ORDER,
        )

    def test_no_plot_stages_in_processing(self) -> None:
        from pipeline_newgen_rev1.runtime.stages import PROCESSING_STAGE_ORDER
        for key in PROCESSING_STAGE_ORDER:
            self.assertFalse(key.startswith("plot_"), f"{key} should not be in PROCESSING_STAGE_ORDER")
            self.assertNotIn("unitary_plots", key)

    def test_no_compute_stages_in_plotting(self) -> None:
        from pipeline_newgen_rev1.runtime.stages import PLOTTING_STAGE_ORDER
        for key in PLOTTING_STAGE_ORDER:
            self.assertFalse(key.startswith("compute_"), f"{key} should not be in PLOTTING_STAGE_ORDER")
            self.assertNotIn("export_excel", key)


if __name__ == "__main__":
    unittest.main()
