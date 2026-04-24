# 2026-04-24 — port-upstream-frames (Passo 3b.3)

## O que mudou

- **`src/pipeline_newgen_rev1/runtime/fuel_properties.py`** (novo — ~200 linhas) — port nativo de `load_fuel_properties_lookup` (legado L4274-4317). Converte `ConfigBundle.fuel_properties` (List[Dict]) → DataFrame, normaliza colunas, preenche defaults de densidade/custo via `bundle.defaults`, infere labels de composição, merge com `lhv.csv` fallback. Inclui 5 helpers internos: `_normalize_fuel_properties_df`, `_fill_fuel_property_defaults`, `_fuel_label_from_components`, `_load_lhv_csv`, `_to_float`/`_to_str_or_empty`.
- **`src/pipeline_newgen_rev1/runtime/motec_stats.py`** (novo — ~80 linhas) — port nativo de `compute_motec_trechos_stats` (legado L5031-5057) e `compute_motec_ponto_stats` (legado L5060-5081). Reutiliza `MIN_SAMPLES_PER_WINDOW` e `normalize_repeated_stat_tokens` do subpacote `trechos_ponto`.
- **`src/pipeline_newgen_rev1/runtime/stages/prepare_upstream_frames.py`** (novo) — stage `PrepareUpstreamFramesStage` (feature_key=`prepare_upstream_frames`). Combina 3 preparações: fuel properties (config + CSV fallback), KiBox cross-file aggregation (groupby sobre per-file means já em `ctx.kibox_aggregate_rows`), MoTeC trechos → ponto.
- **`src/pipeline_newgen_rev1/runtime/context.py`** (modificado) — +1 atributo `motec_frames: List[pd.DataFrame]` na seção core helpers.
- **`src/pipeline_newgen_rev1/runtime/runner.py`** (modificado) — `_discover_and_read_inputs` agora armazena raw frames MoTeC em `ctx.motec_frames` (análogo a `ctx.labview_frames`).
- **`src/pipeline_newgen_rev1/runtime/stages/__init__.py`** (modificado) — `PrepareUpstreamFramesStage` registrado no `STAGE_REGISTRY`, inserido entre `compute_trechos_ponto` e `build_final_table`.
- **`src/pipeline_newgen_rev1/workflows/load_sweep/feature_flags.py`** (modificado) — nova `FeatureSpec` `prepare_upstream_frames`.
- **`src/pipeline_newgen_rev1/bridges/legacy_runtime.py`** (modificado) — bypass em `_build_legacy_intermediate_frames` para fuel_properties, kibox_agg e motec_ponto (reutiliza valores nativos quando `ctx.*` já preenchido).
- **`tests/test_upstream_frames.py`** (novo — 22 testes) — fuel (config, CSV fallback, defaults, label inference, vazio), kibox (single/multi-file, vazio), motec (trechos, ponto, filtros, normalization), stage integration.
- **`tests/test_orchestrator.py`** (modificado) — total_steps 17 → 18.
- **`handoff/stages_status.md`** (modificado) — combustível 🔴 → 🟢, KiBox aggregation 🔴 → 🟢.

## Por quê

Os 3 frames restantes que alimentam `build_final_table` eram todos recalculados via legado a cada run pela bridge `_build_legacy_intermediate_frames`. Portar os 3 juntos (fuel_properties, kibox cross-file aggregation, motec trechos/ponto) elimina toda dependência legada nos dados upstream. Agora a bridge `build_final_table` recebe todos os 4 inputs (ponto, fuel, kibox, motec) produzidos nativamente — o próximo passo é portar o `build_final_table` em si.

A adaptação principal foi converter `load_fuel_properties_lookup` para trabalhar com `ConfigBundle.fuel_properties: List[Dict]` e `ConfigBundle.defaults: Dict[str, str]` em vez do legado `Pipeline29ConfigBundle.fuel_properties_df` e `defaults_cfg`.

## Arquivos

- `src/pipeline_newgen_rev1/runtime/fuel_properties.py` (novo)
- `src/pipeline_newgen_rev1/runtime/motec_stats.py` (novo)
- `src/pipeline_newgen_rev1/runtime/stages/prepare_upstream_frames.py` (novo)
- `src/pipeline_newgen_rev1/runtime/context.py` (modificado — +motec_frames)
- `src/pipeline_newgen_rev1/runtime/runner.py` (modificado — armazena motec_frames)
- `src/pipeline_newgen_rev1/runtime/stages/__init__.py` (modificado)
- `src/pipeline_newgen_rev1/workflows/load_sweep/feature_flags.py` (modificado)
- `src/pipeline_newgen_rev1/bridges/legacy_runtime.py` (modificado — 3 bypasses)
- `tests/test_upstream_frames.py` (novo — 22 testes)
- `tests/test_orchestrator.py` (modificado — 17→18)
- `handoff/stages_status.md` (modificado — 2 × 🔴 → 🟢)

## Validação

- `python -m unittest discover -s tests -p "test_*.py"` → **136 testes OK** (era 114; +22 novos).
- Stage graceful skip quando bundle é None ou nenhum dado disponível — testado via runner integration tests existentes.
- Bridge bypass verificado: `_build_legacy_intermediate_frames` reutiliza valores nativos via `ctx.fuel_properties`, `ctx.kibox_agg`, `ctx.motec_ponto`.

## Pendências

- **Paridade com dados reais**: rodar `scripts/compare_cycle.py` com `raw_NANUM` para confirmar que os frames nativos produzem resultados idênticos ao legado. Especialmente fuel_properties (depende da presença ou ausência de `lhv.csv` no config dir).
- **Próximo passo**: port nativo do `build_final_table` em si — agora que os 4 inputs upstream são todos nativos, o `build_final_table` pode ser portado. Este é o passo mais complexo (~300 linhas) e inclui: merge dos 4 frames, incertezas, n_th, BSFC, airflow, emissões, economia.
