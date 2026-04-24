from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from _path import ROOT  # noqa: F401
from pipeline_newgen_rev1.ui.runtime_preflight import (
    PreflightCancelledError,
    RuntimeSelection,
    available_sweep_keys_from_paths,
    build_runtime_preflight_snapshot,
    choose_runtime_preflight,
    parse_filename_sweep,
    planned_pipeline_csv_path,
    scan_open_conversion_status,
    scan_runtime_input_inventory,
)
from pipeline_newgen_rev1.ui.runtime_preflight.prompt import prompt_runtime_preflight_via_cli


def _write_fake_converter(script_path: Path) -> None:
    script_path.write_text(
        (
            "from pathlib import Path\n"
            "import sys\n"
            "args = {}\n"
            "for item in sys.argv[1:]:\n"
            "    if '=' in item:\n"
            "        key, value = item.split('=', 1)\n"
            "        args[key] = value\n"
            "source_dir = Path(args['sourcepath'])\n"
            "export_dir = source_dir / 'CSVExport'\n"
            "export_dir.mkdir(parents=True, exist_ok=True)\n"
            "for open_file in source_dir.glob('*.open'):\n"
            "    (export_dir / f'{open_file.stem}_res.csv').write_text('Cycle\\tValue\\n1\\t1\\n', encoding='utf-8')\n"
            "print('runtime preflight fake converter ran')\n"
        ),
        encoding="utf-8",
    )


class RuntimePreflightScanTests(unittest.TestCase):
    def test_parse_filename_sweep_detects_lambda(self) -> None:
        sweep_key, sweep_value, source = parse_filename_sweep("ensaio_lambda_1,50")
        self.assertEqual(sweep_key, "lambda")
        self.assertEqual(sweep_value, 1.5)
        self.assertEqual(source, "filename_lambda")

    def test_planned_pipeline_csv_path_uses_i_suffix(self) -> None:
        path = planned_pipeline_csv_path(Path(r"C:\tmp\run_01.open"))
        self.assertEqual(path.name, "run_01_i.csv")

    def test_inventory_and_open_scan(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "a.xlsx").write_text("", encoding="utf-8")
            (root / "run_i.csv").write_text("", encoding="utf-8")
            (root / "run_m.csv").write_text("", encoding="utf-8")
            (root / "missing.open").write_text("", encoding="utf-8")
            (root / "done.open").write_text("", encoding="utf-8")
            (root / "done_i.csv").write_text("", encoding="utf-8")
            (root / "~$temp.xlsx").write_text("", encoding="utf-8")

            inventory = scan_runtime_input_inventory(root)
            conversion = scan_open_conversion_status(root)

            self.assertEqual(inventory.lv_count, 1)
            self.assertEqual(inventory.kibox_csv_count, 2)
            self.assertEqual(inventory.motec_csv_count, 1)
            self.assertEqual(len(conversion.open_files), 2)
            self.assertEqual(len(conversion.missing_csv_opens), 1)
            self.assertEqual(conversion.existing_csv_count, 1)

    def test_available_sweep_keys_falls_back_to_default(self) -> None:
        keys = available_sweep_keys_from_paths([Path("plain_file.xlsx")])
        self.assertEqual(keys, ["lambda"])

    def test_build_snapshot_aggregates_scan_results(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "load_lambda_1,2.xlsx").write_text("", encoding="utf-8")
            snapshot = build_runtime_preflight_snapshot(root)
            self.assertEqual(snapshot.inventory.lv_count, 1)
            self.assertEqual(snapshot.available_sweep_keys, ["lambda"])


class RuntimePreflightServiceTests(unittest.TestCase):
    def test_choose_runtime_preflight_can_loop_through_convert(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "run_lambda_1,00.open").write_text("", encoding="utf-8")

            calls = {"prompt": 0, "convert": 0}

            def fake_prompt(snapshot, current):
                calls["prompt"] += 1
                if calls["prompt"] == 1:
                    return "convert", RuntimeSelection(
                        aggregation_mode="sweep",
                        sweep_key="lambda",
                        sweep_x_col="Lambda_Medida",
                        sweep_bin_tol=0.02,
                    )
                return "continue", RuntimeSelection(
                    aggregation_mode="sweep",
                    sweep_key="lambda",
                    sweep_x_col="Lambda_Medida",
                    sweep_bin_tol=0.02,
                )

            def fake_convert(status):
                calls["convert"] += 1
                for source_open in status.missing_csv_opens:
                    planned_pipeline_csv_path(source_open).write_text("", encoding="utf-8")

            selection = choose_runtime_preflight(
                process_dir=root,
                prompt_func=fake_prompt,
                convert_func=fake_convert,
            )
            self.assertEqual(selection.aggregation_mode, "sweep")
            self.assertEqual(selection.sweep_key, "lambda")
            self.assertEqual(selection.sweep_x_col, "Lambda_Medida")
            self.assertEqual(calls["prompt"], 2)
            self.assertEqual(calls["convert"], 1)

    def test_choose_runtime_preflight_raises_on_cancel(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            with self.assertRaises(PreflightCancelledError):
                choose_runtime_preflight(
                    process_dir=root,
                    prompt_func=lambda snapshot, current: ("cancel", current),
                )

    def test_choose_runtime_preflight_can_use_default_converter_adapter(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            fake_converter = root / "fake_OpenToCSV.py"
            _write_fake_converter(fake_converter)
            (root / "run_lambda_1,00.open").write_text("", encoding="utf-8")

            calls = {"prompt": 0}

            def fake_prompt(snapshot, current):
                calls["prompt"] += 1
                if calls["prompt"] == 1:
                    return "convert", RuntimeSelection(
                        aggregation_mode="load",
                        sweep_key="lambda",
                        sweep_x_col="Sweep_Value",
                        sweep_bin_tol=0.015,
                    )
                return "continue", current

            with patch.dict(
                os.environ,
                {"PIPELINE_NEWGEN_OPENTOCSV_PATH": str(fake_converter), "LOCALAPPDATA": tmpdir},
                clear=False,
            ):
                selection = choose_runtime_preflight(
                    process_dir=root,
                    prompt_func=fake_prompt,
                )

            self.assertEqual(selection.aggregation_mode, "load")
            self.assertTrue((root / "run_lambda_1,00_i.csv").exists())

    def test_prompt_runtime_preflight_via_cli_supports_continue(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "sweep_lambda_1,10.open").write_text("", encoding="utf-8")
            snapshot = build_runtime_preflight_snapshot(root)
            answers = iter(["sweep", "lambda", "n"])
            action, selection = prompt_runtime_preflight_via_cli(
                snapshot,
                RuntimeSelection(aggregation_mode="load", sweep_key="lambda"),
                input_func=lambda _prompt: next(answers),
            )
            self.assertEqual(action, "continue")
            self.assertEqual(selection.aggregation_mode, "sweep")
            self.assertEqual(selection.sweep_key, "lambda")


if __name__ == "__main__":
    unittest.main()
