# 2026-04-25 — port-time-diagnostics

## O que mudou

Port nativo da estação `run_time_diagnostics` para o pacote newgen (Passo 3a).

- **`src/pipeline_newgen_rev1/runtime/time_diagnostics/`** (novo subpacote, ~500 linhas):
  - `constants.py` — constantes portadas de `nanum_pipeline_29.py:104-112` (TIME_DELTA_ERROR_THRESHOLD_S, DEFAULT_MAX_DELTA_BETWEEN_SAMPLES_MS, TIME_DIAG_PLOT_DPI, etc.)
  - `core.py` — port de `build_time_diagnostics` (legado 2097-2219) + helpers privados `_parse_time_series` (2081), `_find_first_col_by_substrings` (612), `_canon_name` (262), `_basename_parts/_basename_source_folder_parts/_basename_source_folder_display/_basename_source_file` (626-645), `_infer_sentido_carga_from_folder_parts` (803), `_infer_iteracao_from_folder_parts` (813), e versões privadas `_add_source_identity` / `_add_run_context` (versões enxutas de `add_source_identity_columns` e `add_run_context_columns`)
  - `summary.py` — port de `summarize_time_diagnostics` (legado 2285-2383) + helpers `_time_diag_status_from_flags`, `_first_last_transient_times`
  - `plots.py` — port de `plot_time_delta_all_samples` (legado 2386-2441) e `plot_time_delta_by_file` (2443-2525) + helpers `_safe_name`, `_time_diag_load_title`, `_time_diag_load_slug`, `_apply_time_delta_axis_format`
  - `__init__.py` — exports públicos
- **`src/pipeline_newgen_rev1/runtime/stages/run_time_diagnostics.py`** (novo) — estação `RunTimeDiagnosticsStage` (dataclass frozen). Consome `ctx.labview_frames` + `ctx.output_dir` + `ctx.bundle.data_quality`; chama as 4 funções do subpacote; grava `ctx.time_diagnostics` e `ctx.time_diagnostics_summary`; escreve os 2 xlsx (`lv_time_diagnostics.xlsx`, `lv_diagnostics_summay.xlsx` — typo do legado preservado) e os PNGs em `plots/`.
- **`src/pipeline_newgen_rev1/runtime/context.py`** — 2 slots novos no `RuntimeContext`: `time_diagnostics` e `time_diagnostics_summary`.
- **`src/pipeline_newgen_rev1/runtime/stages/__init__.py`** — split de `STAGE_PIPELINE_ORDER` em 2 tuplas:
  - `CONFIG_STAGE_ORDER` (load_text_config, sync_runtime_dirs, show_runtime_preflight) — rodam **antes** de `_discover_and_read_inputs`
  - `PROCESSING_STAGE_ORDER` (run_time_diagnostics, build_final_table, export_excel, run_unitary_plots) — rodam **depois**, consumindo `ctx.labview_frames`
  - `STAGE_PIPELINE_ORDER` continua exportado como união para compatibilidade com `show-plan` e testes.
- **`src/pipeline_newgen_rev1/runtime/runner.py`** — `run_load_sweep` refatorado para o fluxo em 2 fases: config stages → finalize + discover → processing stages → summary.
- **`tests/test_run_time_diagnostics.py`** (novo — 7 casos):
  - `test_builds_expected_columns` — synthetic lv_raw, verifica 31 colunas esperadas no output.
  - `test_empty_input_returns_empty` — DataFrame vazio → output vazio.
  - `test_missing_time_column_returns_empty` — sem coluna Time → output vazio.
  - `test_summary_rollup_one_row_per_basename` — 3 arquivos sintéticos → summary com 3 linhas.
  - `test_plots_per_file_produces_n_pngs` — 3 arquivos → 3 PNGs em `time_delta_by_file/`.
  - `test_skips_when_labview_frames_empty` — stage pula sem quebrar.
  - `test_tighter_max_delta_flags_more_samples` — respeita `MAX_DELTA_BETWEEN_SAMPLES_ms` do bundle.
- **`handoff/stages_status.md`** — linha `run_time_diagnostics` 🔴 → 🟢; newgen path = `runtime/time_diagnostics/` + `runtime/stages/run_time_diagnostics.py`; Última mudança = 2026-04-25.
- **`handoff/function_cards/stage_run_time_diagnostics.fnctx.md`** (novo) — card operacional.

## Por quê

O `scripts/compare_cycle.py` rodado em 2026-04-25 mostrou que o newgen produzia 37/56 PNGs byte-idênticos ao legado — faltavam 19 PNGs em `plots/time_delta_by_file/` + 1 `time_delta_to_next_all_samples.png`. Eles são produzidos pela função `build_time_diagnostics` + seus 2 plotters do legado e não têm equivalente no newgen.

