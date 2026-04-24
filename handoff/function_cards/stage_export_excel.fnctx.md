# stage_export_excel

## Role
- bridge station that writes `ctx.final_table` to `<out_dir>/lv_kpis_clean.xlsx`
- wraps `nanum_pipeline_29.py::safe_to_excel` (rounding + PermissionError fallback)
- corresponds to feature_key `export_excel`

## Inputs
- `ctx.final_table: Optional[pd.DataFrame]` — produced by a future `build_final_table` station (Passo 2b)
- `ctx.output_dir: Path`

## Outputs
- `ctx.lv_kpis_path: Path` — absolute path of the written workbook
- on disk: `<out_dir>/lv_kpis_clean.xlsx` (or a timestamped fallback if the target is locked)

## Do Not Break
- gracefully skip when `ctx.final_table is None` — this is the expected state until Passo 2b ships
- raise `RuntimeError` when `final_table` is set but `output_dir` is not — sign of wiring failure upstream
- do not touch `ctx.summary` or artifact paths — those belong to the runtime summary helper in `runner.py`

## Edit Notes
- when `build_final_table` is ported natively, the input to this bridge stays the same; this class remains a bridge as long as `safe_to_excel` is not ported (keep `[legacy]` dep)
- if a custom rounding/incerteza layer migrates before `safe_to_excel`, wrap both here temporarily

## Quick Test
- `python -m unittest tests.test_bridge_export_excel`
