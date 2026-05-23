# HANDOFF_MASTER

Date: 2026-04-23
Project: `Pipeline_newgen_rev1`
Target repository: `https://github.com/Motterdude/Pipeline_Newgen`

## Objective
- start the migration from the legacy `pipeline29/pipeline30` codebase into a new repository;
- keep the current `pipeline29` stable and untouched;
- isolate the `pipeline30` `load/sweep` runtime into checkbox-driven features;
- create a documentation model that supports low-context editing with AI.

## What was created
- the new Git repository was cloned locally into:
  - `C:\Temp\np28_git_main_20260422\Pipeline_newgen_rev1`
- the first package scaffold now exists under:
  - `src/pipeline_newgen_rev1`
- a new VS Code workspace file exists:
  - `Pipeline_newgen_rev1.code-workspace`

## First technical decision
- the new generation should not start as another numbered monolith like `pipeline31.py`;
- instead, the migration starts by isolating the `pipeline30` `load/sweep` workflow into feature-flagged execution steps.

## Implemented modules
- `models.py`
  - shared data contracts for features and execution steps
- `bridges/legacy_pipeline30.py`
  - mapping from each new feature to the corresponding legacy anchor
- `workflows/load_sweep/feature_flags.py`
  - the source of truth for the new checkbox-driven workflow
- `workflows/load_sweep/state.py`
  - JSON persistence for feature state
- `workflows/load_sweep/orchestrator.py`
  - execution plan builder and summary helpers
- `ui/load_sweep_feature_dialog.py`
  - optional PySide6 checkbox dialog for feature selection
- `ui/runtime_preflight/*`
  - migrated runtime preflight scanner, prompts, and orchestration service
- `config/*`
  - migrated config adapter for text bundle loading, runtime state loading, and optional Excel bootstrap
- `adapters/open_to_csv.py`
  - migrated batch `.open -> .csv` adapter with saved converter path and pipeline naming
- `cli.py`
  - CLI entrypoint for showing the current plan, scanning preflight inputs, converting `.open`, and inspecting config/runtime state

## Operational checkpoint - 2026-04-23
- the operational working copy moved from the temporary clone to:
  - `C:\Users\sc61730\OneDrive - Stellantis\Pessoal\pipeline_newgen`
- the new repo now carries the runtime assets needed for operation:
  - `config/pipeline29_text`
  - `config/pipeline30_smoke_text`
  - `config/config_incertezas_rev3.xlsx`
  - `config/lhv.csv`
  - `config/rules_consumo.csv`
  - `config/presets/pipeline29_legacy_bundle.json`
- the preserved GUI now saves/loads presets from the repository instead of `%LOCALAPPDATA%`
- `Save & Run` now exits the GUI back into the migrated executor
- the migrated executor now includes:
  - runtime folder chooser
  - runtime preflight
  - plot point filter in `load` mode
  - summary artifact generation under `pipeline_newgen_runtime`

## Real-run debug result - 2026-04-23
- a real `Save & Run` was traced on:
  - `process_dir = E:\raw_pyton\raw_NANUM`
  - `out_dir = E:\out_Nanum_rev2`
- the first real run did execute, but most LabVIEW files failed with:
  - `expected <class 'openpyxl.styles.fills.Fill'>`
- root cause:
  - the migrated LabVIEW reader was using `openpyxl` only
  - the legacy `pipeline30` already had a safer Excel path that preferred `calamine`
- fix applied:
  - `python-calamine` installed
  - `src/pipeline_newgen_rev1/adapters/labview_reader.py` updated to prefer `calamine` and only fall back to `openpyxl`
- post-fix rerun on the same dataset produced:
  - `total_inputs = 133`
  - `labview_files = 76`
  - `kibox_files = 19`
  - `errors = []`
- validation artifact:
  - `E:\out_Nanum_rev2\pipeline_newgen_runtime\newgen_runtime_summary.json`

## New rule for the load/sweep workflow
- `load` mode defaults must preserve the `pipeline29` behavior as much as possible;
- sweep-only features are disabled by default in `load` mode:
  - `show_runtime_preflight`
  - `convert_missing_open_files`
  - `parse_sweep_metadata`
  - `apply_sweep_binning`
  - `prompt_sweep_duplicate_selector`
  - `rewrite_plot_axis_to_sweep`
