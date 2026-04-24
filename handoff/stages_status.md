# Painel de estações

Estado atual: 2026-04-24.

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
| Stages registry | 🟢 | `src/pipeline_newgen_rev1/runtime/stages/__init__.py` | 2026-04-24 — `STAGE_REGISTRY` + `STAGE_PIPELINE_ORDER`. |
| Runner (loop da linha) | 🟢 | `src/pipeline_newgen_rev1/runtime/runner.py` | 2026-04-24 — loop sobre o registry + 4 helpers core privados. |
| Tabela de âncoras legado | ⚪ existe | `src/pipeline_newgen_rev1/bridges/legacy_pipeline30.py` | Remove linha conforme cada estação é portada. |
| Cópia dos monolitos | 🟢 | `src/pipeline_newgen_rev1/legacy_monoliths/` | 2026-04-24 — 4 arquivos legados (29, 30, kibox_open_to_csv, pipeline29_config_backend). |
| Bridge runtime (janela de atendimento) | 🟢 scaffolding | `src/pipeline_newgen_rev1/bridges/legacy_runtime.py` | 2026-04-24 — lazy loader + 1ª estação bridge (`export_excel`). |

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
| Parse de metadados de sweep do nome do arquivo | `parse_sweep_metadata` | 🔴 | — | `nanum_pipeline_30.py::_parse_filename_sweep` | — |

## Fase 2 — Processamento (core comum + delta sweep)

| Estação | feature_key | Estado | newgen | Âncora legado | Última mudança |
|---|---|---|---|---|---|
| Diagnóstico de tempo | `run_time_diagnostics` | 🔴 | — | `nanum_pipeline_29.py::build_time_diagnostics` + `summarize_time_diagnostics` | — |
| Agregação por trechos e pontos | — | 🔴 | — | `nanum_pipeline_29.py::compute_trechos_stats` + `compute_ponto_stats` | — |
| Consulta de propriedades do combustível (LHV/densidade/custo) | — | 🔴 | — | `nanum_pipeline_29.py::load_fuel_properties_lookup` | — |
| Agregação KiBox por ponto | — | 🔴 | — | `nanum_pipeline_29.py::kibox_aggregate` | — |
| Regra de vazão de ar (MAF vs consumo+lambda) | — | 🔴 | — | `nanum_pipeline_29.py` (fluxo airflow) | — |
| Emissões específicas g/kWh | — | 🔴 | — | `nanum_pipeline_29.py` (fluxo emissões) | — |
| Eficiência volumétrica (ETA_V) | — | 🔴 | — | `nanum_pipeline_29.py` (fluxo ETA_V) | — |
| Economia vs diesel + cenários de máquinas | — | 🔴 | — | `nanum_pipeline_29.py` (fluxo economia) | — |
| Propagação de incertezas (uA/uB/uc/U) | — | 🔴 | — | `nanum_pipeline_29.py` (fluxo incertezas) | — |
| **Montagem da tabela final → `lv_kpis_clean.xlsx`** | `build_final_table` | 🟡 bridge | `bridges/legacy_runtime.py::BuildFinalTableBridgeStage` | `nanum_pipeline_29.py::build_final_table` | 2026-04-24 — Passo 2b |
| Sweep binning | `apply_sweep_binning` | 🔴 | — | `nanum_pipeline_30.py::_apply_runtime_sweep_binning` + `_cluster_sweep_bin_centers` | — |
| Seletor de duplicatas de sweep | `prompt_sweep_duplicate_selector` | 🔴 | — | `nanum_pipeline_30.py::prompt_sweep_duplicate_filter` + `_apply_sweep_duplicate_filter` | — |
| Filtro de pontos para plot (load mode) | — | 🟢 | `runtime/plot_point_filter.py` | `nanum_pipeline_29.py::prompt_plot_point_filter` | 2026-04-23 |

## Fase 3 — Plots

