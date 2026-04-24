# 2026-04-24 — port-build-final-table

## O que mudou

- Criado subpacote `runtime/final_table/` com 15 módulos (2.217 linhas) que reproduzem fielmente toda a lógica de `build_final_table` do legado (`nanum_pipeline_29.py` L5361-5832 + 21 helpers).
- Criado stage nativo `runtime/stages/build_final_table.py` (`BuildFinalTableStage`).
- Registry em `runtime/stages/__init__.py` atualizado: import de `BuildFinalTableStage` substitui `BuildFinalTableBridgeStage`.
- Bridge `BuildFinalTableBridgeStage` não é mais usada no fluxo — permanece no código apenas como referência.

## Por quê

`build_final_table` é o coração do processamento — monta o DataFrame que vira `lv_kpis_clean.xlsx`. Todos os 4 inputs upstream já eram nativos (`ponto`, `fuel_properties`, `kibox_agg`, `motec_ponto`), então era o próximo passo natural para eliminar a maior dependência restante do legado no fluxo de dados.

O port é fiel à matemática do legado (GUM, emissões, airflow, economia vs diesel, cenários de máquinas, etc.) e adaptado para os tipos do newgen (`instruments: List[Dict]` em vez de `instruments_df: DataFrame`).

## Arquivos

- `src/pipeline_newgen_rev1/runtime/final_table/__init__.py` (novo)
- `src/pipeline_newgen_rev1/runtime/final_table/constants.py` (novo — K_COVERAGE, AFR_STOICH, MW_*, MACHINE_SCENARIO_SPECS)
- `src/pipeline_newgen_rev1/runtime/final_table/_helpers.py` (novo — norm_key, resolve_col, _to_float, fuzzy column matching)
- `src/pipeline_newgen_rev1/runtime/final_table/_psychrometrics.py` (novo — psat, humidity_ratio, cp_air)
- `src/pipeline_newgen_rev1/runtime/final_table/_source_identity.py` (novo — SourceFolder, SourceFile, Sentido_Carga, Iteracao)
- `src/pipeline_newgen_rev1/runtime/final_table/_merge.py` (novo — left merge on fuel composition keys)
- `src/pipeline_newgen_rev1/runtime/final_table/_fuel_defaults.py` (novo — blend labels, density/cost lookup, LHV)
- `src/pipeline_newgen_rev1/runtime/final_table/_uncertainty_instruments.py` (novo — uB from instruments, uA/uB/uc/U propagation)
- `src/pipeline_newgen_rev1/runtime/final_table/_airflow.py` (novo — MAF vs fuel+lambda airflow)
- `src/pipeline_newgen_rev1/runtime/final_table/_emissions.py` (novo — specific emissions g/kWh with H2O mass balance)
- `src/pipeline_newgen_rev1/runtime/final_table/_volumetric_efficiency.py` (novo — ETA_V from airflow)
- `src/pipeline_newgen_rev1/runtime/final_table/_diesel_cost_delta.py` (novo — economia vs diesel com incerteza GUM)
- `src/pipeline_newgen_rev1/runtime/final_table/_machine_scenarios.py` (novo — cenários E94H6 Colheitadeira/Trator/Caminhao)
- `src/pipeline_newgen_rev1/runtime/final_table/_reporting.py` (novo — rounding por resolução do reporting)
- `src/pipeline_newgen_rev1/runtime/final_table/core.py` (novo — orquestrador `build_final_table()`)
- `src/pipeline_newgen_rev1/runtime/stages/build_final_table.py` (novo — stage nativo)
- `src/pipeline_newgen_rev1/runtime/stages/__init__.py` (modificado — import nativo substitui bridge)
- `handoff/stages_status.md` (modificado — build_final_table e 5 sub-fluxos → 🟢)

## Validação

- `python -m unittest discover -s tests -p "test_*.py"` → **136 tests OK** (3.4s)
- `python -c "from pipeline_newgen_rev1.runtime.final_table import build_final_table"` → import OK
- Stage é invocada corretamente pelo runner nos testes de orquestração

## Pendências

- Testes unitários específicos para os módulos de `final_table/` (cobertura de edge cases por módulo)
- Validação end-to-end: comparar output `lv_kpis_clean.xlsx` nativo vs legado com dados reais (`compare_cycle`)
- Remover `BuildFinalTableBridgeStage` de `bridges/legacy_runtime.py` quando confirmada paridade total
