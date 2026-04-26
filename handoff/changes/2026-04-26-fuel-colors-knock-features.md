# 2026-04-26 — fuel-colors-knock-features

## O que mudou

1. **Cores fixas por combustivel** — Novo modulo `runtime/fuel_colors.py` com `fuel_color_map()` que resolve `fuel_label -> cor hex` a partir de `defaults.toml`. Todos os renderers unitarios (4 funcoes) e o knock histogram agora usam cores consistentes entre graficos. Cores configuraveis na GUI via color picker (QPushButton + QColorDialog) na aba "Knock Thresholds", salvas no preset via workflow normal.

2. **Knock exceedance (thresholds)** — Contagem de ciclos KiBox com KPEAK acima de limiares configuraveis (3 bar, 5 bar default). GUI com checkbox + tabela editavel de thresholds. Saida no Excel agregado.

3. **Knock CCDF (exceedance distribution)** — Curva complementar CDF (P(KPEAK > x) de ~100% ate 0%) por combustivel. 3 variantes de escala (linear, log10, log2). Plots combinados + per-load (um grafico por carga com todos os combustiveis sobrepostos).

4. **Eficiencia termica indicada** — `P_ind_kW`, `n_th_ind`, `n_th_ind_pct`, `n_mech`, `n_mech_pct` calculados a partir de IMEPH do KiBox, cilindrada 3.992L, RPM. Colunas disponiveis na final_table para plotagem via GUI.

5. **Otimizacao de performance** — Eliminacao de double-read KiBox (parametro `preloaded`), consolidacao de 3 `rglob` em 1, correcao de fragmentacao de DataFrame (`df.assign(**dict)` em vez de `df[col] = ...` em loop), supressao de PerformanceWarning.

## Por que

- Cores inconsistentes entre graficos dificultavam comparacao visual entre combustiveis
- Knock exceedance e distribuicao sao metricas essenciais para analise de combustao dual-fuel
- Eficiencia indicada complementa a eficiencia de freio para analise termodinamica
- Pipeline estava lento apos selecao de pontos (double-read + fragmentacao)

## Arquivos

### Criados
- `src/pipeline_newgen_rev1/runtime/fuel_colors.py` — utilitario compartilhado de cores
- `src/pipeline_newgen_rev1/runtime/knock_exceedance.py` — contagem de exceedance
- `src/pipeline_newgen_rev1/runtime/knock_histogram.py` — CCDF + plot
- `src/pipeline_newgen_rev1/runtime/stages/plot_knock_histogram.py` — stage de plot
- `config/pipeline29_text/knock_thresholds.toml` — config de thresholds
- `handoff/decisions/2026-04-26-config-via-gui-preset-workflow.md` — decisao: config via GUI preset

### Modificados
- `config/pipeline29_text/defaults.toml` — +4 FUEL_COLOR_*, +2 GUI_KNOCK_* flags
- `src/pipeline_newgen_rev1/runtime/unitary_plots/renderers.py` — fuel_colors param nos 4 renderers
- `src/pipeline_newgen_rev1/runtime/unitary_plots/dispatch.py` — fuel_color_map + threading
- `src/pipeline_newgen_rev1/runtime/stages/run_unitary_plots.py` — passa defaults
- `src/pipeline_newgen_rev1/runtime/stages/plot_knock_histogram.py` — passa fuel_colors
- `src/pipeline_newgen_rev1/runtime/stages/__init__.py` — registro da stage plot_knock_histogram
- `src/pipeline_newgen_rev1/runtime/context.py` — campos knock_histogram_raw/by_load
- `src/pipeline_newgen_rev1/runtime/runner.py` — coleta KPEAK por fuel/load, preloaded KiBox
- `src/pipeline_newgen_rev1/runtime/final_table/core.py` — secao 5a-bis n_th_ind + df.assign
- `src/pipeline_newgen_rev1/runtime/uncertainty_audit/core.py` — df.copy() defrag
- `src/pipeline_newgen_rev1/runtime/motec_stats.py` — remocao de .copy() desnecessarios
- `src/pipeline_newgen_rev1/adapters/kibox_reader.py` — parametro preloaded
- `src/pipeline_newgen_rev1/adapters/input_discovery.py` — rglob consolidado
- `src/pipeline_newgen_rev1/ui/legacy/pipeline29_config_gui.py` — color picker + knock checkboxes
- `src/pipeline_newgen_rev1/workflows/load_sweep/feature_flags.py` — feature flags knock
- `tests/test_sweep_stages.py`, `tests/test_compare_plots.py`, `tests/test_orchestrator.py` — stage count 19->21

## Validacao

- `python -m unittest discover -s tests -p "test_*.py"` — 0 falhas novas (10 erros pre-existentes de bridges removidas)
- Compile check OK em todos os arquivos modificados
- GUI: color picker funcional, cores persistem via preset

## Pendencias

- **Knock CCDF escala log**: a curva log10/log2 plotada com eixo 0-100% achata o sinal na regiao mais relevante (<5%). Revisar: considerar eixo em fracao (0-1) ou ajustar limites y para log, ou usar escala log apenas no range util.
