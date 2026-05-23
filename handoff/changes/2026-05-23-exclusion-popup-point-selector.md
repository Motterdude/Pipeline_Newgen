# 2026-05-23 — exclusion-popup-point-selector

## O que mudou

- `src/pipeline_newgen_rev1/runtime/plot_point_filter.py`:
  - `QFileDialog` adicionado ao bloco de imports PySide6.
  - Variável de módulo `_runtime_exclusion_list_path: Optional[Path] = None` e getter `get_runtime_exclusion_list_path()` adicionados.
  - Nova função `_show_exclusion_preview_qt(path, parent)`: dialog read-only com tabela de exclusões (5 colunas: Serie, Load kW, Escopo, Razao, Data), botão "OK — aplicar estas exclusoes".
  - Em `accept_selection()` dentro de `_prompt_plot_point_filter_catalog_via_qt`: após validar seleção e antes de `dialog.accept()`, exibe `QMessageBox.question("Deseja aplicar uma lista de exclusao?")`; Sim → abre `QFileDialog`, se arquivo selecionado chama `_show_exclusion_preview_qt` e salva em `_runtime_exclusion_list_path`; Não → `_runtime_exclusion_list_path = None`.

- `src/pipeline_newgen_rev1/runtime/runner.py`:
  - Em `_discover_and_read_inputs`, após `prompt_plot_point_filter_from_metas` retornar, lê `get_runtime_exclusion_list_path()` e seta `ctx.exclusion_list_path` se o arquivo existir.

## Por quê

A implementação anterior adicionou o seletor de exclusion list ao `Pipeline30SweepHelperDialog` (aba que abre ao clicar na tab "Pipeline 30 Sweep/Load helper"). O usuário nunca chegou a ver esse seletor porque não abriu aquela aba antes de clicar em "Save & Run". O lugar correto é o seletor de pontos interativo (`_prompt_plot_point_filter_catalog_via_qt`), que já abre automaticamente após "Save & Run". O pop-up aparece exatamente no momento certo: depois de o usuário confirmar quais pontos plotar, antes de o pipeline processar os dados.

## Arquivos

- `src/pipeline_newgen_rev1/runtime/plot_point_filter.py` (modificado)
- `src/pipeline_newgen_rev1/runtime/runner.py` (modificado)

## Validação

- `python -m py_compile` → OK
- `python -m unittest discover` → 446 testes, 10 erros pré-existentes (bridges)

## Pendências

- O seletor no `Pipeline30SweepHelperDialog` ainda existe (permite pré-configurar via aba helper). As duas vias funcionam: o dialog interativo sobrescreve a configuração do helper se o usuário selecionar algo.
- Testar ciclo completo end-to-end com exclusion list real.
