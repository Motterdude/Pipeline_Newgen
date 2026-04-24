# 2026-04-24 — bridge-unitary-plots (Passo 2c)

## O que mudou

- **`src/pipeline_newgen_rev1/runtime/context.py`** — 2 slots novos:
  - `legacy_bundle: Any = None` — cache do `Pipeline29ConfigBundle` do legado entre bridges (build_final_table salva, run_unitary_plots reusa).
  - `unitary_plot_summary: Optional[Dict[str, Any]] = None` — guarda o dict que `make_plots_from_config_with_summary` retorna (chaves `generated`, `generated_labels`, `generated_files`, `skipped`, `disabled`).
- **`src/pipeline_newgen_rev1/bridges/legacy_runtime.py`** — adições:
  - `_ensure_legacy_bundle(ctx, legacy)` — retorna `ctx.legacy_bundle` se cacheado; senão carrega via `legacy.load_pipeline29_config_bundle` e cacheia.
  - `RunUnitaryPlotsBridgeStage(feature_key="run_unitary_plots")` — roda `make_plots_from_config_with_summary(ctx.final_table, bundle.plots_df, bundle.mappings, plot_dir=ctx.output_dir/'plots')`. Skip com log se `final_table is None`; catch-and-log se a função legada disparar.
  - `_build_legacy_intermediate_frames` agora escreve `ctx.legacy_bundle = legacy_bundle` para o run_unitary_plots não precisar recarregar.
- **`src/pipeline_newgen_rev1/runtime/stages/__init__.py`** — registra `RunUnitaryPlotsBridgeStage` após `export_excel` em `STAGE_REGISTRY` e `STAGE_PIPELINE_ORDER`.
- **`tests/test_bridge_unitary_plots.py`** (novo) — 3 casos com mock do legado via `sys.modules["nanum_pipeline_29"] = stub`:
  - `test_skips_when_final_table_is_none` — nada acontece, diretório `plots/` não é criado.
  - `test_invokes_legacy_plot_function_and_stores_summary` — verifica que bundle é carregado sob demanda, `make_plots_from_config_with_summary` é chamado com dirs corretos, summary é gravado.
  - `test_catches_legacy_exception_gracefully` — exceção do legado vira warning; ctx não quebra.
- **Smoke real com raw do legacy repo (`raw/subindo_aditivado_1/`)**: 37 PNGs gerados em `<out>/plots/`, lista e bytes **idênticos** ao baseline standalone do legado.

## Por quê

Passo 2c fecha a trilogia 2a/2b/2c. Agora o newgen produz via bridge:
- `lv_kpis_clean.xlsx` (Passo 2b) — paridade byte-a-byte confirmada (19×511 DataFrame idêntico ao baseline).
- Plots unitários PNG em `<out>/plots/` (Passo 2c) — 37/37 PNGs idênticos em tamanho ao baseline.

Isto é o fim da "fase de terceirização": rodar o newgen hoje, com `pip install .[legacy]`, entrega a mesma coisa que o monolito legado (para os módulos já cobertos). Os Passos 3+ vão PORTAR cada estação bridge para nativa, uma por vez, com fixture de paridade comparando newgen nativo × bridge legado — infraestrutura que agora temos pronta.

## Arquivos

- `handoff/changes/2026-04-24-bridge-unitary-plots.md` (novo — este arquivo)
- `handoff/CHANGES_INDEX.md` (entrada no topo)
- `handoff/stages_status.md` (Fase 3 "Plots unitários" 🔴 → 🟡 bridge)
- `handoff/function_cards/stage_run_unitary_plots.fnctx.md` (novo)
- `handoff/function_cards/bridge_legacy_runtime.fnctx.md` (atualizado)
- `src/pipeline_newgen_rev1/runtime/context.py` (2 slots)
- `src/pipeline_newgen_rev1/bridges/legacy_runtime.py` (+ helper + 1 classe)
- `src/pipeline_newgen_rev1/runtime/stages/__init__.py` (registry + ordem)
- `tests/test_bridge_unitary_plots.py` (novo)

## Validação

- `python -m unittest discover -s tests -p "test_*.py"` → **61 testes, OK, 0 skipped** (matplotlib instalado agora; +3 do bridge novo).
- **Paridade numérica** do `lv_kpis_clean.xlsx`: `DataFrame.equals(baseline) == True` sobre 19×511 células. Smoke em `raw/subindo_aditivado_1/` do legacy repo (18 xlsx LabVIEW).
- **Paridade de plots**: 37 PNGs, mesma lista de nomes, mesmo tamanho em bytes.
- `export_excel` bridge agora produz arquivo real em runs reais (`rows=19`, `79877 bytes`).
- Warnings do legado propagam (airflow/emissions/etc.) — comportamento esperado do monolito quando só há LV sem MoTeC/KiBox.

## Pendências

- **Bridge `run_time_diagnostics`**: opcional. Consome `ctx.labview_frames` (ou re-lê). Decidir se entra num Passo 2d ou fica esperando até um port nativo pedir.
- **Bridges `run_compare_plots`, `run_compare_iteracoes`, `run_special_load_plots`**: análogas à `run_unitary_plots`, mas exigem agrupamentos/iteracoes específicos. Perfil similar ao 2c; podem ser feitas quando a GUI precisar delas.
- **Bridge `apply_sweep_binning`, `prompt_sweep_duplicate_selector`, `rewrite_plot_axis_to_sweep`**: modo sweep. Não bloqueantes do modo load.
- **Port nativo**: com a fundação bridge estável, Passo 3 pode começar. Ordem sugerida (da decisão 2026-04-23): `run_time_diagnostics` → `build_final_table` (sub-partes) → `export_excel` → `run_unitary_plots` → ... Cada port precisa de fixture em `tests/fixtures/paridade/` + test comparando nativo × bridge legado.
- **matplotlib como dep default** (sair de `[legacy]`) quando o primeiro port depender dele; por enquanto fica opt-in.
- **Sincronizar git ↔ OneDrive** antes de qualquer Save & Run do usuário.
