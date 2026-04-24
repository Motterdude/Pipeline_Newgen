from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

from _path import ROOT  # noqa: F401
from pipeline_newgen_rev1.adapters.input_discovery import discover_input_file
from pipeline_newgen_rev1.adapters.labview_reader import (
    choose_labview_sheet,
    read_labview_xlsx,
    summarize_labview_read,
)


@unittest.skipIf(importlib.util.find_spec("openpyxl") is None, "openpyxl not installed")
class LabviewReaderTests(unittest.TestCase):
    def _write_workbook(self, path: Path) -> None:
        from openpyxl import Workbook

        workbook = Workbook()
        worksheet = workbook.active
        worksheet.title = "labview"
        worksheet.append(["Carga (kW)", "P_COLETOR", "Sensor A", "Unnamed: 4"])
        worksheet.append([49.9, -1000, 10.0, "x"])
        worksheet.append([50.1, 101.3, 11.0, "y"])
        workbook.save(path)

    def test_choose_labview_sheet_prefers_named_sheet(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "50KW_E75H25.xlsx"
            self._write_workbook(path)
            self.assertEqual(choose_labview_sheet(path), "labview")

    def test_read_labview_xlsx_enriches_rows_and_sanitizes_pressure(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            path = root / "50KW_E75H25.xlsx"
            self._write_workbook(path)

            result = read_labview_xlsx(path, process_root=root)
            summary = summarize_labview_read(result)

            self.assertEqual(result.meta.source_type, "LABVIEW")
            self.assertEqual(result.meta.load_kw, 50.0)
            self.assertEqual(result.meta.etoh_pct, 75.0)
            self.assertEqual(result.meta.h2o_pct, 25.0)
            self.assertEqual(result.sheet_name, "labview")
            self.assertEqual(len(result.rows), 2)
            self.assertNotIn("Unnamed: 4", result.columns)
            self.assertEqual(result.rows[0]["P_COLETOR"], None)
            self.assertEqual(result.rows[0]["Load_kW"], 50.0)
            self.assertEqual(result.rows[0]["Load_Signal_kW"], 50.0)
            self.assertEqual(result.rows[0]["WindowID"], 0)
            self.assertEqual(summary["pressure_sentinel_hits"]["P_COLETOR"], 1)
            self.assertEqual(summary["inferred_single_load_kw"], 50.0)

    def test_read_labview_xlsx_can_fallback_to_signal_when_filename_has_no_load(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            path = root / "E75H25.xlsx"
            self._write_workbook(path)
            meta = discover_input_file(path, roots=(root,))

            result = read_labview_xlsx(path, process_root=root, meta=meta)

            self.assertIsNone(meta.load_kw)
            self.assertEqual(result.load_source, "signal")
            self.assertEqual(result.rows[0]["Load_kW"], 50.0)


if __name__ == "__main__":
    unittest.main()
