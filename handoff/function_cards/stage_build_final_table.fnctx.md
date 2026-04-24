# stage_build_final_table

## Role
- bridge station that reproduces the preparation chain of `nanum_pipeline_29.main()` and runs `build_final_table` to produce `ctx.final_table`
- feeds the downstream `export_excel` bridge so `lv_kpis_clean.xlsx` gets written with legacy-equivalent content
- corresponds to feature_key `build_final_table`

## Inputs
- `ctx.input_dir` (resolved by `sync_runtime_dirs` upstream)
- `ctx.text_config_dir` / `ctx.excel_path` (the bridge reloads the bundle via the legacy loader for type fidelity)
- legacy module `nanum_pipeline_29` importable (requires `pip install .[legacy]` for matplotlib)

## Outputs
- `ctx.final_table: pd.DataFrame` — the ~100-column KPI table used by `export_excel` and future plot bridges
- `ctx.ponto`, `ctx.fuel_properties`, `ctx.kibox_agg`, `ctx.motec_ponto` — intermediate frames made available for downstream debugging and for future bridges (diagnostics, unitary plots) that consume them

## Do Not Break
- if `ctx.input_dir is None`, log and return (sync_runtime_dirs has not run yet — surface as a wiring bug elsewhere)
- if the legacy module is not importable (dev env without `[legacy]`), return gracefully via `_try_load_legacy_pipeline29()` — keeps the newgen test suite runnable
- the chain call order is load-bearing: `apply_runtime_path_overrides` **must** precede every other legacy call because it mutates module-level globals (`PROCESS_DIR`, `OUT_DIR`, `PLOTS_DIR`) that the downstream functions read
- do not swap the legacy readers for the newgen adapters here — the point of the bridge is paridade byte-for-byte with the monolith. Reader ports get their own fixture-backed paridade test.

## Edit Notes
- the 11 call sequence is documented in `_build_legacy_intermediate_frames`: reload bundle → apply_runtime_path_overrides → list raw → parse_meta/bucket → read_labview_xlsx × N → compute_trechos_stats → compute_ponto_stats → load_fuel_properties_lookup → kibox_aggregate → MoTeC chain → build_final_table
- when any of the underlying legacy functions is ported natively (e.g. `compute_ponto_stats` gets a newgen implementation), swap the call here **one step at a time** and add a paridade test per swap
- this stage stays a bridge until `build_final_table` itself is ported; at that point the class is replaced by a native one that still takes `ctx` and still populates `ctx.final_table` under the same `feature_key`

## Quick Test
- `python -m unittest tests.test_bridge_build_final_table`
- smoke with legacy installed: `pip install .[legacy]` then `python -m pipeline_newgen_rev1.cli run-load-sweep --config-dir config\pipeline29_text --process-dir E:\raw_pyton\raw_NANUM --out-dir E:\out_Nanum_rev2 --json`
