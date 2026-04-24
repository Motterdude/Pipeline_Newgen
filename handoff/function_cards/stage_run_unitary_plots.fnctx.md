# stage_run_unitary_plots

## Role
- bridge station that generates the legacy unitary plots from `ctx.final_table` and the bundle's `plots_df`
- wraps `nanum_pipeline_29.py::make_plots_from_config_with_summary`
- corresponds to feature_key `run_unitary_plots`

## Inputs
- `ctx.final_table` (populated by `build_final_table` upstream)
- `ctx.legacy_bundle` (cached by `build_final_table`; reloaded lazily if absent)
- `ctx.output_dir` (the stage writes into `<out>/plots/`)

## Outputs
- `ctx.unitary_plot_summary: dict` — keys: `generated` (int), `generated_labels` (list), `generated_files` (list of abs paths), `skipped` (int), `disabled` (int)
- on disk: PNGs under `<out>/plots/`

## Do Not Break
- skip cleanly when `ctx.final_table is None` — expected when `build_final_table` upstream was itself skipped (dev-env without `[legacy]`, or failed fixture)
- raise `RuntimeError` when `output_dir is None` — wiring bug upstream
- catch legacy exceptions and log — the plot stage must not crash the pipeline summary flow
- the `plots_df` passed to the legacy function must come from the legacy bundle (has different column conventions than the newgen bundle)

## Edit Notes
- reuses `ctx.legacy_bundle` cached by `build_final_table`; a standalone run (no prior bridge) triggers `_ensure_legacy_bundle` to reload
- `plot_dir = ctx.output_dir / "plots"` is the convention — the legacy `make_plots_from_config_with_summary` accepts it explicitly so we don't depend on the module-level `PLOTS_DIR`
- when a native plots implementation ports over, keep the same `feature_key` and `ctx.unitary_plot_summary` schema so downstream consumers (GUI, summary) don't change

## Quick Test
- `python -m unittest tests.test_bridge_unitary_plots`
- smoke: `PYTHONPATH=src python -m pipeline_newgen_rev1.cli run-load-sweep --config-dir config\pipeline29_text --process-dir <raw> --out-dir <tempdir> --json` then inspect `<tempdir>/plots/`
