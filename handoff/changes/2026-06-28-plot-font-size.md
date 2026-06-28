# 2026-06-28 — Plot Font Size configurável

## O que mudou

- Botão "Font..." na barra superior do Preview Plot abre dialog com spinbox (6–32, default 12).
- O tamanho é aplicado ao título (+2), labels dos eixos, ticks (-1) e legenda (-1) de cada figura renderizada.
- O Export All aplica o mesmo font size via rcParams durante o loop de export.
- Valor persiste em `session["display"]["plot_font_size"]` → salvo no workspace JSON.

## Por quê

PNGs exportados para o Word ficavam com fontes pequenas demais para leitura confortável.

## Arquivos

- `src/pipeline_newgen_rev1/ui/preview_plot_tab.py`

## Validação

- `py_compile` OK.
- Workspace compat: workspaces antigos sem `plot_font_size` usam default 12.

## Pendências

- Nenhuma.
