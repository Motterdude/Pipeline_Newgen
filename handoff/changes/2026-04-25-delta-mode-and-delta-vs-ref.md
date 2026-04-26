# 2026-04-25 — delta-mode-and-delta-vs-ref

## O que mudou

- **Bug fix MoTeC dtype:** coercao `pd.to_numeric` em colunas de composicao (`DIES_pct`, `BIOD_pct`, etc.) antes de merge/groupby em `motec_stats.py` e `prepare_upstream_frames.py`. Resolvia `ValueError: merge on object and float64`.
- **Bug fix compare plots vazio em fuel mode:** (a) fallback em `resolve_requests()` quando GUI envia series legacy incompativeis com fuel mode — detecta mismatch e usa `_default_compare_pairs(catalog)`; (b) `_apply_diesel_filter` renomeada para `_apply_composition_filter` — agora verifica 4 colunas de composicao (`DIES_pct`, `BIOD_pct`, `EtOH_pct`, `H2O_pct`) ao inves de so diesel, permitindo que combustiveis etanol passem pelo filtro.
- **Feature `delta_mode` em compare_iteracoes:** cada metrica agora declara `delta_mode: "diff"` (metricas ja em %, como n_th, CO2, O2) ou `"ratio"` (valores absolutos como BSFC, consumo, CO, NOx). `build_delta_table()` computa delta em pp (diff) ou % (ratio) conforme o modo. Plot de delta ajusta eixo Y e titulo.
- **Feature `_delta_vs_ref` em final_table:** novo modulo `_delta_vs_ref.py` computa colunas de delta-vs-D85B15 com incerteza GUM diretamente dentro de `build_final_table()`, garantindo presenca em `lv_kpis_clean.xlsx`. Metricas: `n_th_pct` (diff/pp) e `BSFC_g_kWh` (ratio/%).
- **Novo plot type `all_fuels_delta_ref`:** renderer com eixo duplo (`twinx`) — primario mostra valores absolutos por combustivel, secundario mostra delta vs referencia em linhas tracejadas coordenadas por cor. Dispatch case + 2 entradas no `plots.toml`.

## Por que

Ao rodar o pipeline com dados do mestrado (4 combustiveis, fuel mode), tres problemas apareceram:
1. MoTeC falhava no merge por dtype mismatch (colunas de composicao como object).
2. Compare plots nao geravam porque as series legacy da GUI nao batem com fuel mode, e o filtro de diesel descartava combustiveis etanol.
3. Delta de n_th aparecia como 3.33% (razao) quando deveria ser 1 pp (diferenca absoluta entre percentuais).

Alem disso, o usuario pediu graficos comparativos de eficiencia termica e BSFC com todos os combustiveis e um segundo eixo mostrando o delta vs D85B15, com a restricao de que todo dado calculado deve estar auditavel no Excel.

## Arquivos

- `src/pipeline_newgen_rev1/runtime/motec_stats.py` (modificado — coercao numerica)
- `src/pipeline_newgen_rev1/runtime/stages/prepare_upstream_frames.py` (modificado — coercao numerica KiBox)
- `src/pipeline_newgen_rev1/runtime/compare_iteracoes/specs.py` (modificado — `delta_mode` por metrica)
- `src/pipeline_newgen_rev1/runtime/compare_iteracoes/delta.py` (modificado — branching diff/ratio)
- `src/pipeline_newgen_rev1/runtime/compare_iteracoes/core.py` (modificado — fallback + delta_mode passthrough)
- `src/pipeline_newgen_rev1/runtime/compare_iteracoes/prepare.py` (modificado — `_apply_composition_filter`)
- `src/pipeline_newgen_rev1/runtime/compare_iteracoes/plot_delta.py` (modificado — labels diff/ratio)
- `src/pipeline_newgen_rev1/runtime/stages/plot_compare_iteracoes.py` (modificado — delta_mode no titulo)
- `src/pipeline_newgen_rev1/runtime/final_table/_delta_vs_ref.py` (novo — delta vs ref com GUM)
- `src/pipeline_newgen_rev1/runtime/final_table/core.py` (modificado — chamada `_attach_delta_vs_ref_metrics`)
- `src/pipeline_newgen_rev1/runtime/unitary_plots/renderers.py` (modificado — `plot_all_fuels_delta_ref`)
- `src/pipeline_newgen_rev1/runtime/unitary_plots/dispatch.py` (modificado — dispatch `all_fuels_delta_ref`)
- `config/pipeline29_text/plots.toml` (modificado — 2 entradas delta_ref)
- `tests/test_delta_vs_ref.py` (novo — 8 testes)
- `tests/test_unitary_plots.py` (modificado — 2 testes do renderer)

## Validacao

- `python -m unittest discover -s tests -p "test_*.py"` -> 435 testes OK
- `py_compile` de todos os `.py` -> OK
- Sincronizado para OneDrive operacional

## Pendencias

- Rodar pipeline completo com Raw_mestrado via GUI para verificar:
  - `lv_kpis_clean.xlsx` com colunas `Delta_pp_n_th_pct_vs_D85B15` e `Delta_pct_BSFC_g_kWh_vs_D85B15`
  - PNGs `n_th_pct_vs_power_delta_ref.png` e `bsfc_g_kwh_vs_power_delta_ref.png` gerados
  - Compare plots de n_th mostram "Diferenca (pp)" no eixo Y
- Adicionar mais metricas ao `_DELTA_VS_REF_SPECS` conforme necessidade (consumo, emissoes, etc.)
