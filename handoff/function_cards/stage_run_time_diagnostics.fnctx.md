# stage_run_time_diagnostics

## Role
- **native** station that diagnoses per-sample time-delta quality and ACT/ECT control loop errors of the LV acquisitions
- consumes the concatenated `ctx.labview_frames`; produces the same artifacts the legacy `main()` used to: `lv_time_diagnostics.xlsx`, `lv_diagnostics_summay.xlsx` (typo preserved from legacy), plus `<output_dir>/plots/time_delta_to_next_all_samples.png` and `<output_dir>/plots/time_delta_by_file/*.png`
- corresponds to feature_key `run_time_diagnostics`, stage `diagnostics`, default on in both load and sweep modes

## Inputs
- `ctx.labview_frames: List[pd.DataFrame]` — populated by `_discover_and_read_inputs` in the runner (phase 1 → discovery → phase 2)
- `ctx.output_dir: Path` — where xlsx and PNGs go
- `ctx.bundle.data_quality: Dict[str, float]` — carries `MAX_DELTA_BETWEEN_SAMPLES_ms`, `MAX_ACT_CONTROL_ERROR`, `MAX_ECT_CONTROL_ERROR`. Defaults (1200 ms, 5°C, 2°C) apply if keys absent.

## Outputs
- `ctx.time_diagnostics: pd.DataFrame` — one row per sample, 26 columns incl. TIME_DELTA_TO_NEXT_s, TIME_DELTA_ERROR_FLAG, ACT/ECT error flags
- `ctx.time_diagnostics_summary: pd.DataFrame` — one row per BaseName (rolled-up status OK/ERRO/NA + transiente times)
- Files written: `lv_time_diagnostics.xlsx`, `lv_diagnostics_summay.xlsx`, `plots/time_delta_to_next_all_samples.png`, `plots/time_delta_by_file/*.png` (one per BaseName)

## Do Not Break
- if `ctx.labview_frames` is empty, log and return cleanly — the stage must not fail the pipeline when there are no LV inputs
- if `ctx.output_dir is None`, log and return — upstream wiring responsibility (sync_runtime_dirs)
- the xlsx filename `lv_diagnostics_summay.xlsx` preserves a legacy typo — renaming is a separate decision, not to be "fixed" opportunistically
- plot output dimensions and styling match legacy byte-for-byte; if you change dpi/figsize/colors, run `python scripts/compare_cycle.py` to confirm paridade holds
- this is a **pure consumer** of `ctx.labview_frames` — no mutations of lv_raw. Adding columns to the input frames is a regression waiting to happen.

## Edit Notes
- subpackage `runtime/time_diagnostics/` is the logic home. Stage file is a thin wrapper.
- `core.build_time_diagnostics` adds per-sample TIME_PARSED + error flags. Mirrors `nanum_pipeline_29.py:2097-2219` verbatim.
- `summary.summarize_time_diagnostics` rolls up per BaseName. Mirrors `nanum_pipeline_29.py:2285-2383`.
- `plots.plot_time_delta_all_samples` / `plot_time_delta_by_file` reproduce the legacy PNG output 1:1 (1200×600 for all_samples, 1200×450 per-file, dpi 150).
- helpers `_canon_name`, `_basename_source_folder_parts`, `_infer_sentido_carga_from_folder_parts`, `_infer_iteracao_from_folder_parts`, `_parse_time_series`, `_find_first_col_by_substrings`, `_safe_name` are private to the subpackage. If another consumer appears (e.g. native `compute_trechos_stats` port), promote to `runtime/_utils/` with explicit port reference.
- this stage runs in `PROCESSING_STAGE_ORDER` (after `_discover_and_read_inputs` populates `ctx.labview_frames`) and **before** `build_final_table`. Order is declared in `runtime/stages/__init__.py`.

## Quick Test
- `python -m unittest discover -s tests -p "test_run_time_diagnostics.py"` — 7 unit tests
- paridade smoke: `python scripts/compare_cycle.py` → `plots.byte_identical_count` should be 56 (37 unitários + 19 time_delta + 1 all_samples), `plots.missing_in_newgen` empty
