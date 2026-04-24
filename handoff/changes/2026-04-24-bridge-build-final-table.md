# 2026-04-24 — bridge-build-final-table (Passo 2b)

## O que mudou

- **Decisão arquitetural registrada** em `handoff/decisions/2026-04-24-new-feature-build-final-table.md` — adicionar `build_final_table` a `LOAD_SWEEP_FEATURE_SPECS` (15ª entrada).
- **`src/pipeline_newgen_rev1/workflows/load_sweep/feature_flags.py`** — nova `FeatureSpec(key="build_final_table", stage="processing", default_by_mode={"load": True, "sweep": True})`.
- **`src/pipeline_newgen_rev1/bridges/legacy_pipeline30.py`** — nova âncora `"build_final_table": "nanum_pipeline_29.py::build_final_table"`.
- **`src/pipeline_newgen_rev1/runtime/context.py`** — 4 novos slots: `ponto`, `fuel_properties`, `kibox_agg`, `motec_ponto` (DataFrames intermediários que a bridge popula junto com `final_table`).
- **`src/pipeline_newgen_rev1/bridges/legacy_runtime.py`** — três adições:
  - `_try_load_legacy_pipeline29()` — variante do loader que retorna `None` se matplotlib/etc não está instalado, em vez de quebrar. Usada por bridges para log-and-skip em dev env sem `[legacy]` extra.
  - `_build_legacy_intermediate_frames(ctx)` — reproduz as 11 chamadas do `main()` legado: reload do bundle legado → `apply_runtime_path_overrides` (muta globals do monolito) → discovery de `.xlsx`/`.csv` via `ctx.input_dir.rglob` → `parse_meta` + bucket → `read_labview_xlsx` N → `compute_trechos_stats` → `compute_ponto_stats` → `load_fuel_properties_lookup` → `kibox_aggregate` (ou DataFrame vazio) → MoTeC chain (`read_motec_csv` + `compute_motec_trechos_stats` + `compute_motec_ponto_stats`). Retorna dict com os 4 DataFrames + configs + referência ao módulo legado.
  - `BuildFinalTableBridgeStage(feature_key="build_final_table")` — chama o helper acima, popula `ctx.{ponto,fuel_properties,kibox_agg,motec_ponto}`, então chama `legacy.build_final_table(...)` e popula `ctx.final_table`.
- **`src/pipeline_newgen_rev1/runtime/stages/__init__.py`** — registra `BuildFinalTableBridgeStage` em `STAGE_REGISTRY` e insere `"build_final_table"` em `STAGE_PIPELINE_ORDER` **antes** de `"export_excel"`. Agora `export_excel` encontra `ctx.final_table` populado quando `[legacy]` está instalado, e o bridge escreve `lv_kpis_clean.xlsx` real.
- **`tests/test_bridge_build_final_table.py`** (novo) — 3 casos com mock do legado via `sys.modules["nanum_pipeline_29"] = stub`:
  - `test_populates_final_table_via_legacy_chain` — verifica que a bridge chama todas as funções legadas esperadas e popula `ctx.final_table`.
  - `test_skips_when_input_dir_missing` — ctx sem `input_dir` → bridge loga e retorna; ctx mantém `final_table=None`.
  - `test_motec_empty_when_no_motec_files` — diretório sem `_m.csv` → `ctx.motec_ponto` vira DataFrame vazio; funções MoTeC não são chamadas.
- **`tests/test_orchestrator.py`** — ajuste de assertion: `total_steps` agora é 15 (era 14).

## Por quê

Passo 2a entregou a bridge `export_excel` em no-op porque `ctx.final_table` era sempre `None`. Passo 2b fecha o loop: quando a cópia operacional tem `pip install .[legacy]`, rodar `run_load_sweep` produz o `lv_kpis_clean.xlsx` real pelo newgen — a mesma saída do pipeline29 legado, só que acionada pelo registry de estações da fábrica nova.

A decisão de reproduzir a cadeia em vez de invocar o `main()` legado diretamente vem de restrições do `main()`: prompt interativo para filtro de pontos (`prompt_plot_point_filter_from_metas`), argparse, resolução de `plot_scope`, etc. A bridge isola só o caminho de preparação → `build_final_table`, que é puro dado-em/dado-out.

O mock no teste cobre o caso do dev env sem matplotlib: 58 testes verdes em qualquer ambiente. Paridade numérica byte-for-byte do `lv_kpis_clean.xlsx` fica como smoke de integração no env operacional (fora de `tests/`).

## Arquivos

- `handoff/decisions/2026-04-24-new-feature-build-final-table.md` (novo)
- `handoff/changes/2026-04-24-bridge-build-final-table.md` (novo — este arquivo)
- `handoff/CHANGES_INDEX.md` (entrada no topo)
- `handoff/stages_status.md` (Fase 2 "Montagem da tabela final" 🔴 → 🟡 bridge; Fase 4 "Export Excel" ganha nota "ativo quando build_final_table roda")
- `handoff/function_cards/bridge_legacy_runtime.fnctx.md` (atualizado — agora menciona as 2 bridges)
- `handoff/function_cards/stage_build_final_table.fnctx.md` (novo)
- `src/pipeline_newgen_rev1/workflows/load_sweep/feature_flags.py` (15ª entrada)
- `src/pipeline_newgen_rev1/bridges/legacy_pipeline30.py` (âncora nova)
- `src/pipeline_newgen_rev1/runtime/context.py` (4 slots novos)
- `src/pipeline_newgen_rev1/bridges/legacy_runtime.py` (helper + 1 classe bridge nova; `_try_load` fallback)
- `src/pipeline_newgen_rev1/runtime/stages/__init__.py` (registry + ordem)
- `tests/test_bridge_build_final_table.py` (novo)
- `tests/test_orchestrator.py` (assertion 14 → 15)

## Validação

- `python -m unittest discover -s tests -p "test_*.py"` → **58 testes, OK, 1 skipped** (era 55; +3 do bridge novo).
- `PYTHONPATH=src python -m pipeline_newgen_rev1.cli show-plan --mode load` → lista `build_final_table` em `processing`, default enabled.
- `compileall` OK.
- Assinatura de `run_load_sweep` preservada; summary keys idênticas.
- Fallback `_try_load_legacy_pipeline29()` evita regressão no dev env (os 2 testes de `test_runtime_runner` voltaram a passar após o fix).

## Pendências

- **Passo 2c**: bridge `run_unitary_plots` consumindo `ctx.final_table` (provavelmente também `ctx.bundle.plots_df`). Pode ter precisão de nova slot em ctx para o plot summary legado.
- **Bridge `run_time_diagnostics`**: opcional; consome `ctx.labview_frames`. Decidir se entra em 2c ou depois.
- **Smoke de integração real** no env operacional (OneDrive): rodar `pip install .[legacy]` + `python -m pipeline_newgen_rev1.cli run-load-sweep --config-dir config\pipeline29_text --process-dir E:\raw_pyton\raw_NANUM --out-dir E:\out_Nanum_rev2 --json` e comparar `E:\out_Nanum_rev2\lv_kpis_clean.xlsx` com o baseline do legado para validar paridade numérica.
- **Fixture de paridade** (`tests/fixtures/paridade/`) para teste de paridade byte-for-byte quando o primeiro port nativo de uma função da cadeia for feito.
- **Sincronizar git ↔ OneDrive** antes de qualquer Save & Run real.
