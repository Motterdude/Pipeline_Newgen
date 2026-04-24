from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pandas as pd

from _path import ROOT  # noqa: F401
from pipeline_newgen_rev1.ui.legacy.pipeline29_config_backend import (
    DEFAULT_COMPARE_COLUMNS,
    DEFAULT_FUEL_PROPERTY_COLUMNS,
    DEFAULT_INSTRUMENT_COLUMNS,
    DEFAULT_MAPPING_COLUMNS,
    DEFAULT_PLOT_COLUMNS,
    DEFAULT_REPORTING_COLUMNS,
    Pipeline29ConfigBundle,
    default_gui_state_path,
    load_bundle_preset,
    load_gui_state,
    save_bundle_preset,
    save_gui_state,
    save_text_config_bundle,
    load_text_config_bundle,
)


def _sample_bundle(tmpdir: str) -> Pipeline29ConfigBundle:
    return Pipeline29ConfigBundle(
        mappings={
            "power_kw": {"mean": "Power_kW", "sd": "Power_SD", "unit": "kW", "notes": ""},
            "fuel_kgh": {"mean": "Fuel_kg_h", "sd": "", "unit": "kg/h", "notes": ""},
            "lhv_kj_kg": {"mean": "LHV_kJ_kg", "sd": "", "unit": "kJ/kg", "notes": ""},
        },
        instruments_df=pd.DataFrame([{"key": "power_kw", "component": "dyno", "source": "bench"}], columns=DEFAULT_INSTRUMENT_COLUMNS),
        reporting_df=pd.DataFrame([{"key": "power_kw", "report_resolution": "0.1", "report_digits": "1", "rule": "round"}], columns=DEFAULT_REPORTING_COLUMNS),
        plots_df=pd.DataFrame([{"enabled": "1", "with_uncertainty": "1", "without_uncertainty": "0", "plot_type": "all_fuels_yx", "filename": "power_vs_load.png", "title": "", "x_col": "Load_kW", "y_col": "Power_kW"}], columns=DEFAULT_PLOT_COLUMNS),
        compare_df=pd.DataFrame([{"enabled": "1", "with_uncertainty": "1", "without_uncertainty": "0", "left_series": "baseline_media", "right_series": "aditivado_media", "metric_id": "consumo"}], columns=DEFAULT_COMPARE_COLUMNS),
        fuel_properties_df=pd.DataFrame([{"Fuel_Label": "D85B15", "DIES_pct": "85", "BIOD_pct": "15"}], columns=DEFAULT_FUEL_PROPERTY_COLUMNS),
        data_quality_cfg={"MAX_DELTA_BETWEEN_SAMPLES_ms": 500.0},
        defaults_cfg={"RAW_INPUT_DIR": tmpdir, "OUT_DIR": tmpdir},
        source_kind="text",
        source_path=Path(tmpdir),
        text_dir=Path(tmpdir),
    )


class LegacyGuiBackendTests(unittest.TestCase):
    def test_text_bundle_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir) / "config" / "pipeline29_text"
            saved = save_text_config_bundle(_sample_bundle(tmpdir), config_dir)
            loaded = load_text_config_bundle(config_dir)

            self.assertEqual(saved.defaults_cfg["RAW_INPUT_DIR"], tmpdir)
            self.assertEqual(loaded.mappings["power_kw"]["mean"], "Power_kW")
            self.assertIn("left_series", loaded.compare_df.columns)

    def test_preset_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            preset_path = Path(tmpdir) / "sample.json"
            save_bundle_preset(_sample_bundle(tmpdir), preset_path)
            loaded = load_bundle_preset(preset_path)
            self.assertEqual(loaded.reporting_df.iloc[0]["key"], "power_kw")
            self.assertEqual(loaded.compare_df.iloc[0]["metric_id"], "consumo")

    def test_gui_state_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = Path(tmpdir) / "gui_state.json"
            payload = {"config_dir": tmpdir, "active_tab": 3}
            save_gui_state(payload, state_path)
            self.assertEqual(load_gui_state(state_path), payload)
            self.assertTrue(str(default_gui_state_path()).endswith("config_gui_state.json"))


if __name__ == "__main__":
    unittest.main()
