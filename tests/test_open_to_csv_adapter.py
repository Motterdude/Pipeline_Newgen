from __future__ import annotations

import io
import os
import tempfile
import textwrap
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from _path import ROOT  # noqa: F401
from pipeline_newgen_rev1.adapters import (
    build_output_name,
    export_open_file,
    export_open_inputs,
    find_open_to_csv_path,
    planned_pipeline_csv_name,
    planned_pipeline_csv_path,
    summarize_export_results,
)
from pipeline_newgen_rev1.adapters.open_to_csv import ExportRequest
from pipeline_newgen_rev1.cli import main as cli_main


def _write_fake_converter(script_path: Path) -> None:
    script_path.write_text(
        textwrap.dedent(
            """
            from pathlib import Path
            import sys

            args = {}
            flags = set()
            for item in sys.argv[1:]:
                if "=" in item:
                    key, value = item.split("=", 1)
                    args[key] = value
                else:
                    flags.add(item)

            source_dir = Path(args["sourcepath"])
            export_type = args.get("type", "res")
            export_dir = source_dir / "CSVExport"
            export_dir.mkdir(parents=True, exist_ok=True)

            for open_file in source_dir.glob("*.open"):
                out_path = export_dir / f"{open_file.stem}_{export_type}.csv"
                out_path.write_text("Cycle\\tValue\\n1\\t123\\n", encoding="utf-8")

            print(f"fake converter ran on {source_dir}")
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )


class OpenToCsvAdapterTests(unittest.TestCase):
    def test_planned_pipeline_name_uses_i_suffix(self) -> None:
        source = Path(r"C:\tmp\run_01.open")
        self.assertEqual(planned_pipeline_csv_name(source), "run_01_i.csv")
        self.assertEqual(planned_pipeline_csv_path(source).name, "run_01_i.csv")
        self.assertEqual(build_output_name(source, name_mode="tool", export_type="res"), "run_01_res.csv")

    def test_find_open_to_csv_path_uses_env_var(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_converter = Path(tmpdir) / "fake_OpenToCSV.py"
            _write_fake_converter(fake_converter)
            with patch.dict(os.environ, {"PIPELINE_NEWGEN_OPENTOCSV_PATH": str(fake_converter), "LOCALAPPDATA": tmpdir}, clear=False):
                resolved = find_open_to_csv_path()
            self.assertEqual(resolved, fake_converter.resolve())

    def test_export_open_file_supports_python_converter_script(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            fake_converter = root / "fake_OpenToCSV.py"
            _write_fake_converter(fake_converter)
            source_open = root / "sample.open"
            source_open.write_text("open payload", encoding="utf-8")
            destination = root / "out"

            with patch.dict(os.environ, {"LOCALAPPDATA": tmpdir}, clear=False):
                result = export_open_file(
                    ExportRequest(source_open=source_open, destination_dir=destination, name_mode="pipeline"),
                    converter_path=fake_converter,
                )

            self.assertEqual(result.exported_csv.name, "sample_i.csv")
            self.assertTrue(result.exported_csv.exists())
            self.assertIn("fake converter ran", result.stdout)

    def test_export_open_inputs_preserves_relative_subfolders(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            fake_converter = root / "fake_OpenToCSV.py"
            _write_fake_converter(fake_converter)
            input_root = root / "input"
            nested = input_root / "campaign_a"
            nested.mkdir(parents=True, exist_ok=True)
            (nested / "a.open").write_text("a", encoding="utf-8")
            (input_root / "b.open").write_text("b", encoding="utf-8")
            output_root = root / "output"

            with patch.dict(os.environ, {"LOCALAPPDATA": tmpdir}, clear=False):
                results = export_open_inputs(input_root, output_root=output_root, converter_path=fake_converter)

            summary = summarize_export_results(results)
            self.assertEqual(summary["converted_files"], 2)
            self.assertTrue((output_root / "campaign_a" / "a_i.csv").exists())
            self.assertTrue((output_root / "b_i.csv").exists())

    def test_cli_convert_open_json_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            fake_converter = root / "fake_OpenToCSV.py"
            _write_fake_converter(fake_converter)
            source_open = root / "cli_sample.open"
            source_open.write_text("cli", encoding="utf-8")

            buffer = io.StringIO()
            with patch.dict(os.environ, {"LOCALAPPDATA": tmpdir}, clear=False):
                with redirect_stdout(buffer):
                    exit_code = cli_main(
                        [
                            "convert-open",
                            str(source_open),
                            "--converter",
                            str(fake_converter),
                            "--json",
                        ]
                    )

            self.assertEqual(exit_code, 0)
            output = buffer.getvalue()
            self.assertIn('"converted_files": 1', output)
            self.assertIn("cli_sample_i.csv", output)


if __name__ == "__main__":
    unittest.main()
