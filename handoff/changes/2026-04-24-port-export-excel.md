# 2026-04-24 — port-export-excel

## O que mudou

- Criado stage nativo `runtime/stages/export_excel.py` (`ExportExcelStage`) que substitui `ExportExcelBridgeStage`.
- Registry em `runtime/stages/__init__.py` atualizado: import nativo, bridge removida do import.
- 4 testes unitários adicionados em `tests/test_final_table.py`.

## Por quê

`export_excel` era uma bridge trivial que chamava `legacy.safe_to_excel()` — basicamente um `df.to_excel()` com fallback de PermissionError. Todo o rounding e reordenação de colunas já são feitos upstream por `build_final_table`. Portar elimina mais uma dependência do legado e simplifica o fluxo.

## Arquivos

- `src/pipeline_newgen_rev1/runtime/stages/export_excel.py` (novo)
- `src/pipeline_newgen_rev1/runtime/stages/__init__.py` (modificado — troca import)
- `tests/test_final_table.py` (modificado — 4 testes novos)
- `handoff/stages_status.md` (modificado — export_excel 🟡→🟢)

## Validação

- `python -m unittest discover -s tests -p "test_*.py"` → **219 tests OK**

## Pendências

- Nenhuma. Bridge `ExportExcelBridgeStage` pode ser removida de `bridges/legacy_runtime.py` quando as outras 2 bridges também forem portadas.
