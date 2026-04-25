# 2026-04-25 — sweep-mode-port

## O que mudou

- Port completo das 4 estações de sweep mode: `parse_sweep_metadata`, `apply_sweep_binning`, `prompt_sweep_duplicate_selector`, `rewrite_plot_axis_to_sweep`.
- 3 módulos core novos: `sweep_binning.py` (~160 linhas, clustering greedy single-pass), `sweep_duplicate_selector.py` (~300 linhas, catalog + dialog PySide6 + injectable prompt), `sweep_axis.py` (~190 linhas, resolução de eixo + reescrita filename/title).
- 4 stages novas no registry (19 total). `PROCESSING_STAGE_ORDER` agora com 11 estações.
- Integração com dispatch de plots: `config_parsing.py` e `dispatch.py` recebem sweep kwargs; 4 `_dispatch_*` helpers propagam resolução de eixo, reescrita de filename/title, e anulação de fixed_x quando sweep override ativo.
- `run_unitary_plots.py` e `run_compare_plots.py` passam sweep fields do `RuntimeContext` ao dispatch.
- `LEGACY_PIPELINE30_ANCHORS` agora é `{}` — zero bridges pendentes.
- 6 campos sweep adicionados ao `RuntimeContext` (sweep_active, sweep_effective_x_col, sweep_axis_label, sweep_axis_token, sweep_selected_basenames, sweep_dup_prompt_func).
- 4 constantes adicionadas a `constants.py` (SWEEP_KEY_COL, SWEEP_DISPLAY_LABEL_COL, SWEEP_BIN_VALUE_COL, SWEEP_BIN_LABEL_COL).
- `runner.py` aceita `_sweep_dup_prompt_func` para injeção headless.

## Por quê

Load mode estava 100% portado (15 stages, 323 testes, zero bridges). As 4 estações de sweep eram as últimas pendentes (todas 🔴). O sweep mode precisa de binning (agrupar valores próximos de lambda/AFR/EGR em bins estáveis), seleção interativa de duplicatas (quando há mais de um arquivo por fuel×sweep_value), e reescrita transparente de eixos (plots pedem "Load_kW" mas em sweep mode o eixo X deve ser "Lambda" ou "AFR").

Com esta sessão, o pipeline inteiro — load + sweep — roda 100% sobre código newgen, sem nenhuma chamada ao galpão antigo.

## Arquivos

### Novos (7 módulos + 4 testes)
- `src/pipeline_newgen_rev1/runtime/sweep_binning.py` (novo)
- `src/pipeline_newgen_rev1/runtime/sweep_duplicate_selector.py` (novo)
- `src/pipeline_newgen_rev1/runtime/sweep_axis.py` (novo)
- `src/pipeline_newgen_rev1/runtime/stages/parse_sweep_metadata.py` (novo)
- `src/pipeline_newgen_rev1/runtime/stages/apply_sweep_binning.py` (novo)
- `src/pipeline_newgen_rev1/runtime/stages/prompt_sweep_duplicate_selector.py` (novo)
- `src/pipeline_newgen_rev1/runtime/stages/rewrite_plot_axis_to_sweep.py` (novo)
- `tests/test_sweep_binning.py` (novo — 15 testes)
- `tests/test_sweep_duplicate_selector.py` (novo — 8 testes)
- `tests/test_sweep_axis.py` (novo — 12 testes)
- `tests/test_sweep_stages.py` (novo — 11 testes)

### Modificados (9)
- `src/pipeline_newgen_rev1/ui/runtime_preflight/constants.py` — +4 constantes
- `src/pipeline_newgen_rev1/runtime/context.py` — +6 campos sweep
- `src/pipeline_newgen_rev1/runtime/runner.py` — sweep_dup_prompt_func param
- `src/pipeline_newgen_rev1/runtime/stages/__init__.py` — +4 imports, registry 19
- `src/pipeline_newgen_rev1/runtime/unitary_plots/config_parsing.py` — sweep kwargs
- `src/pipeline_newgen_rev1/runtime/unitary_plots/dispatch.py` — sweep kwargs nos 4 dispatchers
- `src/pipeline_newgen_rev1/runtime/stages/run_unitary_plots.py` — passa sweep ctx
- `src/pipeline_newgen_rev1/runtime/stages/run_compare_plots.py` — passa sweep ctx
- `src/pipeline_newgen_rev1/bridges/legacy_pipeline30.py` — anchors todas comentadas

### Testes atualizados (2)
- `tests/test_compare_plots.py` — 19 stages (era 15)
- `tests/test_unitary_plots.py` — sweep fields no mock ctx

## Validação

- `python -m unittest discover -s tests -p "test_*.py"` → 382 testes OK (+59)
- `py_compile` de todos os arquivos modificados → OK
- Feature-flag gating: em load mode, 4 sweep stages desabilitadas; em sweep mode, habilitadas
- `LEGACY_PIPELINE30_ANCHORS` = `{}` (vazio)

## Pendências

- Smoke test end-to-end com dados reais de sweep (raw_NANUM contém campanhas de sweep?) — não testado nesta sessão
- Dialog PySide6 (`_SweepDuplicateSelectorDialog`) não testado visualmente — apenas via injectable prompt_func
- `convert_missing_open_files` continua opt-in e desabilitado por default (decisão deliberada)
