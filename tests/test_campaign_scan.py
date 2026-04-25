"""Tests for runtime/campaign_scan.py — campaign structure scanner."""
from __future__ import annotations

import unittest
from pathlib import Path

from _path import ROOT  # noqa: F401
from pipeline_newgen_rev1.adapters import DiscoveredRuntimeInputs, InputFileMeta
from pipeline_newgen_rev1.runtime.campaign_scan import (
    CampaignCatalog,
    default_comparison_pairs,
    fuel_label_from_meta,
    infer_campaign_from_path,
    infer_direction_from_path,
    scan_campaign_structure,
    summarize_campaign_catalog,
)


def _meta(
    name: str = "test.xlsx",
    source_type: str = "LABVIEW",
    load_kw: float | None = 50.0,
    dies_pct: float | None = None,
    biod_pct: float | None = None,
    etoh_pct: float | None = None,
    h2o_pct: float | None = None,
    parent: str = "C:/data",
) -> InputFileMeta:
    return InputFileMeta(
        path=Path(parent) / name,
        basename=name,
        source_type=source_type,
        load_kw=load_kw,
        dies_pct=dies_pct,
        biod_pct=biod_pct,
        etoh_pct=etoh_pct,
        h2o_pct=h2o_pct,
    )


class TestFuelLabelFromMeta(unittest.TestCase):
    def test_e94h6(self) -> None:
        label = fuel_label_from_meta(_meta(etoh_pct=94.0, h2o_pct=6.0))
        self.assertEqual(label, "E94H6")

    def test_e75h25(self) -> None:
        label = fuel_label_from_meta(_meta(etoh_pct=75.0, h2o_pct=25.0))
        self.assertEqual(label, "E75H25")

    def test_d85b15(self) -> None:
        label = fuel_label_from_meta(_meta(dies_pct=85.0, biod_pct=15.0))
        self.assertEqual(label, "D85B15")

    def test_no_composition(self) -> None:
        label = fuel_label_from_meta(_meta())
        self.assertIsInstance(label, str)


class TestInferDirection(unittest.TestCase):
    def test_subida_folder(self) -> None:
        self.assertEqual(infer_direction_from_path("C:/data/baseline_subida"), "subida")

    def test_descendo_folder(self) -> None:
        self.assertEqual(infer_direction_from_path("C:/data/descendo_iter1"), "descida")

    def test_up_folder(self) -> None:
        self.assertEqual(infer_direction_from_path("C:/data/run_up"), "subida")

    def test_down_folder(self) -> None:
        self.assertEqual(infer_direction_from_path("C:/data/run_down"), "descida")

    def test_no_direction(self) -> None:
        self.assertIsNone(infer_direction_from_path("C:/data/E94H6"))


class TestInferCampaign(unittest.TestCase):
    def test_baseline(self) -> None:
        self.assertEqual(infer_campaign_from_path("C:/data/baseline_subida"), "baseline")

    def test_aditivado(self) -> None:
        self.assertEqual(infer_campaign_from_path("C:/data/aditivado_descida"), "aditivado")

    def test_ref(self) -> None:
        self.assertEqual(infer_campaign_from_path("C:/data/ref_run"), "baseline")

    def test_no_campaign(self) -> None:
        self.assertIsNone(infer_campaign_from_path("C:/data/E94H6"))


class TestScanFuelBased(unittest.TestCase):
    """Thesis data: files in same directory, grouped by fuel label."""

    def setUp(self) -> None:
        files = [
            _meta("50KW_E94H6.xlsx", etoh_pct=94.0, h2o_pct=6.0, load_kw=50.0, parent="C:/data"),
            _meta("30KW_E94H6.xlsx", etoh_pct=94.0, h2o_pct=6.0, load_kw=30.0, parent="C:/data"),
            _meta("50KW_E75H25.xlsx", etoh_pct=75.0, h2o_pct=25.0, load_kw=50.0, parent="C:/data"),
            _meta("30KW_E75H25.xlsx", etoh_pct=75.0, h2o_pct=25.0, load_kw=30.0, parent="C:/data"),
            _meta("50KW_E65H35.xlsx", etoh_pct=65.0, h2o_pct=35.0, load_kw=50.0, parent="C:/data"),
            _meta("30KW_E65H35.xlsx", etoh_pct=65.0, h2o_pct=35.0, load_kw=30.0, parent="C:/data"),
        ]
        self.discovery = DiscoveredRuntimeInputs(process_dir=Path("C:/data"), files=files)

    def test_iteration_mode_fuel(self) -> None:
        catalog = scan_campaign_structure(self.discovery)
        self.assertEqual(catalog.iteration_mode, "fuel")

    def test_fuel_labels(self) -> None:
        catalog = scan_campaign_structure(self.discovery)
        self.assertEqual(catalog.fuel_labels, ["E65H35", "E75H25", "E94H6"])

    def test_load_points(self) -> None:
        catalog = scan_campaign_structure(self.discovery)
        self.assertEqual(catalog.load_points, [30.0, 50.0])

    def test_no_directions(self) -> None:
        catalog = scan_campaign_structure(self.discovery)
        self.assertEqual(catalog.directions, [])

    def test_no_campaigns(self) -> None:
        catalog = scan_campaign_structure(self.discovery)
        self.assertEqual(catalog.campaigns, [])

    def test_file_counts(self) -> None:
        catalog = scan_campaign_structure(self.discovery)
        self.assertEqual(catalog.file_count_by_fuel["E94H6"], 2)
        self.assertEqual(catalog.file_count_by_fuel["E75H25"], 2)
        self.assertEqual(catalog.total_files, 6)


