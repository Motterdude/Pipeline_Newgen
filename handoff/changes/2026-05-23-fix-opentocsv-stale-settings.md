# 2026-05-23 — fix-opentocsv-stale-settings

## O que mudou

- `src/pipeline_newgen_rev1/adapters/open_to_csv.py`: adicionada lógica defensiva em `find_open_to_csv_path()` que detecta quando o path salvo em settings não existe mais no disco e o limpa automaticamente, permitindo que os candidatos padrão sejam usados.
- `C:\Users\sc61730\AppData\Local\pipeline_newgen_rev1\open_to_csv_settings.json`: corrigido manualmente de um path temporário stale para a instalação real.

## Por quê

Após instalar o KiBox ToGo (Kistler CSVExportSeriell), a GUI reportava erro de "não encontrei o OpenToCSV.exe" mesmo com o executável presente em `C:\Program Files (x86)\Kistler\CSVExportSeriell\OpenToCSV.exe`.

A causa raiz era o arquivo de settings persistido (`open_to_csv_settings.json`) que apontava para `C:\Users\sc61730\AppData\Local\Temp\tmp1gygrapc\fake_OpenToCSV.py` — um script fake criado durante execução de testes unitários que ficou gravado como path "lembrado". Embora o código já verificasse `.exists()` antes de usar qualquer candidato, a mensagem de erro no `FileNotFoundError` listava os paths testados de forma confusa.

A correção defensiva agora limpa automaticamente paths salvos que não existem, garantindo que o settings nunca acumule entradas stale.

## Arquivos

- `src/pipeline_newgen_rev1/adapters/open_to_csv.py` (modificado)

## Validação

- `python -m unittest discover -s tests -p "test_open_to_csv*"` → 5 testes OK
- `python -m unittest discover -s tests -p "test_*.py"` → 445 testes, 10 erros (todos pré-existentes em bridges legados, não relacionados)
- Teste manual: `find_open_to_csv_path()` retorna path correto; `OpenToCSV.exe` responde (return code 6 sem argumentos = esperado)

## Pendências

- Nenhuma. A instalação do KiBox ToGo está funcional e o adapter encontra o executável corretamente.
