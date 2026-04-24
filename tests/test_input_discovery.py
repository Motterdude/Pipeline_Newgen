from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from _path import ROOT  # noqa: F401
from pipeline_newgen_rev1.adapters.input_discovery import (
    build_input_basename,
    classify_source_type,
    discover_input_file,
    discover_runtime_inputs,
    parse_filename_composition,
    parse_filename_load,
    summarize_discovered_inputs,
)


class InputDiscoveryTests(unittest.TestCase):
    def test_classify_source_type_by_suffix(self) -> None:
        self.assertEqual(classify_source_type(Path("sample_i.csv")), "KIBOX")
        self.assertEqual(classify_source_type(Path("sample_m.csv")), "MOTEC")
        self.assertEqual(classify_source_type(Path("sample.xlsx")), "LABVIEW")

    def test_parse_filename_load_detects_kw(self) -> None:
        load_kw, load_parse = parse_filename_load("50KW_E75H25")
        self.assertEqual(load_kw, 50.0)
        self.assertEqual(load_parse, "filename")

    def test_parse_filename_composition_detects_ethanol_hydrated(self) -> None:
        dies_pct, biod_pct, etoh_pct, h2o_pct, source = parse_filename_composition("50KW_E75H25")
        self.assertIsNone(dies_pct)
        self.assertIsNone(biod_pct)
        self.assertEqual(etoh_pct, 75.0)
        self.assertEqual(h2o_pct, 25.0)
        self.assertEqual(source, "filename_ethanol")

    def test_parse_filename_composition_detects_diesel_biodiesel(self) -> None:
        dies_pct, biod_pct, etoh_pct, h2o_pct, source = parse_filename_composition("D85B15_lambda_1,20")
        self.assertEqual(dies_pct, 85.0)
        self.assertEqual(biod_pct, 15.0)
        self.assertIsNone(etoh_pct)
        self.assertIsNone(h2o_pct)
        self.assertEqual(source, "filename_diesel")

    def test_build_input_basename_uses_relative_parts(self) -> None:
        root = Path("C:/tmp/process")
        path = root / "nested" / "run_01_i.csv"
        self.assertEqual(build_input_basename(path, roots=(root,)), "nested__run_01_i")

    def test_discover_input_file_parses_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "campaign" / "50KW_E75H25_lambda_1,10_i.csv"
            source.parent.mkdir(parents=True, exist_ok=True)
            source.write_text("", encoding="utf-8")

            meta = discover_input_file(source, roots=(root,))

            self.assertEqual(meta.basename, "campaign__50KW_E75H25_lambda_1,10_i")
            self.assertEqual(meta.source_type, "KIBOX")
            self.assertEqual(meta.load_kw, 50.0)
            self.assertEqual(meta.etoh_pct, 75.0)
            self.assertEqual(meta.h2o_pct, 25.0)
            self.assertEqual(meta.sweep_key, "lambda")
            self.assertEqual(meta.sweep_value, 1.1)

    def test_discover_runtime_inputs_summarizes_all_sources(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "10KW_D85B15.xlsx").write_text("", encoding="utf-8")
            (root / "10KW_D85B15_i.csv").write_text("", encoding="utf-8")
            (root / "10KW_D85B15_m.csv").write_text("", encoding="utf-8")
            (root / "~$ignore.xlsx").write_text("", encoding="utf-8")

            discovery = discover_runtime_inputs(root)
            summary = summarize_discovered_inputs(discovery)

            self.assertEqual(summary["total_files"], 3)
            self.assertEqual(summary["by_source"]["LABVIEW"], 1)
            self.assertEqual(summary["by_source"]["KIBOX"], 1)
            self.assertEqual(summary["by_source"]["MOTEC"], 1)
            self.assertEqual(summary["files_with_load"], 3)
            self.assertEqual(summary["files_with_composition"], 3)


if __name__ == "__main__":
    unittest.main()