class TestScanDirectionBased(unittest.TestCase):
    """Stellantis data: baseline/aditivado with subida/descida."""

    def setUp(self) -> None:
        files = [
            _meta("50KW_D85B15.xlsx", dies_pct=85.0, biod_pct=15.0, load_kw=50.0, parent="C:/data/baseline_subida"),
            _meta("50KW_D85B15.xlsx", dies_pct=85.0, biod_pct=15.0, load_kw=50.0, parent="C:/data/baseline_descida"),
            _meta("50KW_D85B15.xlsx", dies_pct=85.0, biod_pct=15.0, load_kw=50.0, parent="C:/data/aditivado_subida"),
            _meta("50KW_D85B15.xlsx", dies_pct=85.0, biod_pct=15.0, load_kw=50.0, parent="C:/data/aditivado_descida"),
        ]
        self.discovery = DiscoveredRuntimeInputs(process_dir=Path("C:/data"), files=files)

    def test_iteration_mode_direction(self) -> None:
        catalog = scan_campaign_structure(self.discovery)
        self.assertEqual(catalog.iteration_mode, "direction")

    def test_directions_detected(self) -> None:
        catalog = scan_campaign_structure(self.discovery)
        self.assertEqual(catalog.directions, ["descida", "subida"])

    def test_campaigns_detected(self) -> None:
        catalog = scan_campaign_structure(self.discovery)
        self.assertEqual(catalog.campaigns, ["aditivado", "baseline"])


class TestScanEmpty(unittest.TestCase):
    def test_empty_discovery(self) -> None:
        discovery = DiscoveredRuntimeInputs(process_dir=Path("C:/empty"), files=[])
        catalog = scan_campaign_structure(discovery)
        self.assertEqual(catalog.fuel_labels, [])
        self.assertEqual(catalog.total_files, 0)
        self.assertEqual(catalog.iteration_mode, "fuel")

    def test_non_labview_files_skipped(self) -> None:
        files = [
            _meta("test_i.csv", source_type="KIBOX", load_kw=50.0, parent="C:/data"),
            _meta("test_m.csv", source_type="MOTEC", load_kw=50.0, parent="C:/data"),
        ]
        discovery = DiscoveredRuntimeInputs(process_dir=Path("C:/data"), files=files)
        catalog = scan_campaign_structure(discovery)
        self.assertEqual(catalog.total_files, 0)


class TestDefaultComparisonPairs(unittest.TestCase):
    def test_fuel_based_pairs(self) -> None:
        catalog = CampaignCatalog(
            fuel_labels=["E65H35", "E75H25", "E94H6"],
            load_points=[30.0, 50.0],
            directions=[],
            campaigns=[],
            iteration_mode="fuel",
            file_count_by_fuel={"E65H35": 2, "E75H25": 2, "E94H6": 2},
            file_count_by_campaign={},
            file_count_by_direction={},
            total_files=6,
        )
        pairs = default_comparison_pairs(catalog)
        self.assertEqual(pairs, [("E65H35", "E75H25"), ("E65H35", "E94H6")])

    def test_direction_based_pairs(self) -> None:
        catalog = CampaignCatalog(
            fuel_labels=["D85B15"],
            load_points=[50.0],
            directions=["descida", "subida"],
            campaigns=["aditivado", "baseline"],
            iteration_mode="direction",
            file_count_by_fuel={"D85B15": 4},
            file_count_by_campaign={"baseline": 2, "aditivado": 2},
            file_count_by_direction={"subida": 2, "descida": 2},
            total_files=4,
        )
        pairs = default_comparison_pairs(catalog)
        self.assertIn(("aditivado_descida", "baseline_descida"), pairs)
        self.assertIn(("aditivado_subida", "baseline_subida"), pairs)
        self.assertIn(("aditivado_media", "baseline_media"), pairs)

    def test_single_fuel_no_pairs(self) -> None:
        catalog = CampaignCatalog(
            fuel_labels=["E94H6"],
            load_points=[50.0],
            directions=[],
            campaigns=[],
            iteration_mode="fuel",
            file_count_by_fuel={"E94H6": 1},
            file_count_by_campaign={},
            file_count_by_direction={},
            total_files=1,
        )
        self.assertEqual(default_comparison_pairs(catalog), [])


class TestSummarizeCatalog(unittest.TestCase):
    def test_summary_keys(self) -> None:
        catalog = CampaignCatalog(
            fuel_labels=["E94H6"],
            load_points=[50.0],
            directions=[],
            campaigns=[],
            iteration_mode="fuel",
            file_count_by_fuel={"E94H6": 1},
            file_count_by_campaign={},
            file_count_by_direction={},
            total_files=1,
        )
        summary = summarize_campaign_catalog(catalog)
        self.assertIn("iteration_mode", summary)
        self.assertIn("fuel_labels", summary)
        self.assertIn("total_files", summary)


class TestStageRegistration(unittest.TestCase):
    def test_stage_in_registry(self) -> None:
        from pipeline_newgen_rev1.runtime.stages import STAGE_REGISTRY, PROCESSING_STAGE_ORDER
        self.assertIn("scan_campaign_structure", STAGE_REGISTRY)
        self.assertIn("scan_campaign_structure", PROCESSING_STAGE_ORDER)

    def test_stage_before_compare(self) -> None:
        from pipeline_newgen_rev1.runtime.stages import PROCESSING_STAGE_ORDER
        scan_idx = PROCESSING_STAGE_ORDER.index("scan_campaign_structure")
        compare_idx = PROCESSING_STAGE_ORDER.index("compute_compare_iteracoes")
        self.assertLess(scan_idx, compare_idx)


if __name__ == "__main__":
    unittest.main()
