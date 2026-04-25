# 2026-04-25 — load-mode-completion

## O que mudou

- Port nativo de `run_compare_plots`: módulo `compare_plots.py` com 6 funções de agrupamento subida×descida + stage `RunComparePlotsStage`.
- Port nativo de `run_special_load_plots`: subpacote `special_load_plots/` com ethanol_equivalent (overlay 3 blends + ratio delta%) e machine_scenarios (6 PNGs por 3 máquinas) + stage `RunSpecialLoadPlotsStage`.
- CLI flags `--plot-scope` e `--compare-iter-pairs` no handler `run-load-sweep` com fallback para env vars (`PIPELINE29_PLOT_SCOPE`, `PIPELINE29_COMPARE_ITER_PAIRS`, `PIPELINE29_USE_DEFAULT_RUNTIME_DIRS`).
- Plot-scope gating no runner: constante `_PLOT_SCOPE_INCLUDE` com dual gating (feature flag + scope).
- `RuntimeContext` ganhou campos `plot_scope` e `compare_iter_pairs_override`.
- `compute_compare_iteracoes` aceita `pairs_override` via ctx para bypass de seleção interativa.
- Limpeza completa de bridges mortas: 4 classes (`BuildFinalTableBridgeStage`, `RunUnitaryPlotsBridgeStage`, `RunCompareIteracoesBridgeStage`, `ExportExcelBridgeStage`) e helpers órfãos removidos de `legacy_runtime.py`.
- 4 test files de bridge removidos (512 linhas de testes obsoletos).
- Registry atualizado: 15 stages total, `PLOTTING_STAGE_ORDER` com 5 entries.

## Por quê

O usuário pediu completude do load mode antes de atacar sweep. As duas últimas estações de plot (`run_compare_plots` e `run_special_load_plots`) eram as únicas 🔴 restantes para o modo load. O CLI precisava de `--plot-scope` e `--compare-iter-pairs` para paridade com o legado. As 4 bridge classes eram código morto — todos os ports nativos já as substituíam mas elas permaneciam no arquivo, gerando confusão.

Com este commit, **todas as estações do modo load estão 🟢 nativas**. O pipeline pode processar dados reais de ponta a ponta sem tocar no galpão antigo (exceto para features de sweep que continuam 🔴).

## Arquivos

### Novos (9):
- `src/pipeline_newgen_rev1/runtime/compare_plots.py` (novo)
- `src/pipeline_newgen_rev1/runtime/stages/run_compare_plots.py` (novo)
- `src/pipeline_newgen_rev1/runtime/special_load_plots/__init__.py` (novo)
- `src/pipeline_newgen_rev1/runtime/special_load_plots/ethanol_equivalent.py` (novo)
- `src/pipeline_newgen_rev1/runtime/special_load_plots/machine_scenarios.py` (novo)
- `src/pipeline_newgen_rev1/runtime/stages/run_special_load_plots.py` (novo)
- `tests/test_compare_plots.py` (novo)
- `tests/test_special_load_plots.py` (novo)
- `tests/test_plot_scope.py` (novo)

### Modificados (8):
- `src/pipeline_newgen_rev1/runtime/stages/__init__.py` (modificado — +2 imports, registry 15 stages)
- `src/pipeline_newgen_rev1/runtime/context.py` (modificado — +2 campos)
- `src/pipeline_newgen_rev1/runtime/runner.py` (modificado — +2 params, `_PLOT_SCOPE_INCLUDE`, dual gating)
- `src/pipeline_newgen_rev1/cli.py` (modificado — +2 args, env vars)
- `src/pipeline_newgen_rev1/runtime/stages/compute_compare_iteracoes.py` (modificado — pairs_override)
- `src/pipeline_newgen_rev1/runtime/compare_iteracoes/core.py` (modificado — pairs_override param)
- `src/pipeline_newgen_rev1/bridges/legacy_runtime.py` (modificado — 4 classes + helpers removidos)
- `src/pipeline_newgen_rev1/bridges/legacy_pipeline30.py` (modificado — anchors portadas comentadas)

### Removidos (4):
- `tests/test_bridge_build_final_table.py` (removido)
- `tests/test_bridge_compare_iteracoes.py` (removido)
- `tests/test_bridge_export_excel.py` (removido)
- `tests/test_bridge_unitary_plots.py` (removido)

## Validação

- `python -m unittest discover -s tests -p "test_*.py"` → 323 testes OK (era 295, +28 novos)
- Todos os 3 novos test files passam: `test_compare_plots.py` (12), `test_special_load_plots.py` (10), `test_plot_scope.py` (6)
- Testes existentes (`test_orchestrator`, `test_feature_flags`) atualizados para 15 stages

## Pendências

- `PIPELINE29_SKIP_CONFIG_GUI_PROMPT` env var não implementada no handler `launch-config-gui` (não é crítica para load mode).
- Sweep mode continua 🔴: `parse_sweep_metadata`, `apply_sweep_binning`, `prompt_sweep_duplicate_selector`, `rewrite_plot_axis_to_sweep`.
- Paridade byte-a-byte dos plots de compare e special_load ainda não validada contra baseline legado (requer dados reais de campanha com subida+descida).
