"""Unit tests for the native final_table subpackage.

Covers: helpers, psychrometrics, source_identity, merge, fuel_defaults,
reporting, airflow, emissions, volumetric efficiency, diesel_cost_delta,
machine_scenarios, and the build_final_table orchestrator.
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

from pipeline_newgen_rev1.runtime.final_table.constants import (
    AFR_STOICH_BIODIESEL,
    AFR_STOICH_DIESEL,
    AFR_STOICH_ETHANOL,
    K_COVERAGE,
    MW_CO2_KG_KMOL,
    MW_CO_KG_KMOL,
    MW_N2_KG_KMOL,
    MW_NO_KG_KMOL,
    MW_NO2_KG_KMOL,
    MW_O2_KG_KMOL,
    R_AIR_DRY_J_KG_K,
    rect_to_std,
    res_to_std,
)
from pipeline_newgen_rev1.runtime.final_table._helpers import (
    _canon_name,
    _find_first_col_by_substrings,
    _is_blank_cell,
    _nan_series,
    _normalize_repeated_stat_tokens_in_name,
    _to_float,
    _to_str_or_empty,
    norm_key,
    resolve_col,
)
from pipeline_newgen_rev1.runtime.final_table._psychrometrics import (
    _cp_air_dry_kj_kgk,
    _cp_moist_air_kj_kgk,
    _humidity_ratio_w_from_rh,
    _psat_water_pa_magnus,
)
from pipeline_newgen_rev1.runtime.final_table._source_identity import (
    add_run_context_columns,
    add_source_identity_columns,
)
from pipeline_newgen_rev1.runtime.final_table._merge import (
    _find_kibox_col_by_tokens,
    _left_merge_on_fuel_keys,
)
from pipeline_newgen_rev1.runtime.final_table._fuel_defaults import (
    _fuel_blend_labels,
    _fuel_default_lookup_series,
    _lookup_lhv_for_blend,
)
from pipeline_newgen_rev1.runtime.final_table._reporting import (
    _apply_reporting_rounding,
    _round_half_up_to_resolution,
)
from pipeline_newgen_rev1.runtime.final_table._airflow import (
    _airflow_stoich_blend_from_composition,
    _series_is_static,
    add_airflow_channels_prefer_maf_inplace,
)
from pipeline_newgen_rev1.runtime.final_table._emissions import (
    specific_emissions_from_analyzer,
)
from pipeline_newgen_rev1.runtime.final_table._volumetric_efficiency import (
    add_volumetric_efficiency_from_airflow_method_inplace,
)
from pipeline_newgen_rev1.runtime.final_table._diesel_cost_delta import (
    _aggregate_metric_with_uncertainty,
    _attach_diesel_cost_delta_metrics,
)
from pipeline_newgen_rev1.runtime.final_table._machine_scenarios import (
    _attach_e94h6_machine_scenario_metrics,
    _resolve_machine_scenario_inputs,
)
from pipeline_newgen_rev1.runtime.stages.build_final_table import (
    BuildFinalTableStage,
)
from pipeline_newgen_rev1.runtime.stages.export_excel import (
    ExportExcelStage,
)


# =========================================================================== #
#  _helpers
# =========================================================================== #

class TestNormKey(unittest.TestCase):
    def test_strips_and_lowercases(self):
        self.assertEqual(norm_key("  HELLO  "), "hello")

    def test_removes_bom(self):
        self.assertEqual(norm_key("﻿key"), "key")


class TestCanonName(unittest.TestCase):
    def test_removes_accents(self):
        self.assertEqual(_canon_name("Potência"), "potencia")

    def test_normalizes_whitespace(self):
        self.assertEqual(_canon_name("a  b   c"), "a b c")


class TestNormalizeRepeatedStatTokens(unittest.TestCase):
    def test_mean_mean_of_windows(self):
        self.assertEqual(
            _normalize_repeated_stat_tokens_in_name("RPM_mean_mean_of_windows"),
            "RPM_mean_of_windows",
        )

    def test_double_underscore(self):
        self.assertEqual(
            _normalize_repeated_stat_tokens_in_name("RPM__mean"),
            "RPM_mean",
        )

    def test_no_change(self):
        self.assertEqual(
            _normalize_repeated_stat_tokens_in_name("RPM_mean"),
            "RPM_mean",
        )


class TestIsBlankCell(unittest.TestCase):
    def test_none(self):
        self.assertTrue(_is_blank_cell(None))

    def test_nan(self):
        self.assertTrue(_is_blank_cell(float("nan")))

    def test_empty_string(self):
        self.assertTrue(_is_blank_cell(""))

    def test_nan_string(self):
        self.assertTrue(_is_blank_cell("nan"))

    def test_valid_value(self):
        self.assertFalse(_is_blank_cell("hello"))
        self.assertFalse(_is_blank_cell(42))


class TestToFloat(unittest.TestCase):
    def test_numeric(self):
        self.assertEqual(_to_float(3.14), 3.14)

    def test_string_with_comma(self):
        self.assertAlmostEqual(_to_float("3,14"), 3.14)

    def test_none(self):
        self.assertEqual(_to_float(None, default=-1.0), -1.0)

    def test_invalid_string(self):
        self.assertEqual(_to_float("abc", default=0.0), 0.0)

    def test_empty_string(self):
        self.assertEqual(_to_float("", default=99.0), 99.0)


class TestResolveCol(unittest.TestCase):
    def test_exact_match(self):
        df = pd.DataFrame({"RPM_mean_of_windows": [1]})
        self.assertEqual(resolve_col(df, "RPM_mean_of_windows"), "RPM_mean_of_windows")

    def test_case_insensitive(self):
        df = pd.DataFrame({"rpm_mean_of_windows": [1]})
        self.assertEqual(resolve_col(df, "RPM_Mean_Of_Windows"), "rpm_mean_of_windows")

    def test_accent_insensitive(self):
        df = pd.DataFrame({"Potência Total_mean_of_windows": [1]})
        self.assertEqual(resolve_col(df, "Potencia Total_mean_of_windows"), "Potência Total_mean_of_windows")

    def test_stat_token_normalization(self):
        df = pd.DataFrame({"RPM_mean_of_windows": [1]})
        self.assertEqual(resolve_col(df, "RPM_mean_mean_of_windows"), "RPM_mean_of_windows")

    def test_missing_raises(self):
        df = pd.DataFrame({"RPM": [1]})
        with self.assertRaises(KeyError):
            resolve_col(df, "totally_nonexistent_column_xyz")

    def test_empty_raises(self):
        df = pd.DataFrame({"RPM": [1]})
        with self.assertRaises(KeyError):
            resolve_col(df, "")


class TestFindFirstColBySubstrings(unittest.TestCase):
    def test_found(self):
        df = pd.DataFrame({"KIBOX_IMEP_Mean": [1], "RPM": [2]})
        self.assertEqual(_find_first_col_by_substrings(df, ["kibox", "imep"]), "KIBOX_IMEP_Mean")

    def test_not_found(self):
        df = pd.DataFrame({"RPM": [1]})
        self.assertIsNone(_find_first_col_by_substrings(df, ["kibox"]))


class TestNanSeries(unittest.TestCase):
    def test_length(self):
        idx = pd.RangeIndex(5)
        result = _nan_series(idx)
        self.assertEqual(len(result), 5)
        self.assertTrue(result.isna().all())


# =========================================================================== #
#  constants
# =========================================================================== #

class TestConstantFunctions(unittest.TestCase):
    def test_res_to_std(self):
        self.assertAlmostEqual(res_to_std(1.0), 1.0 / math.sqrt(12))
        self.assertEqual(res_to_std(0.0), 0.0)
        self.assertEqual(res_to_std(-1.0), 0.0)

    def test_rect_to_std(self):
        result = rect_to_std(pd.Series([3.0]))
        self.assertAlmostEqual(float(result.iloc[0]), 3.0 / math.sqrt(3))


# =========================================================================== #
#  _psychrometrics
# =========================================================================== #

class TestPsychrometrics(unittest.TestCase):
    def test_psat_at_100C(self):
        result = _psat_water_pa_magnus(pd.Series([100.0]))
        self.assertAlmostEqual(float(result.iloc[0]), 101325.0, delta=3000)

    def test_psat_at_0C(self):
        result = _psat_water_pa_magnus(pd.Series([0.0]))
        self.assertAlmostEqual(float(result.iloc[0]), 611.2, delta=5.0)

    def test_humidity_ratio_dry_air(self):
        result = _humidity_ratio_w_from_rh(
            pd.Series([25.0]), pd.Series([0.0]), pd.Series([101.3]),
        )
        self.assertAlmostEqual(float(result.iloc[0]), 0.0, places=6)

    def test_humidity_ratio_saturated_air(self):
        result = _humidity_ratio_w_from_rh(
            pd.Series([25.0]), pd.Series([100.0]), pd.Series([101.3]),
        )
        self.assertGreater(float(result.iloc[0]), 0.018)
        self.assertLess(float(result.iloc[0]), 0.025)

    def test_cp_dry_at_25C(self):
        result = _cp_air_dry_kj_kgk(pd.Series([25.0]))
        self.assertAlmostEqual(float(result.iloc[0]), 1.005, places=4)

    def test_cp_moist_higher_than_dry(self):
        cp_dry = _cp_air_dry_kj_kgk(pd.Series([25.0]))
        cp_moist = _cp_moist_air_kj_kgk(
            pd.Series([25.0]), pd.Series([80.0]), pd.Series([101.3]),
        )
        self.assertGreater(float(cp_moist.iloc[0]), float(cp_dry.iloc[0]))


# =========================================================================== #
#  _source_identity
# =========================================================================== #

class TestSourceIdentity(unittest.TestCase):
    def test_add_source_identity(self):
        df = pd.DataFrame({"BaseName": ["folder1__folder2__file.xlsx"]})
        result = add_source_identity_columns(df)
        self.assertEqual(result["SourceFolder"].iloc[0], "folder1 / folder2")
        self.assertEqual(result["SourceFile"].iloc[0], "file.xlsx")

    def test_single_part_basename(self):
        df = pd.DataFrame({"BaseName": ["file_only.xlsx"]})
        result = add_source_identity_columns(df)
        self.assertEqual(result["SourceFolder"].iloc[0], "")
        self.assertEqual(result["SourceFile"].iloc[0], "file_only.xlsx")

    def test_run_context_subindo(self):
        df = pd.DataFrame({"BaseName": ["subindo_aditivado_1__file.xlsx"]})
        result = add_run_context_columns(df)
        self.assertEqual(result["Sentido_Carga"].iloc[0], "subida")
        self.assertEqual(int(result["Iteracao"].iloc[0]), 1)

    def test_run_context_descendo(self):
        df = pd.DataFrame({"BaseName": ["descendo_baseline_2__file.xlsx"]})
        result = add_run_context_columns(df)
        self.assertEqual(result["Sentido_Carga"].iloc[0], "descida")
        self.assertEqual(int(result["Iteracao"].iloc[0]), 2)

    def test_empty_df(self):
        result = add_source_identity_columns(pd.DataFrame())
        self.assertEqual(len(result), 0)


# =========================================================================== #
#  _merge
# =========================================================================== #

class TestMerge(unittest.TestCase):
    def test_left_merge_on_fuel_keys(self):
        left = pd.DataFrame({
            "DIES_pct": [85.0, 0.0],
            "BIOD_pct": [15.0, 0.0],
            "EtOH_pct": [0.0, 94.0],
            "H2O_pct": [0.0, 6.0],
            "value": [1, 2],
        })
        right = pd.DataFrame({
            "DIES_pct": [85.0],
            "BIOD_pct": [15.0],
            "EtOH_pct": [0.0],
            "H2O_pct": [0.0],
            "extra_data": [42],
        })
        result = _left_merge_on_fuel_keys(left, right)
        self.assertEqual(len(result), 2)
        self.assertEqual(int(result.loc[0, "extra_data"]), 42)
        self.assertTrue(pd.isna(result.loc[1, "extra_data"]))

    def test_find_kibox_col(self):
        df = pd.DataFrame({"KIBOX_IMEP_Mean": [1], "KIBOX_COV_Std": [2], "RPM": [3]})
        self.assertEqual(_find_kibox_col_by_tokens(df, ["imep", "mean"]), "KIBOX_IMEP_Mean")
        self.assertIsNone(_find_kibox_col_by_tokens(df, ["pmax"]))

    def test_find_kibox_non_kibox_prefix_ignored(self):
        df = pd.DataFrame({"OTHER_IMEP_Mean": [1]})
        self.assertIsNone(_find_kibox_col_by_tokens(df, ["imep"]))


# =========================================================================== #
#  _fuel_defaults
# =========================================================================== #

class TestFuelDefaults(unittest.TestCase):
    def test_fuel_blend_labels_diesel(self):
        df = pd.DataFrame({"DIES_pct": [85.0], "BIOD_pct": [15.0], "EtOH_pct": [0.0], "H2O_pct": [0.0]})
        labels = _fuel_blend_labels(df)
        self.assertEqual(str(labels.iloc[0]), "D85B15")

    def test_fuel_blend_labels_ethanol(self):
        df = pd.DataFrame({"DIES_pct": [0.0], "BIOD_pct": [0.0], "EtOH_pct": [94.0], "H2O_pct": [6.0]})
        labels = _fuel_blend_labels(df)
        self.assertEqual(str(labels.iloc[0]), "E94H6")

    def test_fuel_default_lookup_density(self):
        df = pd.DataFrame({"DIES_pct": [85.0], "BIOD_pct": [15.0], "EtOH_pct": [0.0], "H2O_pct": [0.0]})
        defaults = {"fuel_density_kg_m3_d85b15": "833.0"}
        values, missing = _fuel_default_lookup_series(df, defaults, field="density_param")
        self.assertAlmostEqual(float(values.iloc[0]), 833.0)
        self.assertEqual(len(missing), 0)

    def test_fuel_default_lookup_missing(self):
        df = pd.DataFrame({"DIES_pct": [85.0], "BIOD_pct": [15.0], "EtOH_pct": [0.0], "H2O_pct": [0.0]})
        values, missing = _fuel_default_lookup_series(df, {}, field="density_param")
        self.assertTrue(np.isnan(float(values.iloc[0])))
        self.assertGreater(len(missing), 0)

    def test_lookup_lhv_exact_match(self):
        lhv_df = pd.DataFrame({"EtOH_pct": [94.0], "H2O_pct": [6.0], "LHV_kJ_kg": [25000.0]})
        result = _lookup_lhv_for_blend(lhv_df, etoh_pct=94.0, h2o_pct=6.0)
        self.assertAlmostEqual(result, 25000.0)

    def test_lookup_lhv_no_match(self):
        lhv_df = pd.DataFrame({"EtOH_pct": [94.0], "H2O_pct": [6.0], "LHV_kJ_kg": [25000.0]})
        result = _lookup_lhv_for_blend(lhv_df, etoh_pct=50.0, h2o_pct=50.0)
        self.assertTrue(math.isnan(result))

    def test_lookup_lhv_empty(self):
        result = _lookup_lhv_for_blend(pd.DataFrame(), etoh_pct=94.0, h2o_pct=6.0)
        self.assertTrue(math.isnan(result))


# =========================================================================== #
#  _reporting
# =========================================================================== #

class TestReporting(unittest.TestCase):
    def test_round_half_up_basic(self):
        result = _round_half_up_to_resolution(pd.Series([1.26, 1.34, 2.0]), 0.1)
        self.assertAlmostEqual(float(result.iloc[0]), 1.3)
        self.assertAlmostEqual(float(result.iloc[1]), 1.3)
        self.assertAlmostEqual(float(result.iloc[2]), 2.0)

    def test_round_half_up_negative(self):
        result = _round_half_up_to_resolution(pd.Series([-1.25, -1.35]), 0.1)
        self.assertAlmostEqual(float(result.iloc[0]), -1.3)
        self.assertAlmostEqual(float(result.iloc[1]), -1.4)

    def test_round_half_up_zero_resolution(self):
        values = pd.Series([1.234, 5.678])
        result = _round_half_up_to_resolution(values, 0.0)
        self.assertAlmostEqual(float(result.iloc[0]), 1.234)
        self.assertAlmostEqual(float(result.iloc[1]), 5.678)

    def test_apply_reporting_rounding(self):
        df = pd.DataFrame({"RPM_mean_of_windows": [1234.5678]})
        mappings = {"rpm": {"mean": "RPM_mean_of_windows"}}
        reporting_df = pd.DataFrame({"key": ["RPM"], "report_resolution": [1.0], "rule": ["round_half_up"]})
        result = _apply_reporting_rounding(df, mappings, reporting_df)
        self.assertIn("RPM_mean_of_windows_report", result.columns)
        self.assertAlmostEqual(float(result["RPM_mean_of_windows_report"].iloc[0]), 1235.0)

    def test_apply_reporting_empty_reporting(self):
        df = pd.DataFrame({"RPM": [1234.5]})
        result = _apply_reporting_rounding(df, {}, pd.DataFrame())
        self.assertEqual(list(result.columns), ["RPM"])


# =========================================================================== #
#  _airflow
# =========================================================================== #

class TestAirflow(unittest.TestCase):
    def test_stoich_blend_diesel(self):
        df = pd.DataFrame({"DIES_pct": [100.0], "BIOD_pct": [0.0], "EtOH_pct": [0.0]})
        result = _airflow_stoich_blend_from_composition(df)
        self.assertAlmostEqual(float(result.iloc[0]), AFR_STOICH_DIESEL)

    def test_stoich_blend_ethanol(self):
        df = pd.DataFrame({"DIES_pct": [0.0], "BIOD_pct": [0.0], "EtOH_pct": [100.0]})
        result = _airflow_stoich_blend_from_composition(df)
        self.assertAlmostEqual(float(result.iloc[0]), AFR_STOICH_ETHANOL)

    def test_stoich_blend_mixed(self):
        df = pd.DataFrame({"DIES_pct": [85.0], "BIOD_pct": [15.0], "EtOH_pct": [0.0]})
        result = _airflow_stoich_blend_from_composition(df)
        expected = 0.85 * AFR_STOICH_DIESEL + 0.15 * AFR_STOICH_BIODIESEL
        self.assertAlmostEqual(float(result.iloc[0]), expected)

    def test_series_is_static(self):
        self.assertTrue(_series_is_static(pd.Series([5.0, 5.0, 5.0])))
        self.assertFalse(_series_is_static(pd.Series([5.0, 6.0, 5.0])))
        self.assertFalse(_series_is_static(pd.Series(dtype="float64")))

    def test_airflow_channels_fuel_lambda_method(self):
        df = pd.DataFrame({
            "DIES_pct": [85.0],
            "BIOD_pct": [15.0],
            "EtOH_pct": [0.0],
            "H2O_pct": [0.0],
            "Consumo_kg_h_mean_of_windows": [5.0],
            "Lambda_mean_of_windows": [1.5],
        })
        result = add_airflow_channels_prefer_maf_inplace(
            df, lambda_col="Lambda_mean_of_windows", maf_col=None,
        )
        self.assertIn("Air_kg_h", result.columns)
        self.assertIn("Airflow_Method", result.columns)
        air = float(result["Air_kg_h"].iloc[0])
        afr_blend = 0.85 * AFR_STOICH_DIESEL + 0.15 * AFR_STOICH_BIODIESEL
        expected = 1.5 * afr_blend * 5.0
        self.assertAlmostEqual(air, expected, places=2)
        self.assertEqual(result["Airflow_Method"].iloc[0], "fuel_lambda")


# =========================================================================== #
#  _emissions (specific_emissions_from_analyzer)
# =========================================================================== #

class TestEmissions(unittest.TestCase):
    def test_mass_balance_conservation(self):
        air = pd.Series([100.0])
        fuel = pd.Series([7.0])
        power = pd.Series([30.0])
        co2 = pd.Series([12.0])
        co = pd.Series([0.1])
        o2 = pd.Series([2.0])
        nox = pd.Series([500.0])
        thc = pd.Series([100.0])
        h2o = pd.Series([0.05])
        result = specific_emissions_from_analyzer(
            air_kg_h=air, fuel_kg_h=fuel, power_kW=power,
            co2_pct_dry=co2, co_pct_dry=co, o2_pct_dry=o2,
            nox_ppm_dry=nox, thc_ppm_dry=thc, h2o_wet_frac=h2o,
        )
        exhaust = float(result["Exhaust_kg_h"].iloc[0])
        self.assertAlmostEqual(exhaust, 107.0, places=1)

    def test_g_kWh_positive_with_nonzero_power(self):
        air = pd.Series([100.0])
        fuel = pd.Series([7.0])
        power = pd.Series([30.0])
        result = specific_emissions_from_analyzer(
            air_kg_h=air, fuel_kg_h=fuel, power_kW=power,
            co2_pct_dry=pd.Series([12.0]), co_pct_dry=pd.Series([0.1]),
            o2_pct_dry=pd.Series([2.0]), nox_ppm_dry=pd.Series([500.0]),
            thc_ppm_dry=pd.Series([100.0]), h2o_wet_frac=pd.Series([0.05]),
        )
        for col in ["CO2_g_kWh", "CO_g_kWh", "NOx_g_kWh"]:
            self.assertGreater(float(result[col].iloc[0]), 0)

    def test_nox_basis_no_vs_no2(self):
        kwargs = dict(
            air_kg_h=pd.Series([100.0]),
            fuel_kg_h=pd.Series([7.0]),
            power_kW=pd.Series([30.0]),
            co2_pct_dry=pd.Series([12.0]),
            co_pct_dry=pd.Series([0.1]),
            o2_pct_dry=pd.Series([2.0]),
            nox_ppm_dry=pd.Series([500.0]),
            thc_ppm_dry=pd.Series([100.0]),
            h2o_wet_frac=pd.Series([0.05]),
        )
        result_no = specific_emissions_from_analyzer(**kwargs, nox_basis="NO")
        result_no2 = specific_emissions_from_analyzer(**kwargs, nox_basis="NO2")
        nox_no = float(result_no["NOx_g_kWh"].iloc[0])
        nox_no2 = float(result_no2["NOx_g_kWh"].iloc[0])
        self.assertGreater(nox_no2, nox_no)
        self.assertAlmostEqual(nox_no2 / nox_no, MW_NO2_KG_KMOL / MW_NO_KG_KMOL, places=1)

    def test_zero_power_gives_na(self):
        result = specific_emissions_from_analyzer(
            air_kg_h=pd.Series([100.0]),
            fuel_kg_h=pd.Series([7.0]),
            power_kW=pd.Series([0.0]),
            co2_pct_dry=pd.Series([12.0]),
            co_pct_dry=pd.Series([0.1]),
            o2_pct_dry=pd.Series([2.0]),
            nox_ppm_dry=pd.Series([500.0]),
            thc_ppm_dry=pd.Series([100.0]),
            h2o_wet_frac=pd.Series([0.05]),
        )
        self.assertTrue(pd.isna(result["CO2_g_kWh"].iloc[0]))


# =========================================================================== #
#  _volumetric_efficiency
# =========================================================================== #

class TestVolumetricEfficiency(unittest.TestCase):
    def test_basic_eta_v(self):
        df = pd.DataFrame({
            "Air_kg_h": [80.0],
            "T_ADMISSAO_mean_of_windows": [25.0],
            "Rotação_mean_of_windows": [2000.0],
            "Airflow_Method": ["MAF"],
        })
        defaults = {
            "engine_displacement_l": "3.992",
            "vol_eff_ref_pressure_kpa": "101.3",
        }
        result = add_volumetric_efficiency_from_airflow_method_inplace(df, defaults)
        self.assertIn("ETA_V", result.columns)
        eta_v = float(result["ETA_V"].iloc[0])
        self.assertGreater(eta_v, 0)
        self.assertLess(eta_v, 2.0)
        self.assertAlmostEqual(float(result["ETA_V_pct"].iloc[0]), eta_v * 100.0)

    def test_eta_v_formula(self):
        displacement_l = 3.992
        t_intake_c = 25.0
        rpm = 2000.0
        ref_p_kpa = 101.3
        air_kg_h = 80.0
        displacement_m3 = displacement_l / 1000.0
        t_k = t_intake_c + 273.15
        rho = (ref_p_kpa * 1000.0) / (R_AIR_DRY_J_KG_K * t_k)
        theoretical = rho * displacement_m3 * (rpm / 2.0) * 60.0
        expected_eta_v = air_kg_h / theoretical

        df = pd.DataFrame({
            "Air_kg_h": [air_kg_h],
            "T_ADMISSAO_mean_of_windows": [t_intake_c],
            "Rotação_mean_of_windows": [rpm],
            "Airflow_Method": ["MAF"],
        })
        defaults = {"engine_displacement_l": str(displacement_l), "vol_eff_ref_pressure_kpa": str(ref_p_kpa)}
        result = add_volumetric_efficiency_from_airflow_method_inplace(df, defaults)
        self.assertAlmostEqual(float(result["ETA_V"].iloc[0]), expected_eta_v, places=6)

    def test_missing_displacement(self):
        df = pd.DataFrame({
            "Air_kg_h": [80.0],
            "T_ADMISSAO_mean_of_windows": [25.0],
            "Rotação_mean_of_windows": [2000.0],
        })
        result = add_volumetric_efficiency_from_airflow_method_inplace(df, {"engine_displacement_l": "0"})
        self.assertTrue(pd.isna(result["ETA_V"].iloc[0]))


# =========================================================================== #
#  _diesel_cost_delta
# =========================================================================== #

class TestDieselCostDelta(unittest.TestCase):
    def test_aggregate_metric_basic(self):
        df = pd.DataFrame({
            "group": ["A", "A", "B"],
            "val": [10.0, 12.0, 20.0],
            "uA": [0.1, 0.2, 0.3],
            "uB": [0.05, 0.06, 0.1],
            "uc": [0.11, 0.21, 0.32],
            "U": [0.22, 0.42, 0.64],
        })
        result = _aggregate_metric_with_uncertainty(
            df, group_cols=["group"],
            value_col="val", uA_col="uA", uB_col="uB", uc_col="uc", U_col="U",
            value_name="metric",
        )
        self.assertEqual(len(result), 2)
        a_row = result[result["group"] == "A"].iloc[0]
        self.assertAlmostEqual(a_row["metric"], 11.0)
        self.assertEqual(a_row["n_points"], 2)

    def test_diesel_cost_delta_with_diesel_points(self):
        df = pd.DataFrame({
            "Fuel_Label": ["D85B15", "D85B15", "E94H6"],
            "Load_kW": [50.0, 50.0, 50.0],
            "DIES_pct": [85.0, 85.0, 0.0],
            "BIOD_pct": [15.0, 15.0, 0.0],
            "EtOH_pct": [0.0, 0.0, 94.0],
            "H2O_pct": [0.0, 0.0, 6.0],
            "Custo_R_h": [100.0, 110.0, 80.0],
            "uA_Custo_R_h": [1.0, 1.5, 0.8],
            "uB_Custo_R_h": [2.0, 2.5, 1.5],
            "uc_Custo_R_h": [2.24, 2.92, 1.7],
            "U_Custo_R_h": [4.47, 5.83, 3.4],
        })
        result = _attach_diesel_cost_delta_metrics(df)
        self.assertIn("Economia_vs_Diesel_pct", result.columns)
        self.assertIn("Razao_Custo_vs_Diesel", result.columns)
        diesel_eco = float(result.loc[result["Fuel_Label"] == "D85B15", "Economia_vs_Diesel_pct"].iloc[0])
        self.assertAlmostEqual(diesel_eco, 0.0)
        ethanol_eco = float(result.loc[result["Fuel_Label"] == "E94H6", "Economia_vs_Diesel_pct"].iloc[0])
        self.assertLess(ethanol_eco, 0)

    def test_diesel_cost_delta_no_diesel(self):
        df = pd.DataFrame({
            "Fuel_Label": ["E94H6"],
            "Load_kW": [50.0],
            "DIES_pct": [0.0],
            "BIOD_pct": [0.0],
            "EtOH_pct": [94.0],
            "H2O_pct": [6.0],
            "Custo_R_h": [80.0],
            "uA_Custo_R_h": [0.8],
            "uB_Custo_R_h": [1.5],
            "uc_Custo_R_h": [1.7],
            "U_Custo_R_h": [3.4],
        })
        result = _attach_diesel_cost_delta_metrics(df)
        self.assertTrue(pd.isna(result["Economia_vs_Diesel_pct"].iloc[0]))


# =========================================================================== #
#  _machine_scenarios
# =========================================================================== #

class TestMachineScenarios(unittest.TestCase):
    def test_resolve_inputs_normal(self):
        defaults = {
            "machine_hours_per_year_colheitadeira": "1200",
            "machine_diesel_l_h_colheitadeira": "30",
        }
        spec = {
            "key": "Colheitadeira",
            "label": "Colheitadeira",
            "hours_param": "MACHINE_HOURS_PER_YEAR_COLHEITADEIRA",
            "diesel_l_h_param": "MACHINE_DIESEL_L_H_COLHEITADEIRA",
        }
        hours, diesel, swapped = _resolve_machine_scenario_inputs(defaults, spec)
        self.assertAlmostEqual(hours, 1200.0)
        self.assertAlmostEqual(diesel, 30.0)
        self.assertFalse(swapped)

    def test_resolve_inputs_swapped(self):
        defaults = {
            "machine_hours_per_year_colheitadeira": "30",
            "machine_diesel_l_h_colheitadeira": "1200",
        }
        spec = {
            "key": "Colheitadeira",
            "label": "Colheitadeira",
            "hours_param": "MACHINE_HOURS_PER_YEAR_COLHEITADEIRA",
            "diesel_l_h_param": "MACHINE_DIESEL_L_H_COLHEITADEIRA",
        }
        hours, diesel, swapped = _resolve_machine_scenario_inputs(defaults, spec)
        self.assertAlmostEqual(hours, 1200.0)
        self.assertAlmostEqual(diesel, 30.0)
        self.assertTrue(swapped)

    def test_machine_scenarios_creates_columns(self):
        df = pd.DataFrame({
            "Fuel_Label": ["E94H6"],
            "DIES_pct": [0.0],
            "BIOD_pct": [0.0],
            "EtOH_pct": [94.0],
            "H2O_pct": [6.0],
            "Economia_vs_Diesel_pct": [-15.0],
            "U_Economia_vs_Diesel_pct": [3.0],
        })
        defaults = {
            "fuel_cost_r_l_d85b15": "6.0",
            "fuel_cost_r_l_e94h6": "4.0",
            "machine_hours_per_year_colheitadeira": "1200",
            "machine_diesel_l_h_colheitadeira": "30",
            "machine_hours_per_year_trator_transbordo": "800",
            "machine_diesel_l_h_trator_transbordo": "20",
            "machine_hours_per_year_caminhao": "1500",
            "machine_diesel_l_h_caminhao": "25",
        }
        result = _attach_e94h6_machine_scenario_metrics(df, defaults)
        self.assertIn("Scenario_Colheitadeira_Hours_Ano", result.columns)
        self.assertIn("Scenario_Colheitadeira_Economia_R_ano", result.columns)
        self.assertIn("Scenario_Trator_Transbordo_Hours_Ano", result.columns)
        self.assertIn("Scenario_Caminhao_Hours_Ano", result.columns)


# =========================================================================== #
#  Stage integration
# =========================================================================== #

class TestBuildFinalTableStage(unittest.TestCase):
    def test_feature_key(self):
        stage = BuildFinalTableStage()
        self.assertEqual(stage.feature_key, "build_final_table")

    def test_skips_when_ponto_is_none(self):
        ctx = MagicMock()
        ctx.ponto = None
        ctx.final_table = None
        ctx.bundle = MagicMock()
        stage = BuildFinalTableStage()
        stage.run(ctx)
        self.assertIsNone(ctx.final_table)

    def test_skips_when_bundle_is_none(self):
        ctx = MagicMock()
        ctx.ponto = pd.DataFrame({"X": [1]})
        ctx.bundle = None
        stage = BuildFinalTableStage()
        stage.run(ctx)


# =========================================================================== #
#  build_final_table orchestrator (integration)
# =========================================================================== #

class TestBuildFinalTableOrchestrator(unittest.TestCase):
    def _minimal_ponto(self):
        return pd.DataFrame({
            "BaseName": ["subindo_aditivado_1__file.xlsx"],
            "Load_kW": [50.0],
            "DIES_pct": [85.0],
            "BIOD_pct": [15.0],
            "EtOH_pct": [0.0],
            "H2O_pct": [0.0],
            "Consumo_kg_h_mean_of_windows": [5.0],
            "Consumo_kg_h_sd_of_windows": [0.05],
            "Potência Total_mean_of_windows": [20.0],
            "Potência Total_sd_of_windows": [0.1],
            "RPM_mean_of_windows": [2000.0],
            "N_trechos_validos": [3],
            "LHV_kJ_kg": [43500.0],
        })

    def _minimal_mappings(self):
        return {
            "consumo_kg_h": {"mean": "Consumo_kg_h_mean_of_windows", "sd": "Consumo_kg_h_sd_of_windows"},
            "potencia": {"mean": "Potência Total_mean_of_windows", "sd": "Potência Total_sd_of_windows"},
            "power_kw": {"mean": "Potência Total_mean_of_windows", "sd": "Potência Total_sd_of_windows"},
            "fuel_kgh": {"mean": "Consumo_kg_h_mean_of_windows", "sd": "Consumo_kg_h_sd_of_windows"},
            "lhv_kj_kg": {"mean": "LHV_kJ_kg"},
        }

    def test_orchestrator_produces_dataframe(self):
        from pipeline_newgen_rev1.runtime.final_table import build_final_table
        result = build_final_table(
            ponto=self._minimal_ponto(),
            fuel_properties=pd.DataFrame(),
            kibox_agg=pd.DataFrame(),
            motec_ponto=pd.DataFrame(),
            mappings=self._minimal_mappings(),
            instruments=[],
            reporting=[],
            defaults={},
        )
        self.assertIsInstance(result, pd.DataFrame)
        self.assertEqual(len(result), 1)

    def test_orchestrator_adds_source_identity(self):
        from pipeline_newgen_rev1.runtime.final_table import build_final_table
        result = build_final_table(
            ponto=self._minimal_ponto(),
            fuel_properties=pd.DataFrame(),
            kibox_agg=pd.DataFrame(),
            motec_ponto=pd.DataFrame(),
            mappings=self._minimal_mappings(),
            instruments=[],
            reporting=[],
            defaults={},
        )
        self.assertIn("SourceFolder", result.columns)
        self.assertIn("Sentido_Carga", result.columns)

    def test_orchestrator_adds_fuel_label(self):
        from pipeline_newgen_rev1.runtime.final_table import build_final_table
        result = build_final_table(
            ponto=self._minimal_ponto(),
            fuel_properties=pd.DataFrame(),
            kibox_agg=pd.DataFrame(),
            motec_ponto=pd.DataFrame(),
            mappings=self._minimal_mappings(),
            instruments=[],
            reporting=[],
            defaults={},
        )
        self.assertIn("Fuel_Label", result.columns)
        self.assertEqual(str(result["Fuel_Label"].iloc[0]), "D85B15")

    def test_orchestrator_empty_ponto(self):
        from pipeline_newgen_rev1.runtime.final_table import build_final_table
        result = build_final_table(
            ponto=pd.DataFrame(),
            fuel_properties=pd.DataFrame(),
            kibox_agg=pd.DataFrame(),
            motec_ponto=pd.DataFrame(),
            mappings={},
            instruments=[],
            reporting=[],
            defaults={},
        )
        self.assertIsInstance(result, pd.DataFrame)
        self.assertEqual(len(result), 0)


# =========================================================================== #
#  ExportExcelStage
# =========================================================================== #

class TestExportExcelStage(unittest.TestCase):
    def test_feature_key(self):
        stage = ExportExcelStage()
        self.assertEqual(stage.feature_key, "export_excel")

    def test_writes_xlsx(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            ctx = MagicMock()
            ctx.final_table = pd.DataFrame({"A": [1, 2], "B": [3, 4]})
            ctx.output_dir = Path(tmpdir)
            ctx.lv_kpis_path = None

            stage = ExportExcelStage()
            stage.run(ctx)

            written = Path(ctx.lv_kpis_path)
            self.assertTrue(written.exists())
            self.assertEqual(written.name, "lv_kpis_clean.xlsx")
            roundtrip = pd.read_excel(written)
            self.assertEqual(list(roundtrip.columns), ["A", "B"])
            self.assertEqual(len(roundtrip), 2)

    def test_skips_when_no_final_table(self):
        ctx = MagicMock()
        ctx.final_table = None
        ctx.lv_kpis_path = None

        stage = ExportExcelStage()
        stage.run(ctx)
        self.assertIsNone(ctx.lv_kpis_path)

    def test_permission_error_fallback(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            target = Path(tmpdir) / "lv_kpis_clean.xlsx"
            target.write_bytes(b"dummy")

            df = pd.DataFrame({"X": [1]})
            original_to_excel = pd.DataFrame.to_excel
            call_count = [0]

            def patched_to_excel(self_df, path, **kwargs):
                call_count[0] += 1
                if call_count[0] == 1:
                    raise PermissionError("file locked")
                return original_to_excel(self_df, path, **kwargs)

            ctx = MagicMock()
            ctx.final_table = df
            ctx.output_dir = Path(tmpdir)
            ctx.lv_kpis_path = None

            import unittest.mock
            with unittest.mock.patch.object(pd.DataFrame, "to_excel", patched_to_excel):
                stage = ExportExcelStage()
                stage.run(ctx)

            written = Path(ctx.lv_kpis_path)
            self.assertTrue(written.exists())
            self.assertNotEqual(written.name, "lv_kpis_clean.xlsx")
            self.assertTrue(written.name.startswith("lv_kpis_clean_"))


if __name__ == "__main__":
    unittest.main()
