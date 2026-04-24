from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from _path import ROOT  # noqa: F401
from pipeline_newgen_rev1.adapters.input_discovery import discover_input_file
from pipeline_newgen_rev1.adapters.motec_reader import read_motec_csv, summarize_motec_read


def _write_motec_csv(path: Path) -> None:
    lines = [
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
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


class MotecReaderTests(unittest.TestCase):
    def test_read_motec_csv_enriches_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            path = root / "50KW_D85B15_m.csv"
            _write_motec_csv(path)

            result = read_motec_csv(path, process_root=root)
            summary = summarize_motec_read(result)

            self.assertEqual(result.meta.source_type, "MOTEC")
            self.assertEqual(result.meta.load_kw, 50.0)
            self.assertEqual(result.meta.dies_pct, 85.0)
            self.assertEqual(result.meta.biod_pct, 15.0)
            self.assertEqual(len(result.rows), 2)
            self.assertEqual(result.rows[0]["Motec_Time"], "0.00")
            self.assertIsNone(result.rows[0]["Motec_Time_Delta_s"])
            self.assertAlmostEqual(result.rows[1]["Motec_Time_Delta_s"], 0.02)
            self.assertEqual(result.rows[0]["WindowID"], 0)
            self.assertEqual(summary["metadata"]["Motec_SampleRate_Hz"], 50.0)
            self.assertEqual(summary["metadata"]["Motec_Duration_s"], 2.0)

    def test_read_motec_csv_accepts_discovered_meta(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            path = root / "run_lambda_1,20_m.csv"
            _write_motec_csv(path)
            meta = discover_input_file(path, roots=(root,))

            result = read_motec_csv(path, process_root=root, meta=meta)

            self.assertEqual(result.meta.sweep_key, "lambda")
            self.assertEqual(result.meta.sweep_value, 1.2)


if __name__ == "__main__":
    unittest.main()
