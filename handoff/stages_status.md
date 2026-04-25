# Painel de estações

Estado atual: 2026-04-25 (atualizado após sweep mode port — 19 stages, 0 bridges pendentes).

Legenda:
- 🟢 **Portada** — estação implementada dentro do pacote novo, sem dependência do galpão antigo.
- 🟡 **Bridge** — estação opera via `bridges/legacy_runtime.py` chamando o monolito em `legacy_monoliths/`. Funciona end-to-end mas ainda depende do código legado.
- 🔴 **Não iniciada** — estação ainda 100% no galpão antigo; newgen não produz a saída correspondente.
- ⚪ **Não é estação** — infraestrutura (esteira, plano, registry). Listada à parte.

## Infraestrutura (a esteira e o plano da linha)

| Peça | Estado | Arquivo newgen | Observação |
|---|---|---|---|
| `RuntimeContext` (esteira) | 🟢 | `src/pipeline_newgen_rev1/runtime/context.py` | 2026-04-24 — Passo 1 esteira. |
| Plano da linha (`orchestrator`) | 🟢 | `src/pipeline_newgen_rev1/workflows/load_sweep/orchestrator.py` | 2026-04-24 — agora é consultado pelo `SyncRuntimeDirsStage` via `merge_feature_selection`. |
| Stages registry | 🟢 | `src/pipeline_newgen_rev1/runtime/stages/__init__.py` | 2026-04-25 — 3 tuplas (CONFIG/PROCESSING/PLOTTING) + 19 stages (4 sweep). |
| Runner (loop da linha) | 🟢 | `src/pipeline_newgen_rev1/runtime/runner.py` | 2026-04-25 — 3 loops + feature-flag gating + plot-scope gating. |
| Tabela de âncoras legado | ⚪ vazio | `src/pipeline_newgen_rev1/bridges/legacy_pipeline30.py` | 2026-04-25 — `LEGACY_PIPELINE30_ANCHORS` vazio (todas portadas). |
| Cópia dos monolitos | 🟢 | `src/pipeline_newgen_rev1/legacy_monoliths/` | 2026-04-24 — 4 arquivos legados (29, 30, kibox_open_to_csv, pipeline29_config_backend). |
| Bridge runtime (janela de atendimento) | 🟢 limpo | `src/pipeline_newgen_rev1/bridges/legacy_runtime.py` | 2026-04-25 — 4 bridge classes removidas; sobram apenas lazy loaders. |

## Fase 1 — Entrada

| Estação | feature_key | Estado | newgen | Âncora legado | Última mudança |
|---|---|---|---|---|---|
| Recepção de receita (config bundle TOML/Excel) | `load_text_config` | 🟢 | `config/adapter.py` | `nanum_pipeline_29.py::load_pipeline29_config_bundle` | 2026-04-23 — setup inicial |
| Escolha de `RAW_INPUT_DIR` e `OUT_DIR` | `sync_runtime_dirs` | 🟢 | `runtime/runtime_dirs.py` | `nanum_pipeline_29.py::_choose_runtime_dirs` | 2026-04-23 |
| Preflight (inventário + detecção de sweep + `.open`) | `show_runtime_preflight` | 🟢 | `ui/runtime_preflight/*` | `nanum_pipeline_30.py::_choose_runtime_preflight` | 2026-04-23 |
| Conversão `.open -> _i.csv` | `convert_missing_open_files` | 🟢 | `adapters/open_to_csv.py` | `kibox_open_to_csv.py::export_open_file` | 2026-04-23 |
| Discovery (classifica LV/MoTeC/KiBox + metadados) | — | 🟢 | `adapters/input_discovery.py` | `nanum_pipeline_29.py::parse_meta` | 2026-04-23 |
| Leitura LabVIEW (`calamine` → `openpyxl`) | — | 🟢 | `adapters/labview_reader.py` | `nanum_pipeline_29.py::read_labview_xlsx` | 2026-04-23 — fix calamine |
| Leitura MoTeC | — | 🟢 | `adapters/motec_reader.py` | `nanum_pipeline_29.py::read_motec_csv` | 2026-04-23 |
| Leitura KiBox | — | 🟢 | `adapters/kibox_reader.py` | `nanum_pipeline_29.py::read_kibox_csv_robust` | 2026-04-23 |
| Parse de metadados de sweep do nome do arquivo | `parse_sweep_metadata` | 🟢 | `runtime/stages/parse_sweep_metadata.py` | `nanum_pipeline_30.py::_parse_filename_sweep` | 2026-04-25 — port sweep mode |

## Fase 2 — Processamento (core comum + delta sweep)

