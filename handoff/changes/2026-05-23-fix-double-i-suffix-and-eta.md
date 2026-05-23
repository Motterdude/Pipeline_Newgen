# 2026-05-23 — fix-double-i-suffix-and-eta

## O que mudou

- `src/pipeline_newgen_rev1/adapters/open_to_csv.py`: `_default_output_name()` agora detecta se o stem do .open já termina com `_i` e não duplica o sufixo. `D85B15_10kW_i.open` → `D85B15_10kW_i.csv` (antes gerava `D85B15_10kW_i_i.csv`).
- `src/pipeline_newgen_rev1/ui/legacy/pipeline29_config_gui.py`: adicionada estimativa de tempo (ETA) na barra de status durante a conversão batch de .open, baseada na média de tempo por arquivo.
- `tests/test_open_to_csv_adapter.py`: novo teste `test_planned_pipeline_name_no_double_i_suffix` confirma o comportamento correto.

## Por quê

Os arquivos .open na pasta `_renamed_combustion` já seguem a convenção `D85B15_{load}kW_i.open` (com `_i` no stem). O pipeline mode adicionava outro `_i`, gerando nomes como `_i_i.csv` que quebravam a detecção de "já convertido" no scan.

A estimativa de tempo foi adicionada para dar visibilidade ao usuário durante conversões batch de muitos arquivos (ex: 223 .open de combustão).

## Arquivos

- `src/pipeline_newgen_rev1/adapters/open_to_csv.py` (modificado)
- `src/pipeline_newgen_rev1/ui/legacy/pipeline29_config_gui.py` (modificado)
- `tests/test_open_to_csv_adapter.py` (modificado)

## Validação

- `python -m unittest discover -s tests -p "test_open_to_csv*"` → 6 testes OK
- `python -m unittest discover -s tests -p "test_*.py"` → 446 testes, 10 erros pré-existentes
- Teste manual: `export_open_file()` com `D85B15_10kW_i.open` gera `D85B15_10kW_i.csv` (600 KB, 603 linhas de dados de combustão)

## Pendências

- Nenhuma. Recarregar a GUI e apontar para `raw_nanum_post_injector_fix_renamed_combustion` para converter os 223 .open.