- compare and load-centric plots remain enabled by default in `load` mode.

## New low-context documentation format
- full narrative handoff stays in `handoff/HANDOFF_MASTER.md`
- operational low-context notes now live in:
  - `handoff/function_cards/*.fnctx.md`
- format reference:
  - `handoff/FUNCTION_CONTEXT_FORMAT.md`

## Validation expected for this slice
- `python -m unittest discover -s tests -p "test_*.py"`
- `Get-ChildItem -Recurse -Filter *.py | ForEach-Object { python -m py_compile $_.FullName }`
- `$env:PYTHONPATH='src'; python -m pipeline_newgen_rev1.cli show-plan --mode load`
- `$env:PYTHONPATH='src'; python -m pipeline_newgen_rev1.cli show-plan --mode sweep`
- `$env:PYTHONPATH='src'; python -m pipeline_newgen_rev1.cli scan-preflight --process-dir <dir> --json`
- `$env:PYTHONPATH='src'; python -m pipeline_newgen_rev1.cli convert-open <file-or-dir> --converter <path> --json`
- `$env:PYTHONPATH='src'; python -m pipeline_newgen_rev1.cli inspect-config --config-source text --text-config-dir <dir> --json`
- `$env:PYTHONPATH='src'; python -m pipeline_newgen_rev1.cli show-runtime-state --json`

## Validation status now
- `52` tests passing in the operational repository
- `py_compile` passing across the repository
- real run validated on `E:\raw_pyton\raw_NANUM`

## Next step (2026-04-23, já concluído)
- move from the current summary-oriented migrated executor into full processing parity with the legacy runtime:
  - real KPI/output generation
  - final plot generation
  - compare/compare_iteracoes outputs
  - sweep binning and duplicate filtering wired into final outputs

---

## Sessão 2026-05-23 — Sistema de Exclusão de Pontos, Preview Plot e Pipeline de Combustão

### Contexto da campanha

A campanha em curso é a **Rev2 combustão do Nanum**: combustível D85B15 (diesel 85% + biodiesel 15%), com 12 iterações (3 BL × subida/descida + 3 ADTV × subida/descida). Os arquivos brutos originais (pós-correção do injetor) foram organizados em `raw_nanum_post_injector_fix_renamed_combustion/` com 222 xlsx + 223 .open pareados.

Descobrimos que a série `Subindo_Aditivado_1` (→ label "ADTV Sub 1") tinha um defeito instrumental: vazão de ar (`Air_g_s`) sistematicamente baixa em todos os pontos, o que invalidava os KPIs derivados dessa iteração. A decisão foi excluir a série do pipeline antes do cálculo de médias.

### O que foi feito nesta sessão

#### 1. Sistema de Exclusão de Pontos — Preview Plot → Pipeline

**Objetivo:** criar um ciclo completo de exclusão: identificar pontos ruins visualmente no Preview Plot → exportar a lista → re-rodar o pipeline com os pontos excluídos → comparar os resultados visualmente.

**Implementado:**
- `point_exclusion.py`: chave `ExclusionKey` passou a incluir `y_col` (sem mais bleeding entre plots). Exclusões de série (`[SERIE]`) usam `y_col="*"` (global). Migração automática de JSON v1→v2. Métodos `remove_all()` e `active_keys_for_ycol()`.
- `preview_plot_tab.py`: botões "Restore All", "Export...", fix de row-shift no diálogo de exclusões (rebuilding da tabela em vez de `removeRow(i)`), render imediato ao restaurar.
- `exclusion_runner.py`: novo módulo em `runtime/` que carrega uma exclusion list JSON e aplica o filtro no DataFrame `ponto` por `(BaseName, Load_kW)`.
- `RuntimeContext.exclusion_list_path`: novo campo opcional que ativa o filtro de exclusão na stage `ComputeTrechosPontoStage`.
- `runner.py` / `run_load_sweep`: parâmetro `exclusion_list_path` propagado do GUI ao contexto.
- `Pipeline30SweepHelperDialog`: seletor de exclusion list com combo (arquivos disponíveis no config dir), botão "Ver lista..." (preview read-only) e botão "Browse...". Persiste em `pipeline30_runtime_settings`.
- `plot_point_filter.py` (`_prompt_plot_point_filter_catalog_via_qt`): ao clicar em "Gerar gráficos", abre popup "Tem exclusion list? [Sim/Não]". Sim → file picker → preview da lista → aplica. Não → roda sem exclusões. Path propagado via variável de módulo `_runtime_exclusion_list_path`, lida pelo runner imediatamente após o dialog.

