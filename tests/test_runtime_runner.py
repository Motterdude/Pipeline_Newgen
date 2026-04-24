from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from openpyxl import Workbook

from _path import ROOT  # noqa: F401
from pipeline_newgen_rev1.config import RuntimeState, save_runtime_state
from pipeline_newgen_rev1.runtime import run_load_sweep
from pipeline_newgen_rev1.ui.runtime_preflight.models import RuntimeSelection


def _write_labview(path: Path) -> None:
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "labview"
    worksheet.append(["Carga (kW)", "P_COLETOR"])
    worksheet.append([50, 101.3])
    workbook.save(path)


def _write_motec(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "Sample Rate,50",
                "Duration,2.0",
                "Header3,x",
                "Header4,x",
                "Header5,x",
                "Header6,x",
                "Header7,x",
                "Header8,x",
                "Header9,x",
                "Header10,x",
                "Header11,x",
                "Header12,x",
                "Header13,x",
                "Header14,x",
                "Time,Lambda,Pressure",
                "s,-,-",
                "0.00,1.10,101.0",
                "0.02,1.11,101.2",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def _write_kibox(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                "intro",
                "Cycle;AI05_1;AI90_1;Pressure;TextCol;Dummy",
                "1;10,5;20,5;101,3;ok;x",
                "2;11,5;21,5;102,3;ok;y",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


class RuntimeRunnerTests(unittest.TestCase):
    def test_run_load_sweep_writes_summary_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            config_dir = root / "config" / "pipeline29_text"
            config_dir.mkdir(parents=True, exist_ok=True)
            (config_dir / "metadata.toml").write_text('schema_version = 1\n\n[metadata]\nformat = "pipeline29_text"\n', encoding="utf-8")
            (config_dir / "defaults.toml").write_text(f'schema_version = 1\n\n[defaults]\nRAW_INPUT_DIR = "{str(root / "raw").replace("\\", "\\\\")}"\nOUT_DIR = "{str(root / "out").replace("\\", "\\\\")}"\n', encoding="utf-8")
            (config_dir / "data_quality.toml").write_text("schema_version = 1\n\n[data_quality]\n", encoding="utf-8")
            (config_dir / "mappings.toml").write_text(
                'schema_version = 1\n\n[mappings.power_kw]\nmean = "Power_kW"\n\n[mappings.fuel_kgh]\nmean = "Fuel_kg_h"\n\n[mappings.lhv_kj_kg]\nmean = "LHV_kJ_kg"\n',
                encoding="utf-8",
            )
            (config_dir / "instruments.toml").write_text("schema_version = 1\n", encoding="utf-8")
            (config_dir / "reporting_rounding.toml").write_text("schema_version = 1\n", encoding="utf-8")
            (config_dir / "plots.toml").write_text("schema_version = 1\n", encoding="utf-8")

            raw = root / "raw"
            raw.mkdir(parents=True, exist_ok=True)
            _write_labview(raw / "50KW_E75H25.xlsx")
            _write_motec(raw / "50KW_D85B15_m.csv")
            _write_kibox(raw / "campaign_a" / "50KW_D85B15_i.csv")

            state_path = root / "runtime_state.json"
            save_runtime_state(
                state_path,
                RuntimeState(
                    raw_input_dir=raw,
                    out_dir=root / "out",
                    selection=RuntimeSelection(aggregation_mode="load"),
                    helper_configured=True,
                    dirs_configured_in_gui=True,
                    config_dir=config_dir,
                ),
            )

            result = run_load_sweep(
                project_root=root,
                config_source="text",
                text_config_dir=config_dir,
                state_path=state_path,
            )

            self.assertEqual(result.summary["labview_files"], 1)
            self.assertEqual(result.summary["motec_files"], 1)
            self.assertEqual(result.summary["kibox_files"], 1)
            self.assertTrue(result.summary_json_path.exists())
            self.assertTrue(result.summary_xlsx_path.exists())
            payload = json.loads(result.summary_json_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["total_inputs"], 3)

    def test_run_load_sweep_can_force_runtime_dirs_and_plot_filter(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            config_dir = root / "config" / "pipeline29_text"
            config_dir.mkdir(parents=True, exist_ok=True)
            (config_dir / "metadata.toml").write_text('schema_version = 1\n\n[metadata]\nformat = "pipeline29_text"\n', encoding="utf-8")
            (config_dir / "defaults.toml").write_text(f'schema_version = 1\n\n[defaults]\nRAW_INPUT_DIR = "{str(root / "raw_default").replace("\\", "\\\\")}"\nOUT_DIR = "{str(root / "out_default").replace("\\", "\\\\")}"\n', encoding="utf-8")
            (config_dir / "data_quality.toml").write_text("schema_version = 1\n\n[data_quality]\n", encoding="utf-8")
            (config_dir / "mappings.toml").write_text(
                'schema_version = 1\n\n[mappings.power_kw]\nmean = "Power_kW"\n\n[mappings.fuel_kgh]\nmean = "Fuel_kg_h"\n\n[mappings.lhv_kj_kg]\nmean = "LHV_kJ_kg"\n',
                encoding="utf-8",
            )
            (config_dir / "instruments.toml").write_text("schema_version = 1\n", encoding="utf-8")
            (config_dir / "reporting_rounding.toml").write_text("schema_version = 1\n", encoding="utf-8")
            (config_dir / "plots.toml").write_text("schema_version = 1\n", encoding="utf-8")

            raw = root / "raw_selected"
            raw.mkdir(parents=True, exist_ok=True)
            _write_labview(raw / "50KW_E75H25.xlsx")
            chosen_out = root / "out_selected"
            state_path = root / "runtime_state.json"
            save_runtime_state(
                state_path,
                RuntimeState(
                    raw_input_dir=root / "raw_saved",
                    out_dir=root / "out_saved",
                    selection=RuntimeSelection(aggregation_mode="load"),
                    helper_configured=True,
                    dirs_configured_in_gui=True,
                    config_dir=config_dir,
                ),
            )

            result = run_load_sweep(
                project_root=root,
                config_source="text",
                text_config_dir=config_dir,
                state_path=state_path,
                prompt_runtime_dirs=True,
                prompt_plot_filter=True,
                _runtime_dirs_prompt_func=lambda _input, _output: (raw, chosen_out),
                _plot_filter_prompt_func=lambda fuel_labels, load_values, counts: {("E75H25", 50.0)},
            )

            self.assertEqual(result.summary["process_dir"], str(raw.resolve()))
            self.assertEqual(result.summary["out_dir"], str(chosen_out.resolve()))
            self.assertEqual(result.summary["selected_plot_points_count"], 1)


if __name__ == "__main__":
    unittest.main()
