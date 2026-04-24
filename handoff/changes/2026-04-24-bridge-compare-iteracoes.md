# 2026-04-24 — bridge-compare-iteracoes (Passo 2d)

## O que mudou

- **`src/pipeline_newgen_rev1/bridges/legacy_runtime.py`** (modificado) — nova bridge class `RunCompareIteracoesBridgeStage`. Resolve compare requests a partir de `bundle.compare_df` (aba Compare do TOML) via `legacy._resolve_compare_iter_requests`, depois chama `legacy._plot_compare_iteracoes_bl_vs_adtv` passando `ctx.final_table`, `root_plot_dir` e `mappings`. Padrão idêntico ao `RunUnitaryPlotsBridgeStage`: skip graceful quando `final_table is None`, try/except com `[WARN]` sem re-raise.
- **`src/pipeline_newgen_rev1/runtime/context.py`** (modificado) — +1 atributo `compare_iteracoes_export_path: Optional[Path]` na seção bridge do `RuntimeContext`.
- **`src/pipeline_newgen_rev1/runtime/stages/__init__.py`** (modificado) — `RunCompareIteracoesBridgeStage` importada e registrada em `STAGE_REGISTRY`; `"run_compare_iteracoes"` adicionada ao final de `PROCESSING_STAGE_ORDER`.
- **`tests/test_bridge_compare_iteracoes.py`** (novo — 3 testes) — `test_skips_when_final_table_is_none`, `test_invokes_legacy_compare_and_stores_path`, `test_catches_legacy_exception_gracefully`. Usa stub module com `_resolve_compare_iter_requests` e `_plot_compare_iteracoes_bl_vs_adtv` mockados.
- **`scripts/compare_cycle.py`** (modificado) — `_compare_metricas_incertezas()` para validar `compare_iteracoes_metricas_incertezas.xlsx` (shape + DataFrame.equals). Suporte a `sys.argv[1]` como `--raw-source` alternativo (default: `subindo_aditivado_1`).
- **`handoff/stages_status.md`** (modificado) — linha `run_compare_iteracoes` de 🔴 para 🟡 bridge.

## Por quê

O Passo 2d fecha a lacuna funcional mais visível do newgen: a saída `compare_iteracoes_bl_vs_adtv/` (PNGs de comparação BL × ADTV + `compare_iteracoes_metricas_incertezas.xlsx`). A feature flag e a decisão já existiam desde 2026-04-25 (`handoff/decisions/2026-04-25-new-feature-run-compare-iteracoes.md`), mas a bridge stage não havia sido implementada.

A bridge consome `ctx.final_table` (produzido pela `BuildFinalTableBridgeStage`) e a configuração de compare do bundle TOML. Resolve os requests habilitados na aba Compare (honrando enables/disables da GUI) e passa para a função legada que gera os plots e o xlsx.

## Arquivos

- `src/pipeline_newgen_rev1/bridges/legacy_runtime.py` (modificado — +48 linhas, nova class)
- `src/pipeline_newgen_rev1/runtime/context.py` (modificado — +1 atributo)
- `src/pipeline_newgen_rev1/runtime/stages/__init__.py` (modificado — import + registry + order)
- `tests/test_bridge_compare_iteracoes.py` (novo — 3 testes)
- `scripts/compare_cycle.py` (modificado — metricas_incertezas + raw-source arg)
- `handoff/stages_status.md` (modificado — 🔴 → 🟡)

## Validacao

- `python -m unittest discover -s tests -p "test_*.py"` → **83 testes OK** (era 80; +3 novos do bridge).
- `python scripts/compare_cycle.py` (dataset `subindo_aditivado_1`, campanha unica) → rc=0/0; 56/56 PNGs byte-identicos; ambos produziram 0 PNGs de compare_iteracoes (esperado — sem baseline para comparar). Paridade mantida.
- `python scripts/compare_cycle.py E:\raw_pyton\raw_NANUM` (4 campanhas: baseline+aditivado × subida+descida) → rc=0/0; newgen produziu 122 PNGs de compare_iteracoes + xlsx com 1116 linhas/30 colunas (11 metricas × 5 comparacoes × dual uncertainty). Legado raiz produziu 396 linhas (7 metricas — nao suporta `*_g_kwh`). Nas 7 metricas comuns: **14 colunas de valor IDENTICAS**, `significancia_95pct` 396/396 (100%).

## Pendencias

- **Drift legado raiz vs legacy_monoliths**: a copia raiz em `nanum-pipeline-28-main` nao tem as metricas `*_g_kwh` nem os fixes GUM. A paridade byte-a-byte do xlsx so sera possivel quando ambas as copias estiverem sincronizadas, ou quando o port nativo substitua a bridge.
- **Passo 3b.3** — port nativo de `build_final_table` (maior trabalho pendente).
- **`run_compare_plots`** (🔴) — bridge para compare subida×descida dentro da mesma campanha. Mesmo padrao, menor escopo.
- **`run_special_load_plots`** (🔴) — bridge para plots especiais (ethanol equivalent, machine scenarios).
