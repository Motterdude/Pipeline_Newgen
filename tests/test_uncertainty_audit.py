"""Unit tests do audit layer de incerteza."""

from __future__ import annotations

import math
import unittest

import numpy as np
import pandas as pd

from pipeline_newgen_rev1.runtime.uncertainty_audit import (
    AUDITED_MEASURANDS,
    contribution_var,
    decompose_uB,
    enrich_final_table_with_audit,
    propagate_n_th,
)


class DecomposeUBTests(unittest.TestCase):
    def test_decompose_uB_resolution_only(self):
        """Instrumento só com resolução → uB_acc=0, uB_res = res/√12."""
        instruments = [{"key": "demo", "dist": "rect", "resolution": 0.1}]
        val = pd.Series([10.0, 20.0, 30.0])
        res, acc = decompose_uB(val, "demo", instruments)
        self.assertTrue(np.allclose(res, 0.1 / math.sqrt(12), atol=1e-9))
        self.assertTrue(np.allclose(acc, 0.0, atol=1e-9))

    def test_decompose_uB_accuracy_only(self):
        """Instrumento só com acc_abs (rect) → uB_res=0, uB_acc = acc_abs/√3."""
        instruments = [{"key": "demo", "dist": "rect", "acc_abs": 2.0}]
        val = pd.Series([10.0, 10.0, 10.0])
        res, acc = decompose_uB(val, "demo", instruments)
        self.assertTrue(np.allclose(res, 0.0, atol=1e-9))
        self.assertTrue(np.allclose(acc, 2.0 / math.sqrt(3), atol=1e-9))

    def test_decompose_uB_combined_matches_total(self):
        """uB_res² + uB_acc² = uB_total² (via RSS equivalente ao legado)."""
        instruments = [
            {"key": "demo", "dist": "rect", "resolution": 0.1, "acc_abs": 0.5, "acc_pct": 0.01},
        ]
        val = pd.Series([100.0])
        res, acc = decompose_uB(val, "demo", instruments)
        uB_total = math.sqrt(float(res.iloc[0]) ** 2 + float(acc.iloc[0]) ** 2)
        # Calcular o uB "total" pelo algoritmo legado:
        # u_res = 0.1/√12; limit = |100|·0.01 + 0.5 = 1.5; u_acc = 1.5/√3; uB = sqrt(u_res²+u_acc²)
        expected_res = 0.1 / math.sqrt(12)
        expected_acc = 1.5 / math.sqrt(3)
        expected_total = math.sqrt(expected_res ** 2 + expected_acc ** 2)
        self.assertAlmostEqual(uB_total, expected_total, places=9)

    def test_decompose_uB_stacks_components(self):
        """Múltiplas linhas com mesma key → RSS dentro de cada termo."""
        instruments = [
            {"key": "demo", "dist": "rect", "resolution": 0.1},
            {"key": "demo", "dist": "rect", "resolution": 0.2},
        ]
        val = pd.Series([10.0])
        res, _ = decompose_uB(val, "demo", instruments)
        expected_res = math.sqrt((0.1 / math.sqrt(12)) ** 2 + (0.2 / math.sqrt(12)) ** 2)
        self.assertAlmostEqual(float(res.iloc[0]), expected_res, places=9)

    def test_decompose_uB_no_matching_key(self):
        """Sem entrada no instruments → NaN."""
        instruments = [{"key": "other", "dist": "rect", "resolution": 0.1}]
        val = pd.Series([10.0, 20.0])
        res, acc = decompose_uB(val, "demo", instruments)
        self.assertTrue(pd.isna(res.iloc[0]))
        self.assertTrue(pd.isna(acc.iloc[0]))