**Resultado do pipeline com exclusion list:**
- `out_nanum_post_injector_fix_renamed_combustion_excl_list/lv_kpis_clean.xlsx`: **203 linhas** (222 − 19 = 203). ADTV Sub 1 ausente — ✓ confirmado.
- `out_nanum_post_injector_fix_renamed_combustion/lv_kpis_clean.xlsx`: **222 linhas** (referência pré-exclusão). ADTV Sub 1 presente.

#### 2. Preview Plot — Toggle Raw / Excl

**Objetivo:** poder alternar instantaneamente entre o arquivo original (raw, 222 linhas) e o arquivo pós-exclusão (excl, 203 linhas) para comparação visual.

**Implementado:**
- Segunda barra de dados abaixo da barra principal: labels "Raw / Excl" com Browse, Reload e combo "Ativo: [raw | excl]".
- Novos campos internos: `_raw_df`, `_raw_path`, `_excl_df`, `_excl_path`, `_active_source`.
- `_get_effective_df()` reescrito: raw_df → excl_df → loaded_df → fallback.
- Session persistence: `data_source.raw_path`, `data_source.excl_path`, `data_source.active_source`.
- `_browse_data_file` (Browse antigo): popula automaticamente `_raw_df` se ele ainda for None, para que o workflow natural "Browse → toggle" funcione sem precisar usar Browse Raw explicitamente.
- Modo raw bypassa o `ExclusionStore` (`apply_exclusions` não é chamado quando `active_source == "raw"`). Raw = dados originais, sem nenhum filtro de preview.

**Resultado:** toggle raw=222 linhas com ADTV Sub 1 visível, excl=203 linhas sem ADTV Sub 1.

#### 3. Compare mode unificado no lv_kpis_clean.xlsx

**Objetivo:** eliminar o Browse separado para carregar o `compare_iteracoes_metricas_incertezas.xlsx`.

**Implementado:**
- `compute_compare_iteracoes.py`: após salvar o arquivo de compare separado, appenda o mesmo DataFrame como sheet `"compare"` no `lv_kpis_clean.xlsx` via `ExcelWriter(mode="a", if_sheet_exists="replace")`.
- `load_data_from_file()`: ao carregar um xlsx, tenta ler sheet `"compare"`. Se presente com colunas `Metrica`/`Comparacao`, popula `_compare_df` automaticamente — sem Browse adicional.
- Backward compatible: se a aba não existe (arquivo gerado antes desta feature), comporta-se como antes.

**Resultado:** carregar `lv_kpis_clean.xlsx` do próximo run ativa compare mode automaticamente.

#### 4. Robustez do workspace do Preview Plot

Quatro bugs corrigidos após investigação com subagentes:

| Bug | Causa | Fix |
|-----|-------|-----|
| **Workspace merge** | `dict.update()` em `_on_workspace_double_click` contaminava novo workspace com y_scales/series_styles do anterior | Full replace: reset da `_session` ao template antes de carregar |
| **ExclusionStore bleeding** | Singleton do ExclusionStore persiste entre troca de arquivo | Toggle "Aplicar excl." removido; substituído pelo toggle Raw/Excl |
| **Browse não limpa styles** | `_browse_data_file` não resetava `series_style_overrides` | Reset de `series_styles`, `series_style_overrides`, `draft_overrides` ao Browse |
| **Stale `_loaded_df`** | `_restore_session_to_ui` não limpava `_loaded_df` antes de recarregar | Reset explícito de `_loaded_df = None` no início de `_restore_session_to_ui` |

#### 5. Workspace list e outros fixes de UI

- `_refresh_workspace_list`: glob `*.json` com filtro `version==2 + data_source` em vez de `preview_workspace*.json`. Encontra qualquer workspace salvo com nome livre (ex: `NANUM_W_COMBUSTION.json`).
- `_open_exclusions_review`: rebuild da tabela a cada restore, render imediato, botão Restore All com confirmação.
- Crash "no attribute `_presets_file_path`": substituído por `_workspace_file_path()` em `_get_exclusion_store`.
- Thumbnails: `_invalidate_thumb_cache` reseta `_thumb_items_snapshot` para forçar rebuild ao trocar dataset.

