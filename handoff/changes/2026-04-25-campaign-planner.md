# 2026-04-25 — campaign-planner

## O que mudou

- Novo módulo `runtime/campaign_scan.py` (~177 linhas): scanner automático de estrutura experimental. `CampaignCatalog` (dataclass frozen) com `fuel_labels`, `load_points`, `directions`, `campaigns`, `iteration_mode`, contagens por fuel/campanha/direção, `total_files`. Funções `scan_campaign_structure()` e `default_comparison_pairs()`.
- Nova stage `stages/scan_campaign_structure.py`: roda em PROCESSING, popula `ctx.campaign_catalog`.
- Nova FeatureSpec `scan_campaign_structure` em `workflows/load_sweep/feature_flags.py`.
- Generalização do subpacote `compare_iteracoes/` para aceitar `CampaignCatalog`:
  - `specs.py`: `build_series_meta_from_catalog()` — gera meta dinâmico por fuel label ou fallback legado.
  - `prepare.py`: `fuel_label_from_row()` + `_assign_group_and_filter()` — atribui grupo por fuel_label (mestrado) ou campanha (Stellantis).
  - `series.py`: `build_series_frames_dynamic()` — delega para legado (direction) ou cria frames por fuel label.
  - `core.py`: `compute_compare_iteracoes()` aceita `catalog`, usa `group_cols` dinâmicos, gera pares sensatos.
  - `__init__.py`: exporta `build_series_meta_from_catalog`.
- `stages/compute_compare_iteracoes.py`: passa `catalog=ctx.campaign_catalog`.
- Nova aba GUI `ui/campaign_planner_tab.py` (~321 linhas): `CampaignPlannerTab` com scan automático, checkboxes de grupos, pares de comparação (dropdowns), seletor de agregação, famílias de plots.
- `ui/legacy/pipeline29_config_gui.py`: aba "Compare" (4 checkboxes fixos) substituída pela aba "Campanha" com `CampaignPlannerTab`. Aliases de compatibilidade preservados.
- `runtime/compare_plots.py`: `iter_compare_plot_groups()` flexibilizado — não exige mais subida+descida; aceita 2+ séries distintas.
- `runtime/context.py`: +1 campo `campaign_catalog: Optional[CampaignCatalog] = None`.
- `stages/__init__.py`: `scan_campaign_structure` registrada em `PROCESSING_STAGE_ORDER`.
- `ui/runtime_preflight/__init__.py`: imports de `.scan` e `.service` mudados para lazy via `__getattr__` (fix de import circular).

## Por quê

O pipeline assumia hardcoded que os dados tinham estrutura Stellantis (baseline/aditivado × subida/descida). Dados do mestrado do usuário têm composições de combustível (E94H6, E75H25, E65H35, D85B15) na mesma pasta, sem subida/descida. O sistema precisava:

1. Detectar automaticamente a estrutura dos dados (fuel-based vs direction-based).
2. Deixar o usuário escolher quais grupos incluir e quais pares comparar.
3. Gerar deltas entre pares de combustíveis, não só entre baseline e aditivado.

A implementação seguiu o plano aprovado de 4 sessões: scanner → generalização compare_iteracoes → GUI → polish.

## Arquivos

- `src/pipeline_newgen_rev1/runtime/campaign_scan.py` (novo)
- `src/pipeline_newgen_rev1/runtime/stages/scan_campaign_structure.py` (novo)
- `src/pipeline_newgen_rev1/ui/campaign_planner_tab.py` (novo)
- `tests/test_campaign_scan.py` (novo)
- `tests/test_campaign_planner_tab.py` (novo)
- `src/pipeline_newgen_rev1/runtime/compare_iteracoes/__init__.py` (modificado)
- `src/pipeline_newgen_rev1/runtime/compare_iteracoes/core.py` (modificado)
- `src/pipeline_newgen_rev1/runtime/compare_iteracoes/prepare.py` (modificado)
- `src/pipeline_newgen_rev1/runtime/compare_iteracoes/series.py` (modificado)
- `src/pipeline_newgen_rev1/runtime/compare_iteracoes/specs.py` (modificado)
- `src/pipeline_newgen_rev1/runtime/compare_plots.py` (modificado)
- `src/pipeline_newgen_rev1/runtime/context.py` (modificado)
- `src/pipeline_newgen_rev1/runtime/stages/__init__.py` (modificado)
- `src/pipeline_newgen_rev1/runtime/stages/compute_compare_iteracoes.py` (modificado)
- `src/pipeline_newgen_rev1/ui/legacy/pipeline29_config_gui.py` (modificado)
- `src/pipeline_newgen_rev1/ui/runtime_preflight/__init__.py` (modificado)
- `src/pipeline_newgen_rev1/workflows/load_sweep/feature_flags.py` (modificado)
- `tests/test_compare_iteracoes.py` (modificado)
- `tests/test_compare_plots.py` (modificado)
- `tests/test_orchestrator.py` (modificado)
- `tests/test_sweep_stages.py` (modificado)

## Validação

- `python -m unittest discover -s tests -p "test_*.py"` → 425 testes OK (+43 sobre sweep-mode-port)
- Smoke test com `Raw_mestrado`: scanner detecta 49 arquivos, 4 combustíveis (D85B15, E65H35, E75H25, E94H6), 20 pontos de carga, `iteration_mode=fuel`
- `compute_compare_iteracoes` com catalog fuel-mode produz deltas significativos entre pares de combustíveis
- Dados Stellantis (baseline/aditivado × subida/descida): backward compat total — `catalog=None` cai no comportamento legado
- Import circular entre `adapters` → `ui.runtime_preflight` → `adapters` resolvido com lazy `__getattr__`

## Pendências

- Testar a GUI interativamente com `Raw_mestrado` (scan → selecionar pares → Save & Run end-to-end)
- Serialização do `campaign_planner_state()` em `compare.toml` (wire Save ainda não persiste o catálogo)
- Modo "Por campanha" no dropdown de modo não tem handler (`_on_mode_changed` é no-op)
- Sincronizar cópia operacional OneDrive antes de run real
