# 2026-04-24 — port-trechos-ponto (Passo 3b.2)

## O que mudou

- **`src/pipeline_newgen_rev1/runtime/trechos_ponto/`** (novo subpacote — 4 módulos, ~200 linhas) — port nativo de `compute_trechos_stats` e `compute_ponto_stats` do legado `nanum_pipeline_29.py`. Constantes extraídas (`MIN_SAMPLES_PER_WINDOW=30`, `DT_S=1.0`, `B_ETANOL_COL_CANDIDATES`, grupos de colunas). Helpers adaptados para `List[Dict]` (formato do `ConfigBundle.instruments` do newgen) em vez de `instruments_df: pd.DataFrame` do legado.
- **`src/pipeline_newgen_rev1/runtime/stages/compute_trechos_ponto.py`** (novo) — stage `ComputeTrechosPontoStage` (feature_key=`compute_trechos_ponto`). Consome `ctx.labview_frames` + `ctx.bundle.instruments`, produz `ctx.trechos` + `ctx.ponto`. Graceful skip quando `labview_frames` vazio ou coluna B_Etanol ausente.
- **`src/pipeline_newgen_rev1/runtime/context.py`** (modificado) — +1 atributo `trechos: Optional[pd.DataFrame] = None` na seção native stages.
- **`src/pipeline_newgen_rev1/runtime/stages/__init__.py`** (modificado) — `ComputeTrechosPontoStage` importado, registrado no `STAGE_REGISTRY`, inserido no `PROCESSING_STAGE_ORDER` entre `run_time_diagnostics` e `build_final_table`.
- **`src/pipeline_newgen_rev1/workflows/load_sweep/feature_flags.py`** (modificado) — nova `FeatureSpec` `compute_trechos_ponto` (stage=processing, default=True load+sweep).
- **`src/pipeline_newgen_rev1/bridges/legacy_runtime.py`** (modificado) — `_build_legacy_intermediate_frames` agora verifica `ctx.ponto is not None` antes de recalcular trechos/ponto via legado. Quando o stage nativo já preencheu o ponto, a bridge reutiliza o valor nativo.
- **`tests/test_trechos_ponto.py`** (novo — 22 testes) — helpers (find_b_etanol_col, res_to_std, normalize_repeated_stat_tokens, instrument key lookup), compute_trechos_stats (grouping, filter, consumption formula, uB), compute_ponto_stats (aggregation, sd ddof=1, uB propagation, suffix normalization), stage integration (skip, populate, feature_key).
- **`tests/test_orchestrator.py`** (modificado) — total_steps 16 → 17 para refletir nova feature.
- **`handoff/stages_status.md`** (modificado) — `Agregação por trechos e pontos` 🔴 → 🟢.

## Por quê

Trechos e ponto são o primeiro elo da cadeia de processamento: os dados brutos LabVIEW passam por `compute_trechos_stats` (agrupa por janela, calcula médias, consumo via balanço de etanol, uB via resolução do instrumento) e depois por `compute_ponto_stats` (agrega janelas por ponto, calcula média/desvio com ddof=1, propaga uB via RSS/N). Sem eles nativos, a bridge `build_final_table` precisa reimportar e recalcular via o monolito legado a cada run.

A adaptação principal foi converter os helpers de instrumento do formato `instruments_df: pd.DataFrame` (legado, com coluna `key_norm`) para `instruments: List[Dict[str, Any]]` (formato do `ConfigBundle` do newgen), seguindo o padrão já estabelecido em `uncertainty_audit/decomposition.py::_rows_for_key`.

## Arquivos

- `src/pipeline_newgen_rev1/runtime/trechos_ponto/__init__.py` (novo)
- `src/pipeline_newgen_rev1/runtime/trechos_ponto/constants.py` (novo)
- `src/pipeline_newgen_rev1/runtime/trechos_ponto/helpers.py` (novo)
- `src/pipeline_newgen_rev1/runtime/trechos_ponto/core.py` (novo)
- `src/pipeline_newgen_rev1/runtime/stages/compute_trechos_ponto.py` (novo)
- `src/pipeline_newgen_rev1/runtime/context.py` (modificado)
- `src/pipeline_newgen_rev1/runtime/stages/__init__.py` (modificado)
- `src/pipeline_newgen_rev1/workflows/load_sweep/feature_flags.py` (modificado)
- `src/pipeline_newgen_rev1/bridges/legacy_runtime.py` (modificado)
- `tests/test_trechos_ponto.py` (novo — 22 testes)
- `tests/test_orchestrator.py` (modificado — total_steps 16→17)
- `handoff/stages_status.md` (modificado — 🔴 → 🟢)

## Validação

- `python -m unittest discover -s tests -p "test_*.py"` → **114 testes OK** (era 92 antes desta sessão; +22 novos do trechos_ponto).
- Stage skip graceful quando dados LabVIEW não contêm coluna de balanço (coluna B_Etanol ausente) — testado via runner integration tests existentes.
- Bridge bypass verificado: quando `ctx.ponto is not None`, a bridge `build_final_table` reutiliza o ponto nativo sem reimportar o legado para esse cálculo.

## Pendências

- **Paridade com dados reais**: rodar `scripts/compare_cycle.py` com `raw_NANUM` para confirmar `DataFrame.equals` entre ponto nativo e ponto via legado. O código é logicamente idêntico, mas a validação numérica end-to-end é necessária.
- **Próximas estações de processamento** (Fase 2, 🔴): combustível → KiBox → airflow → emissões → ETA_V → economia → incertezas → `build_final_table` nativo.
