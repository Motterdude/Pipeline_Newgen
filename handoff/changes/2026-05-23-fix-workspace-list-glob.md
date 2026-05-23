# 2026-05-23 — fix-workspace-list-glob

## O que mudou

- `_refresh_workspace_list` em `preview_plot_tab.py`: substituído o glob `preview_workspace*.json` por `*.json` com filtro por conteúdo (`version == 2` e chave `data_source`). Workspaces salvos via "Save As" com qualquer nome (ex: `NANUM_W_COMBUSTION.json`) agora aparecem na lista. `preview_workspace.json` continua exibido como "(default)".

## Por quê

O usuário salvou um workspace via "Save As" com o nome `NANUM_W_COMBUSTION.json`. O glob anterior `preview_workspace*.json` não encontrava arquivos cujo nome não começasse com `preview_workspace`. O arquivo estava corretamente gravado no config dir (v=2, estrutura válida) mas não aparecia na lista ao reabrir a GUI.

A correção escaneia todos os `.json` do config dir e filtra pelos que são workspaces válidos (version==2 + chave data_source), excluindo naturalmente os outros arquivos da pasta (point_exclusions, preview_presets, y_scale_memory).

## Arquivos

- `src/pipeline_newgen_rev1/ui/preview_plot_tab.py` (modificado — `_refresh_workspace_list`)

## Validação

- `python -m py_compile` → OK
- `python -m unittest discover` → 446 testes, 10 erros pré-existentes (bridges)
- Sanidade manual: `NANUM_W_COMBUSTION.json` e `preview_workspace.json` ambos detectados como workspaces válidos pelo novo filtro

## Pendências

- Nenhuma.