#### 6. Organização dos arquivos raw e open_to_csv

- Skill `/organize-raw-files` organizou 222 xlsx + 223 .open em `raw_nanum_post_injector_fix_renamed_combustion/`.
- Fix duplicação de sufixo `_i`: `open_to_csv.py` detectava `.open` → adicionava `_i` mesmo quando nome já tinha `_i`.
- Fix detecção do `OpenToCSV.exe`: limpa path stale se arquivo não existe mais em disco.
- ETA na barra de status durante conversão batch.

### Sanity check das pastas raw

| Subpasta | xlsx | .open | Status |
|---|---|---|---|
| Descendo_Baseline_2 | 15 | 15 | 4 pares ausentes (0–7.5 kW) |
| Descendo_Baseline_3 | 18 | 18 | 0 kW ausente |
| Subindo_Baseline_2 | 18 | 19 | xlsx 35 kW ausente (.open existe) |
| Outras 9 | 19 | 19 | ✓ completo |

### Estado dos arquivos de saída

| Arquivo | Linhas | ADTV Sub 1 | Uso |
|---|---|---|---|
| `out_.../lv_kpis_clean.xlsx` (14:08) | 222 | ✓ presente | Raw — referência pré-exclusão |
| `out_excl.../lv_kpis_clean.xlsx` (15:27) | 203 | ✗ ausente | Excl — para cálculos e comparações |

### Arquivos novos/modificados de código

| Arquivo | Tipo | Mudança principal |
|---|---|---|
| `ui/preview_plot_tab.py` | modificado | Toggle Raw/Excl, compare auto-detect, workspace robustness, exclusão bugs |
| `ui/point_exclusion.py` | modificado | ExclusionKey com y_col, remove_all, active_keys_for_ycol |
| `ui/legacy/pipeline29_config_gui.py` | modificado | Seletor de exclusion list no Sweep Helper, exclusion_list_path para run |
| `runtime/exclusion_runner.py` | **novo** | Carrega JSON de exclusão e filtra DataFrame ponto por (BaseName, Load_kW) |
| `runtime/context.py` | modificado | Campo `exclusion_list_path: Optional[Path]` |
| `runtime/runner.py` | modificado | Kwarg `exclusion_list_path` + leitura do módulo plot_point_filter |
| `runtime/stages/compute_trechos_ponto.py` | modificado | Aplica exclusion_list_path após compute_ponto_stats |
| `runtime/stages/compute_compare_iteracoes.py` | modificado | Embeds sheet "compare" em lv_kpis_clean.xlsx |
| `runtime/plot_point_filter.py` | modificado | Popup exclusion list no "Gerar gráficos", variável de módulo `_runtime_exclusion_list_path` |
| `adapters/open_to_csv.py` | modificado | Fix sufixo _i duplo, fix stale settings, ETA |

### Validação final

- `python -m unittest discover -s tests -p "test_*.py"` → 446 testes, 10 erros pré-existentes (bridges legacy). Sem novas regressões.
- `python -m py_compile` → OK em todos os arquivos modificados.
- Validação headless com dados reais: toggle raw=222/excl=203, ADTV Sub 1 presente/ausente corretamente, Air_kg_h 222/203 pontos.
- ExcelWriter append write+read roundtrip: Sheet1 intacta, compare sheet com schema correto.

### Próximos passos sugeridos

1. Rodar próximo `Save & Run` com `exclusion_list_1.json` selecionada no Sweep Helper para gerar `lv_kpis_clean.xlsx` com a sheet "compare" embutida.
2. Abrir o `lv_kpis_clean.xlsx` novo no Preview Plot — compare mode deve ativar automaticamente sem Browse extra.
3. Usar o toggle raw/excl para comparar todas as métricas com e sem ADTV Sub 1.
4. Avaliar se `Descendo_Baseline_2` (faltam 0–7.5 kW) e `Subindo_Baseline_2` (xlsx 35 kW ausente) precisam de medições complementares ou serão tratados como dados incompletos na campanha.