| Estação | feature_key | Estado | newgen | Âncora legado | Última mudança |
|---|---|---|---|---|---|
| Dispatcher de plots | — | 🔴 | — | `nanum_pipeline_29.py::make_plots_from_config_with_summary` | — |
| Plots unitários | `run_unitary_plots` | 🟡 bridge | `bridges/legacy_runtime.py::RunUnitaryPlotsBridgeStage` | `nanum_pipeline_29.py::make_plots_from_config_with_summary` | 2026-04-24 — Passo 2c (paridade 37/37 PNGs) |
| Plots compare (subida × descida) | `run_compare_plots` | 🔴 | — | `nanum_pipeline_29.py::iter_compare_plot_groups` | — |
| Plots compare_iteracoes | `run_compare_iteracoes` | 🔴 | — | `nanum_pipeline_29.py::_plot_compare_iteracoes_bl_vs_adtv` | — |
| Plots especiais de load (ethanol_equivalent, máquinas) | `run_special_load_plots` | 🔴 | — | `nanum_pipeline_30.py::_plot_ethanol_equivalent_*` + `_plot_machine_scenario_suite` | — |
| Plot_scope gating (`all`/`unitary`/`compare`/`none`) | — | 🟡 parcial | feature flags sim, CLI não | `nanum_pipeline_29.py::main` — `--plot-scope` | — |
| Reescrita de eixo para modo sweep | `rewrite_plot_axis_to_sweep` | 🔴 | — | `nanum_pipeline_30.py::_resolve_plot_x_request` + `_runtime_sweep_axis_token_for_col` | — |

## Fase 4 — Saída

| Estação | feature_key | Estado | newgen | Âncora legado | Última mudança |
|---|---|---|---|---|---|
| Export Excel consolidado (rounding + incertezas) | `export_excel` | 🟡 bridge | `bridges/legacy_runtime.py::ExportExcelBridgeStage` (ativa quando `build_final_table` upstream roda) | `nanum_pipeline_29.py::safe_to_excel` | 2026-04-24 — Passo 2b |
| Export `compare_iteracoes_metricas_incertezas.xlsx` | — | 🔴 | — | `nanum_pipeline_29.py::_plot_compare_iteracoes_bl_vs_adtv` (lado b) | — |

## Fase 5 — Superfície

| Estação | Estado | newgen | Âncora legado | Última mudança |
|---|---|---|---|---|
| GUI de configuração (PySide6, abas Defaults/Data Quality/Mappings/Instruments/Reporting/Plots/Compare/Fuel Properties/Variable Source/Sweep-Load) | 🟢 cópia preservada | `ui/legacy/pipeline29_config_gui.py` + `pipeline29_config_backend.py` | `pipeline29_config_gui.py` + `pipeline29_config_backend.py` | 2026-04-23 |
| Save & Run → executor migrado | 🟢 | ligação feita | exit code 1001 + `load_gui_state` | 2026-04-23 |
| CLI (`show-plan`, `discover-inputs`, `inspect-*`, `run-load-sweep`, `launch-config-gui`, `convert-open`, `scan-preflight`, `show-runtime-state`, `inspect-config`) | 🟢 básico | `cli.py` | — | 2026-04-23 |
| CLI flag `--plot-scope` | 🔴 | — | `nanum_pipeline_29.py` argparse | — |
| CLI flag `--compare-iter-pairs` | 🔴 | — | `nanum_pipeline_29.py` argparse | — |
| CLI flag `--config-source text\|excel\|auto` | 🟡 parcial | presente no `inspect-config` | `nanum_pipeline_29.py` argparse | — |
| Env vars (`PIPELINE29_USE_DEFAULT_RUNTIME_DIRS`, `PIPELINE29_SKIP_CONFIG_GUI_PROMPT`, `PIPELINE29_PLOT_SCOPE`, `PIPELINE29_COMPARE_ITER_PAIRS`) | 🔴 | — | `nanum_pipeline_29.py::main` | — |

## Como usar este painel

- Mudar o status de uma linha é obrigatório quando uma estação passa de 🔴 → 🟡 → 🟢.
- A coluna "Última mudança" aponta para a data da change mais recente em `handoff/changes/` que tocou essa estação.
- Uma nova estação (criada em runtime apartado) deve entrar aqui antes do primeiro commit.