| Estação | feature_key | Estado | newgen | Âncora legado | Última mudança |
|---|---|---|---|---|---|
| Diagnóstico de tempo (compute + xlsx) | `run_time_diagnostics` | 🟢 | `runtime/time_diagnostics/` + `runtime/stages/run_time_diagnostics.py` | `nanum_pipeline_29.py::build_time_diagnostics` + `summarize_time_diagnostics` | 2026-04-25 — 3 fases: compute only, sem PNGs |
| Diagnóstico de tempo (PNGs) | `plot_time_diagnostics` | 🟢 | `runtime/stages/plot_time_diagnostics.py` | (extraído de run_time_diagnostics) | 2026-04-25 — split para fase PLOTTING |
| Agregação por trechos e pontos | `compute_trechos_ponto` | 🟢 | `runtime/trechos_ponto/` + `runtime/stages/compute_trechos_ponto.py` | `nanum_pipeline_29.py::compute_trechos_stats` + `compute_ponto_stats` | 2026-04-24 — Passo 3b.2 (port nativo) |
| Consulta de propriedades do combustível (LHV/densidade/custo) | `prepare_upstream_frames` | 🟢 | `runtime/fuel_properties.py` + `runtime/stages/prepare_upstream_frames.py` | `nanum_pipeline_29.py::load_fuel_properties_lookup` | 2026-04-24 — Passo 3b.3 (port nativo) |
| Agregação KiBox por ponto | `prepare_upstream_frames` | 🟢 | `runtime/stages/prepare_upstream_frames.py` | `nanum_pipeline_29.py::kibox_aggregate` | 2026-04-24 — Passo 3b.3 (port nativo) |
| Regra de vazão de ar (MAF vs consumo+lambda) | — | 🟢 | `runtime/final_table/_airflow.py` | `nanum_pipeline_29.py` (fluxo airflow) | 2026-04-24 — port build_final_table |
| Emissões específicas g/kWh | — | 🟢 | `runtime/final_table/_emissions.py` | `nanum_pipeline_29.py` (fluxo emissões) | 2026-04-24 — port build_final_table |
| Eficiência volumétrica (ETA_V) | — | 🟢 | `runtime/final_table/_volumetric_efficiency.py` | `nanum_pipeline_29.py` (fluxo ETA_V) | 2026-04-24 — port build_final_table |
| Economia vs diesel + cenários de máquinas | — | 🟢 | `runtime/final_table/_diesel_cost_delta.py` + `_machine_scenarios.py` | `nanum_pipeline_29.py` (fluxo economia) | 2026-04-24 — port build_final_table |
| Propagação de incertezas (uA/uB/uc/U) | — | 🟢 | `runtime/final_table/_uncertainty_instruments.py` | `nanum_pipeline_29.py` (fluxo incertezas) | 2026-04-24 — port build_final_table |
| **Montagem da tabela final → `lv_kpis_clean.xlsx`** | `build_final_table` | 🟢 | `runtime/final_table/core.py` + `runtime/stages/build_final_table.py` | `nanum_pipeline_29.py::build_final_table` | 2026-04-24 — port nativo |
| Audit layer de incerteza (uB_res, uB_acc, %uA_contrib) | `enrich_final_table_audit` | 🟢 | `runtime/uncertainty_audit/` + `runtime/stages/enrich_final_table_audit.py` | — (nativa) | 2026-04-25 — Passo 3b.1 |
| Sweep binning | `apply_sweep_binning` | 🟢 | `runtime/sweep_binning.py` + `runtime/stages/apply_sweep_binning.py` | `nanum_pipeline_30.py::_apply_runtime_sweep_binning` + `_cluster_sweep_bin_centers` | 2026-04-25 — port sweep mode |
| Seletor de duplicatas de sweep | `prompt_sweep_duplicate_selector` | 🟢 | `runtime/sweep_duplicate_selector.py` + `runtime/stages/prompt_sweep_duplicate_selector.py` | `nanum_pipeline_30.py::prompt_sweep_duplicate_filter` + `_apply_sweep_duplicate_filter` | 2026-04-25 — port sweep mode |
| Filtro de pontos para plot (load mode) | — | 🟢 | `runtime/plot_point_filter.py` | `nanum_pipeline_29.py::prompt_plot_point_filter` | 2026-04-23 |

## Fase 3 — Plots

