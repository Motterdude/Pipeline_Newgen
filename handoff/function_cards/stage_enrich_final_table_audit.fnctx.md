# stage_enrich_final_table_audit

## Role
- **Native** stage que enriquece `ctx.final_table` com colunas de auditoria de incerteza + indicador de contribuição variance-weighted (GUM §F.1.2.4).
- Roda depois de `build_final_table` (bridge) e antes de `export_excel` para que o `lv_kpis_clean.xlsx` saia já com auditoria embutida.
- corresponds to feature_key `enrich_final_table_audit`.

## Inputs
- `ctx.final_table: pd.DataFrame` — populated por `BuildFinalTableBridgeStage`.
- `ctx.bundle.instruments: List[Dict]` — specs dos instrumentos (resolution, acc_abs, acc_pct, digits, lsd, dist).

## Outputs
- `ctx.final_table` mutado in-place com colunas novas por measurand de `AUDITED_MEASURANDS`:
  - `uB_res_<m>` e `uB_acc_<m>` (só para medidas com `instrument_key` não-None).
  - `pct_uA_contrib_<m>` e `pct_uB_contrib_<m>` (para todos os 13 measurands).
  - Para derivadas sem uA/uB separados no input: cria `uA_<m>` e `uB_<m>` via propagação nativa GUM §5.

## Do Not Break
- Nunca sobrescrever `uA_<m>`, `uB_<m>`, `uc_<m>`, `U_<m>` pré-existentes. O audit layer **só adiciona**.
- Se `ctx.final_table is None` ou `ctx.bundle is None`, log e retorna (upstream é responsabilidade do bridge).
- `pct_uA_contrib + pct_uB_contrib = 100` é invariante (testado) — qualquer mudança na fórmula deve preservar.
- Métricas sem instrumento direto (hoje só `Consumo_kg_h`, que é derivada de balance × dt): NÃO emitir `uB_res`/`uB_acc` (seriam em unidade errada).

## Edit Notes
- Subpacote `runtime/uncertainty_audit/` é a lógica; stage é um thin wrapper.
- `specs.py` lista os 13 measurands — adicionar nova grandeza ao `AUDITED_MEASURANDS` + (se derivada) criar função em `derived_propagation.py` + registrar em `core._DERIVED_PROPAGATORS`.
- `decomposition.py` reproduz `uB_from_instruments_rev2` do legado (`nanum_pipeline_29.py:4880-4933`) mas separa uB_res de uB_acc em vez de combinar.
- `contribution.py` implementa `contribution_var(uA, uc) = 100·(uA/uc)²` com tratamento de NaN/zero.
- `derived_propagation.py` propaga uA/uB para `n_th`, `BSFC`, `Consumo_L_h` e emissões `g/kWh` via partials GUM.

## Quick Test
- `python -m unittest discover -s tests -p "test_uncertainty_audit.py"` — 12 unit tests.
- Smoke real: `python scripts/compare_cycle.py` → newgen xlsx ganha ~30 audit cols; byte parity de plots se mantém; xlsx não se iguala por desenho (colunas extras).
- Sanity manual: abrir lv_kpis_clean.xlsx do newgen e verificar que `pct_uA_contrib_Consumo_kg_h + pct_uB_contrib_Consumo_kg_h == 100` em todos os pontos onde uc é finito.