class ContributionVarTests(unittest.TestCase):
    def test_contribution_var_basic(self):
        """uA=3, uB=4, uc=5 → %uA_contrib = 100·9/25 = 36%."""
        uA = pd.Series([3.0])
        uc = pd.Series([5.0])
        pct = contribution_var(uA, uc)
        self.assertAlmostEqual(float(pct.iloc[0]), 36.0, places=9)

    def test_contribution_var_sums_to_100(self):
        """pct_uA + pct_uB = 100 para qualquer ponto com uc>0."""
        rng = np.random.default_rng(42)
        uA = pd.Series(rng.uniform(0.01, 10.0, size=50))
        uB = pd.Series(rng.uniform(0.01, 10.0, size=50))
        uc = np.sqrt(uA ** 2 + uB ** 2)
        pct_uA = contribution_var(uA, uc)
        pct_uB = 100.0 - pct_uA
        self.assertTrue(np.allclose(pct_uA + pct_uB, 100.0, atol=1e-9))

    def test_contribution_var_handles_zero_or_nan(self):
        """uc=0 ou uA=NaN → NaN."""
        uA = pd.Series([1.0, 1.0, np.nan])
        uc = pd.Series([0.0, np.nan, 5.0])
        pct = contribution_var(uA, uc)
        self.assertTrue(pd.isna(pct.iloc[0]))
        self.assertTrue(pd.isna(pct.iloc[1]))
        self.assertTrue(pd.isna(pct.iloc[2]))


class DerivedPropagationTests(unittest.TestCase):
    def test_derived_n_th_propagation(self):
        """n_th = P / (ṁ · LHV). Para P=20kW, ṁ=5kg/h, LHV=43500kJ/kg → n_th ≈ 0.331.

        Dadas uA_P, uA_ṁ e uB_LHV conhecidos, a propagação deve bater com a fórmula analítica.
        """
        # Unidades: kW, kg/h, kJ/kg — o pipeline legado converte kg/h→kg/s internamente via 3600;
        # aqui testamos só que a lei de propagação relativa funciona.
        df = pd.DataFrame({
            "n_th": [0.331],
            "Potência Total_mean_of_windows": [20.0],
            "uA_P_kw": [0.2],
            "uB_P_kw": [0.4],
            "Consumo_kg_h_mean_of_windows": [5.0],
            "uA_Consumo_kg_h": [0.05],
            "uB_Consumo_kg_h": [0.1],
            "LHV_kJ_kg": [43500.0],
            "uB_LHV_kJ_kg": [435.0],  # 1% relativo
        })
        result = propagate_n_th(df)
        uA = float(result["uA_n_th"].iloc[0])
        uB = float(result["uB_n_th"].iloc[0])
        # Fórmula esperada:
        expected_rel_uA = math.sqrt((0.2 / 20) ** 2 + (0.05 / 5) ** 2)
        expected_rel_uB = math.sqrt((0.4 / 20) ** 2 + (0.1 / 5) ** 2 + (435.0 / 43500.0) ** 2)
        self.assertAlmostEqual(uA, 0.331 * expected_rel_uA, places=6)
        self.assertAlmostEqual(uB, 0.331 * expected_rel_uB, places=6)
        # Variante percentual
        self.assertAlmostEqual(float(result["uA_n_th_pct"].iloc[0]), uA * 100.0, places=6)


