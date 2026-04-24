"""Bridge stations: wrap functions from the frozen legacy monoliths so they
expose the same `Stage.run(ctx)` contract as native stations.

The rule: one bridge class = one feature_key from ``LOAD_SWEEP_FEATURE_SPECS``.
As each station is ported to a native implementation, its bridge class is
deleted and the corresponding entry is removed from
``runtime.stages.STAGE_REGISTRY``.

Legacy modules are imported lazily by ``_load_legacy_pipeline29()``. The
first call pays the ~2s matplotlib+pandas import cost; subsequent calls
reuse the cached module.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List

import pandas as pd

from .. import legacy_monoliths  # noqa: F401  # triggers sys.path injection

if TYPE_CHECKING:
    from ..runtime.context import RuntimeContext


_LV_KPIS_FILENAME = "lv_kpis_clean.xlsx"
_RAW_PATTERNS = ("*.xlsx", "*.csv")


def _load_legacy_pipeline29() -> Any:
    """Import `nanum_pipeline_29` lazily and return the module object.

    Imported on first use to avoid paying the ~10k-line import cost on
    every session. The ``legacy_monoliths`` package has already placed
    its directory on ``sys.path``, so the bare imports inside the legacy
    file (``from pipeline29_config_backend import ...``) resolve inside
    the frozen copies.
    """
    import importlib

    return importlib.import_module("nanum_pipeline_29")


def _try_load_legacy_pipeline29() -> Any:
    """Same as ``_load_legacy_pipeline29`` but returns ``None`` if the
    legacy module cannot be imported (e.g. ``matplotlib`` missing in the
    dev env). Bridges use this to log-and-skip gracefully so the newgen
    test suite stays runnable without the ``[legacy]`` extra installed.
    """
    try:
        return _load_legacy_pipeline29()
    except ModuleNotFoundError as exc:
        print(f"[INFO] legacy bridge | skipping: {exc.name or exc} not installed")
        return None


def _bucket_metas(legacy: Any, raw_files: List[Path]) -> Dict[str, list]:
    """Classify files via the legacy ``parse_meta`` and bucket by source type."""
    buckets: Dict[str, list] = {"LABVIEW": [], "KIBOX": [], "MOTEC": []}
    for path in raw_files:
        try:
            meta = legacy.parse_meta(path)
        except Exception:
            continue
        bucket = getattr(meta, "source_type", None)
        if bucket in buckets:
            buckets[bucket].append(meta)
    return buckets


def _build_legacy_intermediate_frames(ctx: "RuntimeContext") -> Dict[str, Any]:
    """Reproduce the preparation chain of ``nanum_pipeline_29.main()`` from a
    fresh ``ctx`` so ``build_final_table`` can be called with valid inputs.

    Returns a dict with the four DataFrames expected by ``build_final_table``
    plus the already-loaded config pieces. The caller reuses
    ``legacy_module`` instead of re-importing.
    """
    if ctx.input_dir is None:
        raise RuntimeError("build_final_table bridge requires ctx.input_dir to be resolved first")

    legacy = _load_legacy_pipeline29()
    assert legacy is not None

    # 1. Reload the bundle via the legacy loader so the types match the
    #    legacy function signatures. Newgen's ConfigBundle uses the same
    #    field names but is a distinct class. The legacy loader accepts
    #    only (config_source, text_config_dir, rebuild_text_config) — the
    #    ctx may carry an excel_path, but in bridge mode we always go via
    #    the text config which is the operational default.
    legacy_bundle = legacy.load_pipeline29_config_bundle(
        config_source="text" if ctx.text_config_dir is not None else "auto",
        text_config_dir=ctx.text_config_dir,
    )
    defaults_cfg = legacy_bundle.defaults_cfg
    mappings = legacy_bundle.mappings
    instruments_df = legacy_bundle.instruments_df
    reporting_df = legacy_bundle.reporting_df

    # 2. Set legacy module-level globals (RAW_DIR, PROCESS_DIR, OUT_DIR,
    #    PLOTS_DIR) so subsequent legacy calls see the dirs the runtime
    #    chose. We bypass the legacy ``apply_runtime_path_overrides``
    #    because it routes through ``_choose_runtime_dirs`` which is
    #    potentially interactive; we already resolved dirs upstream via
    #    the newgen ``sync_runtime_dirs`` stage.
    legacy.RAW_DIR = ctx.input_dir
    legacy.PROCESS_DIR = ctx.input_dir
    legacy.OUT_DIR = ctx.output_dir if ctx.output_dir is not None else ctx.input_dir
    legacy.PLOTS_DIR = legacy.OUT_DIR / "plots"
    if hasattr(legacy, "_sync_runtime_dirs_to_config_source"):
        legacy._sync_runtime_dirs_to_config_source(legacy_bundle, legacy.PROCESS_DIR, legacy.OUT_DIR)

    # 3. List raw files under the runtime-selected input dir (the legacy
    #    globals may point elsewhere if the bundle defaults differ; we
    #    respect the ctx choice deliberately).
    raw_files: List[Path] = []
    for pattern in _RAW_PATTERNS:
        raw_files.extend(ctx.input_dir.rglob(pattern))

    buckets = _bucket_metas(legacy, raw_files)
    lv_metas = buckets["LABVIEW"]
    kibox_metas = buckets["KIBOX"]
    motec_metas = buckets["MOTEC"]

    # 4. Read LabVIEW → concat → trechos → ponto
    lv_frames = []
    for meta in lv_metas:
        try:
            lv_frames.append(legacy.read_labview_xlsx(meta))
        except Exception as exc:
            print(f"[WARN] build_final_table bridge | LabVIEW read failed for {meta.path.name}: {exc}")
    lv_raw = pd.concat(lv_frames, ignore_index=True) if lv_frames else pd.DataFrame()

    trechos = legacy.compute_trechos_stats(lv_raw, instruments_df=instruments_df)
    ponto = legacy.compute_ponto_stats(trechos)

    # 5. Fuel properties lookup
    fuel_properties = legacy.load_fuel_properties_lookup(legacy_bundle, defaults_cfg)

    # 6. KiBox aggregate (empty frame if no files)
    if kibox_metas:
        kibox_agg = legacy.kibox_aggregate(kibox_metas)
    else:
        kibox_agg = pd.DataFrame()

    # 7. MoTeC chain
    if motec_metas:
        motec_frames = []
        for meta in motec_metas:
            try:
                motec_frames.append(legacy.read_motec_csv(meta))
            except Exception as exc:
                print(f"[WARN] build_final_table bridge | MoTeC read failed for {meta.path.name}: {exc}")
        motec_raw = pd.concat(motec_frames, ignore_index=True) if motec_frames else pd.DataFrame()
        motec_trechos = legacy.compute_motec_trechos_stats(motec_raw)
        motec_ponto = legacy.compute_motec_ponto_stats(motec_trechos)
    else:
        motec_ponto = pd.DataFrame()

    # Cache the legacy bundle on ctx so downstream bridges (plots,
    # diagnostics) can reuse it without another config I/O round.
    ctx.legacy_bundle = legacy_bundle

    return {
        "ponto": ponto,
        "fuel_properties": fuel_properties,
        "kibox_agg": kibox_agg,
        "motec_ponto": motec_ponto,
        "mappings": mappings,
        "instruments_df": instruments_df,
        "reporting_df": reporting_df,
        "defaults_cfg": defaults_cfg,
        "legacy_module": legacy,
    }


@dataclass(frozen=True)
class BuildFinalTableBridgeStage:
    """Bridge: run the legacy preparation chain then
    ``nanum_pipeline_29.build_final_table``. Populates ``ctx.final_table``
    plus the four intermediate frames on the context so downstream stages
    (``export_excel`` today; ``run_unitary_plots``/diagnostics in Passo 2c)
    can consume them.
    """

    feature_key: str = "build_final_table"

    def run(self, ctx: "RuntimeContext") -> None:
        if ctx.input_dir is None:
            print("[INFO] build_final_table bridge | skipping (ctx.input_dir not resolved)")
            return
        if _try_load_legacy_pipeline29() is None:
            # Dev-env without matplotlib. Leave ctx.final_table as None so
            # downstream export_excel also no-ops. Real runs install [legacy].
            return

        try:
            frames = _build_legacy_intermediate_frames(ctx)
            legacy = frames["legacy_module"]

            ctx.ponto = frames["ponto"]
            ctx.fuel_properties = frames["fuel_properties"]
            ctx.kibox_agg = frames["kibox_agg"]
            ctx.motec_ponto = frames["motec_ponto"]

            ctx.final_table = legacy.build_final_table(
                frames["ponto"],
                frames["fuel_properties"],
                frames["kibox_agg"],
                frames["motec_ponto"],
                frames["mappings"],
                frames["instruments_df"],
                frames["reporting_df"],
                frames["defaults_cfg"],
            )
            rows = len(ctx.final_table) if ctx.final_table is not None else 0
            print(f"[OK] build_final_table bridge | rows={rows}")
        except Exception as exc:
            # The legacy chain is strict about required columns (e.g.
            # ``B_Etanol`` in LabVIEW). Minimal synthetic fixtures used by
            # newgen tests don't satisfy that. In real runs with raw_NANUM
            # data the chain completes; in tests we log and leave
            # ``ctx.final_table`` as ``None`` so the pipeline proceeds.
            print(f"[WARN] build_final_table bridge | legacy chain failed: {type(exc).__name__}: {exc}")


def _ensure_legacy_bundle(ctx: "RuntimeContext", legacy: Any) -> Any:
    """Return ``ctx.legacy_bundle`` if already cached; otherwise load it
    via the legacy loader and cache it. Used by bridges that run after
    ``build_final_table`` (which caches the bundle first)."""
    if ctx.legacy_bundle is not None:
        return ctx.legacy_bundle
    ctx.legacy_bundle = legacy.load_pipeline29_config_bundle(
        config_source="text" if ctx.text_config_dir is not None else "auto",
        text_config_dir=ctx.text_config_dir,
    )
    return ctx.legacy_bundle


@dataclass(frozen=True)
class RunUnitaryPlotsBridgeStage:
    """Bridge: generate the legacy unitary plots via
    ``nanum_pipeline_29.make_plots_from_config_with_summary`` using
    ``ctx.final_table`` and the bundle's ``plots_df``. Writes PNGs into
    ``<out_dir>/plots/`` and stores the run summary in
    ``ctx.unitary_plot_summary``.
    """

    feature_key: str = "run_unitary_plots"

    def run(self, ctx: "RuntimeContext") -> None:
        if ctx.final_table is None:
            print("[INFO] run_unitary_plots bridge | nothing to plot (final_table is None)")
            return
        if ctx.output_dir is None:
            raise RuntimeError("run_unitary_plots bridge requires ctx.output_dir to be resolved first")
        legacy = _try_load_legacy_pipeline29()
        if legacy is None:
            return

        bundle = _ensure_legacy_bundle(ctx, legacy)
        plot_dir = ctx.output_dir / "plots"
        plot_dir.mkdir(parents=True, exist_ok=True)

        try:
            ctx.unitary_plot_summary = legacy.make_plots_from_config_with_summary(
                ctx.final_table,
                bundle.plots_df,
                bundle.mappings,
                plot_dir=plot_dir,
            )
            summary = ctx.unitary_plot_summary or {}
            generated = summary.get("generated", 0)
            skipped = summary.get("skipped", 0)
            disabled = summary.get("disabled", 0)
            print(f"[OK] run_unitary_plots bridge | generated={generated} skipped={skipped} disabled={disabled} dir={plot_dir}")
        except Exception as exc:
            print(f"[WARN] run_unitary_plots bridge | legacy plot run failed: {type(exc).__name__}: {exc}")


@dataclass(frozen=True)
class ExportExcelBridgeStage:
    """Bridge: write ``ctx.final_table`` to ``<out_dir>/lv_kpis_clean.xlsx``
    using the legacy ``safe_to_excel`` helper.

    When ``build_final_table`` runs upstream, ``ctx.final_table`` is a real
    DataFrame and this stage writes the legacy-equivalent ``lv_kpis_clean.xlsx``.
    If upstream was skipped, the stage logs and returns.
    """

    feature_key: str = "export_excel"

    def run(self, ctx: "RuntimeContext") -> None:
        if ctx.final_table is None:
            print("[INFO] export_excel bridge | nothing to write (final_table is None)")
            return
        if ctx.output_dir is None:
            raise RuntimeError("export_excel bridge requires ctx.output_dir to be resolved first")

        legacy = _load_legacy_pipeline29()
        target_path = ctx.output_dir / _LV_KPIS_FILENAME
        ctx.lv_kpis_path = legacy.safe_to_excel(ctx.final_table, target_path)
        print(f"[OK] export_excel bridge | wrote {ctx.lv_kpis_path}")