O port nativo:

1. **Fecha o gap** — newgen passa a gerar os 20 PNGs byte-idênticos ao legado (56/56).
2. **Remove dependência do galpão antigo** — nenhuma chamada a `nanum_pipeline_29.py` em `legacy_monoliths/` é necessária para essa saída; a estação é 100% nativa.
3. **Abre caminho para 3b/3c** — o refactor do runner (split config vs processing) permite que futuras estações nativas (como o port nativo de `compute_trechos_stats` ou de `build_final_table`) consumam `ctx.labview_frames` sem mais bridges.

Escolha "port nativo direto" (em vez de bridge primeiro) foi feita pelo usuário sabendo que: (a) `build_time_diagnostics` não depende de cálculo legado — só lê lv_raw e usa limites do `data_quality.toml`; (b) o driver `compare_cycle.py` já serve como smoke de paridade pós-port; (c) é o menor passo autocontido antes de atacar 3b (`build_final_table` + uA/uB separados em derivadas).

## Arquivos

- `src/pipeline_newgen_rev1/runtime/time_diagnostics/__init__.py` (novo)
- `src/pipeline_newgen_rev1/runtime/time_diagnostics/constants.py` (novo)
- `src/pipeline_newgen_rev1/runtime/time_diagnostics/core.py` (novo)
- `src/pipeline_newgen_rev1/runtime/time_diagnostics/summary.py` (novo)
- `src/pipeline_newgen_rev1/runtime/time_diagnostics/plots.py` (novo)
- `src/pipeline_newgen_rev1/runtime/stages/run_time_diagnostics.py` (novo)
- `src/pipeline_newgen_rev1/runtime/stages/__init__.py` (modificado — 2 tuplas ordem + registrada)
- `src/pipeline_newgen_rev1/runtime/runner.py` (modificado — 2 fases)
- `src/pipeline_newgen_rev1/runtime/context.py` (modificado — 2 slots)
- `tests/test_run_time_diagnostics.py` (novo)
- `handoff/stages_status.md` (atualizado)
- `handoff/function_cards/stage_run_time_diagnostics.fnctx.md` (novo)
- `handoff/changes/2026-04-25-port-time-diagnostics.md` (novo — este arquivo)
- `handoff/CHANGES_INDEX.md` (nova linha)

## Validação

- `python -m unittest discover -s tests -p "test_*.py"` → **68 testes OK**, 0 skip (era 61).
- `py_compile` → OK em todos os arquivos novos.
- `python scripts/compare_cycle.py` → `plots.byte_identical_count = 56` (era 37). `plots.missing_in_newgen = []` (era 19). `plots.byte_different_count = 0`. `plots.extra_in_newgen = []`.
- Sanity check de dados KPI: o newgen produz 19×565 colunas, o legado standalone 19×532. Diferença de 33 colunas — **todas extras no newgen**: uA/uB/uc/U para emissões específicas (g/kWh, pct, ppm) de CO, CO2, NOx, THC, O2. Isso é **drift pre-existente** entre as 2 cópias de `nanum_pipeline_29.py` (em `legacy_monoliths/` há propagação de incerteza para emissões que a cópia raiz em `nanum-pipeline-28-main/` não tem). **Não vem do Passo 3a**. Sobre as 512 colunas comuns: `DataFrame.equals == True`. Ou seja, **zero regressão** introduzida pelo port.

## Pendências

- **Resolver o drift de 53 colunas entre as 2 cópias do monolito**: ou portar a propagação de incerteza de emissões específicas para a cópia raiz em `nanum-pipeline-28-main/`, ou aceitar que `legacy_monoliths/` é canonical. É assunto do Passo 3b — quando `build_final_table` for portado nativamente, a tabela passa a ser construída no newgen e a divergência deixa de existir.
- **Passo 3b — port nativo `build_final_table`** com uA/uB separados para métricas derivadas (η_th, BSFC, economia, Consumo_L_h, emissões g/kWh). Decisão `2026-04-25-derivadas-expor-uA-uB-separados.md` já cobre o contrato.
- **OneDrive sync**: nada a sincronizar na cópia operacional por enquanto — o port é 100% newgen-interno. Nenhuma mudança em `legacy_monoliths/` nesta sessão.
- **Consolidar helpers genéricos**: `_canon_name`, `_basename_parts`, `_find_first_col_by_substrings`, `_parse_time_series`, `_safe_name` são privados do subpacote `time_diagnostics/` hoje. Quando outra estação portada nativamente precisar deles (provavelmente `compute_trechos_stats`), promover para `runtime/_utils/` com port reference em docstrings.