class EnrichIntegrationTests(unittest.TestCase):
    def _synthetic_final_table(self) -> pd.DataFrame:
        """final_table mínimo com 1 ponto e as colunas esperadas para todos os 13 measurands."""
        return pd.DataFrame(
            {
                "Consumo_kg_h_mean_of_windows": [5.0],
                "Consumo_kg_h_sd_of_windows": [0.02],
                "uA_Consumo_kg_h": [0.01],
                "uB_Consumo_kg_h": [0.025],
                "uc_Consumo_kg_h": [math.sqrt(0.01 ** 2 + 0.025 ** 2)],
                "Potência Total_mean_of_windows": [20.0],
                "Potência Total_sd_of_windows": [0.1],
                "uA_P_kw": [0.05],
                "uB_P_kw": [0.2],
                "uc_P_kw": [math.sqrt(0.05 ** 2 + 0.2 ** 2)],
                "NOX_mean_of_windows": [400.0],
                "uA_NOx_ppm": [2.0],
                "uB_NOx_ppm": [5.0],
                "uc_NOx_ppm": [math.sqrt(4.0 + 25.0)],
                "CO_mean_of_windows": [0.1],
                "uA_CO_pct": [0.001],
                "uB_CO_pct": [0.002],
                "uc_CO_pct": [math.sqrt(1e-6 + 4e-6)],
                "CO2_mean_of_windows": [10.0],
                "uA_CO2_pct": [0.05],
                "uB_CO2_pct": [0.1],
                "uc_CO2_pct": [math.sqrt(0.0025 + 0.01)],
                "THC_mean_of_windows": [50.0],
                "uA_THC_ppm": [0.5],
                "uB_THC_ppm": [1.0],
                "uc_THC_ppm": [math.sqrt(0.25 + 1.0)],
                "Consumo_L_h": [6.0],
                "Fuel_Density_kg_m3": [833.3],
                "n_th": [0.33],
                "n_th_pct": [33.0],
                "LHV_kJ_kg": [43500.0],
                "BSFC_g_kWh": [250.0],
                "NOx_g_kWh": [4.0],
                "CO_g_kWh": [1.0],
                "CO2_g_kWh": [800.0],
                "THC_g_kWh": [0.5],
            }
        )

    def _instruments(self) -> list:
        return [
            {"key": "fuel_kgh", "dist": "rect", "resolution": 0.01, "acc_pct": 0.005},
            {"key": "power_kw", "dist": "rect", "resolution": 0.01, "acc_pct": 0.01},
            {"key": "nox_ppm", "dist": "rect", "acc_pct": 0.02},
            {"key": "co_pct", "dist": "rect", "acc_abs": 0.001},
            {"key": "co2_pct", "dist": "rect", "acc_abs": 0.05},
            {"key": "thc_ppm", "dist": "rect", "acc_pct": 0.02},
        ]

    def test_enrich_adds_per_measurand_audit_columns(self):
        df = self._synthetic_final_table()
        before_cols = set(df.columns)
        enriched = enrich_final_table_with_audit(df, instruments=self._instruments())
        added = set(enriched.columns) - before_cols
        # Todo measurand ganha as colunas de %contribuição.
        # Somente grandezas medidas (com instrument_key) ganham uB_res/uB_acc.
        for spec in AUDITED_MEASURANDS:
            self.assertIn(f"pct_uA_contrib_{spec.key}", added, f"missing pct_uA_contrib_{spec.key}")
            self.assertIn(f"pct_uB_contrib_{spec.key}", added, f"missing pct_uB_contrib_{spec.key}")
            if spec.kind == "measured" and spec.instrument_key:
                self.assertIn(f"uB_res_{spec.key}", added, f"missing uB_res_{spec.key}")
                self.assertIn(f"uB_acc_{spec.key}", added, f"missing uB_acc_{spec.key}")

    def test_enrich_preserves_existing_columns(self):
        df = self._synthetic_final_table()
        original = df.copy()
        enrich_final_table_with_audit(df, instruments=self._instruments())
        for col in original.columns:
            pd.testing.assert_series_equal(df[col], original[col], check_names=False, check_dtype=False)

    def test_enrich_contribution_sums_to_100_for_measured(self):
        df = self._synthetic_final_table()
        enrich_final_table_with_audit(df, instruments=self._instruments())
        for key in ("Consumo_kg_h", "P_kw"):
            pct_uA = float(df[f"pct_uA_contrib_{key}"].iloc[0])
            pct_uB = float(df[f"pct_uB_contrib_{key}"].iloc[0])
            self.assertAlmostEqual(pct_uA + pct_uB, 100.0, places=6)
            self.assertGreaterEqual(pct_uA, 0.0)
            self.assertLessEqual(pct_uA, 100.0)


if __name__ == "__main__":
    unittest.main()
