from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from _path import ROOT  # noqa: F401
from pipeline_newgen_rev1.adapters.input_discovery import discover_input_file
from pipeline_newgen_rev1.adapters.kibox_reader import (
    aggregate_kibox_mean,
    read_kibox_csv,
    summarize_kibox_aggregate,
    summarize_kibox_read,
)


def _write_kibox_csv(path: Path) -> None:
    lines = [
        "some intro line",
        "another intro line",
        "Cycle;AI05_1;AI90_1;Pressure;Unnamed: 4;TextCol",
        "1;10,5;20,5;101,3;x;ok",
        "2;11,5;21,5;102,3;y;ok",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


class KiboxReaderTests(unittest.TestCase):
    def test_read_kibox_csv_detects_header_and_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            path = root / "campaign_a" / "50KW_D85B15_i.csv"
            path.parent.mkdir(parents=True, exist_ok=True)
            _write_kibox_csv(path)

            result = read_kibox_csv(path, process_root=root)
            summary = summarize_kibox_read(result)

            self.assertEqual(result.meta.source_type, "KIBOX")
            self.assertEqual(result.header_row, 2)
            self.assertEqual(len(result.rows), 2)
            self.assertNotIn("Unnamed: 4", result.columns)
            self.assertEqual(result.rows[0]["AI05_1"], "10,5")
            self.assertEqual(summary["load_kw"], 50.0)

    def test_aggregate_kibox_mean_builds_kibox_prefixed_row(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            path = root / "campaign_a" / "50KW_D85B15_i.csv"
            path.parent.mkdir(parents=True, exist_ok=True)
            _write_kibox_csv(path)

            result = aggregate_kibox_mean(path, process_root=root)
            summary = summarize_kibox_aggregate(result)

            self.assertIn("AI05_1", result.kept_columns)
            self.assertAlmostEqual(result.aggregate_row["KIBOX_AI05_1"], 11.0)
            self.assertAlmostEqual(result.aggregate_row["KIBOX_AI90_1"], 21.0)
            self.assertEqual(result.aggregate_row["SourceFolder"], "campaign_a")
            self.assertEqual(summary["load_kw"], 50.0)

    def test_aggregate_kibox_mean_accepts_discovered_meta(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            path = root / "run_lambda_1,20_i.csv"
            _write_kibox_csv(path)
            meta = discover_input_file(path, roots=(root,))

            result = aggregate_kibox_mean(path, process_root=root, meta=meta)

            self.assertEqual(result.meta.sweep_key, "lambda")
            self.assertEqual(result.meta.sweep_value, 1.2)


if __name__ == "__main__":
    unittest.main()