| Estação | feature_key | Estado | newgen | Âncora legado | Última mudança |
|---|---|---|---|---|---|
| Dispatcher de plots | — | 🟢 | `runtime/unitary_plots/dispatch.py` | `nanum_pipeline_29.py::make_plots_from_config_with_summary` | 2026-04-24 — port nativo |
| Plots unitários | `run_unitary_plots` | 🟢 | `runtime/unitary_plots/` + `runtime/stages/run_unitary_plots.py` | `nanum_pipeline_29.py::make_plots_from_config_with_summary` | 2026-04-24 — port nativo (subpacote 5 módulos) |
| Plots compare (subida × descida) | `run_compare_plots` | 🟢 | `runtime/compare_plots.py` + `runtime/stages/run_compare_plots.py` | `nanum_pipeline_29.py::iter_compare_plot_groups` | 2026-04-25 — port nativo |
| Compute compare_iteracoes (deltas + incertezas + xlsx) | `compute_compare_iteracoes` | 🟢 | `runtime/compare_iteracoes/` + `runtime/stages/compute_compare_iteracoes.py` | `nanum_pipeline_29.py::_plot_compare_iteracoes_bl_vs_adtv` (parte dados) | 2026-04-25 — port nativo (3 fases) |
| Plot compare_iteracoes (PNGs absolutos + delta) | `plot_compare_iteracoes` | 🟢 | `runtime/compare_iteracoes/plot_*.py` + `runtime/stages/plot_compare_iteracoes.py` | `nanum_pipeline_29.py::_plot_compare_iteracoes_bl_vs_adtv` (parte plot) | 2026-04-25 — port nativo (3 fases) |
| Plots especiais de load (ethanol_equivalent, máquinas) | `run_special_load_plots` | 🟢 | `runtime/special_load_plots/` + `runtime/stages/run_special_load_plots.py` | `nanum_pipeline_30.py::_plot_ethanol_equivalent_*` + `_plot_machine_scenario_suite` | 2026-04-25 — port nativo |
| Plot_scope gating (`all`/`unitary`/`compare`/`none`) | — | 🟢 | `runner.py` (`_PLOT_SCOPE_INCLUDE`) + `cli.py` (`--plot-scope`) | `nanum_pipeline_29.py::main` — `--plot-scope` | 2026-04-25 — CLI + runner |
| Reescrita de eixo para modo sweep | `rewrite_plot_axis_to_sweep` | 🟢 | `runtime/sweep_axis.py` + `runtime/stages/rewrite_plot_axis_to_sweep.py` | `nanum_pipeline_30.py::_resolve_plot_x_request` + `_runtime_sweep_axis_token_for_col` | 2026-04-25 — port sweep mode |

## Fase 4 — Saída

| Estação | feature_key | Estado | newgen | Âncora legado | Última mudança |
|---|---|---|---|---|---|
| Export Excel consolidado (rounding + incertezas) | `export_excel` | 🟢 | `runtime/stages/export_excel.py` | `nanum_pipeline_29.py::safe_to_excel` | 2026-04-24 — port nativo |
| Export `compare_iteracoes_metricas_incertezas.xlsx` | — | 🟢 | `runtime/stages/compute_compare_iteracoes.py` (xlsx export) | `nanum_pipeline_29.py::_plot_compare_iteracoes_bl_vs_adtv` (lado b) | 2026-04-25 — incluso no compute stage |

## Fase 5 — Superfície

| Estação | Estado | newgen | Âncora legado | Última mudança |
|---|---|---|---|---|
| GUI de configuração (PySide6, abas Defaults/Data Quality/Mappings/Instruments/Reporting/Plots/Compare/Fuel Properties/Variable Source/Sweep-Load) | 🟢 cópia preservada | `ui/legacy/pipeline29_config_gui.py` + `pipeline29_config_backend.py` | `pipeline29_config_gui.py` + `pipeline29_config_backend.py` | 2026-04-23 |
| Save & Run → executor migrado | 🟢 | ligação feita | exit code 1001 + `load_gui_state` | 2026-04-23 |
| CLI (`show-plan`, `discover-inputs`, `inspect-*`, `run-load-sweep`, `launch-config-gui`, `convert-open`, `scan-preflight`, `show-runtime-state`, `inspect-config`) | 🟢 básico | `cli.py` | — | 2026-04-23 |
| CLI flag `--plot-scope` | 🟢 | `cli.py` + `runner.py` | `nanum_pipeline_29.py` argparse | 2026-04-25 |
| CLI flag `--compare-iter-pairs` | 🟢 | `cli.py` + `runner.py` + `compare_iteracoes/core.py` | `nanum_pipeline_29.py` argparse | 2026-04-25 |
| CLI flag `--config-source text\|excel\|auto` | 🟡 parcial | presente no `inspect-config` | `nanum_pipeline_29.py` argparse | — |
| Env vars (`PIPELINE29_USE_DEFAULT_RUNTIME_DIRS`, `PIPELINE29_PLOT_SCOPE`, `PIPELINE29_COMPARE_ITER_PAIRS`) | 🟢 | `cli.py` handler de `run-load-sweep` | `nanum_pipeline_29.py::main` | 2026-04-25 |

## Como usar este painel

- Mudar o status de uma linha é obrigatório quando uma estação passa de 🔴 → 🟡 → 🟢.
- A coluna "Última mudança" aponta para a data da change mais recente em `handoff/changes/` que tocou essa estação.
- Uma nova estação (criada em runtime apartado) deve entrar aqui antes do primeiro commit.
