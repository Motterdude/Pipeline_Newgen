# 2026-05-23 — plots-kibox-dropdown-and-preview-sync

## O que mudou

1. **Dropdown de y_col no Plots tab agora inclui colunas KIBOX**: o catalogo de variaveis (`_available_variable_catalog`) agora puxa tambem as colunas do DataFrame carregado no Preview Plot (`preview_plot_tab._loaded_df`). Como esse DataFrame vem do `lv_kpis_clean.xlsx` processado, todas as colunas KIBOX_ aparecem no "Pick" ao adicionar novo plot.

2. **Preview Plot atualiza automaticamente ao editar Plots tab**: conectados os signals `rowsInserted`, `rowsRemoved` e `itemChanged` do `plots_table.table.model()` ao `preview_plot_tab.refresh_plot_selector()`. Agora ao adicionar/remover/editar um plot no Plots tab, o dropdown de navegacao no Preview Plot se atualiza instantaneamente.

## Por que

- Colunas KIBOX nao apareciam no dropdown porque o variable catalog so lia do raw input (que nao tem KIBOX). O output processado (lv_kpis_clean.xlsx) que tem essas colunas so era acessivel pelo Preview Plot, nao pelo catalogo do Plots tab.
- Ao adicionar um novo plot na aba Plots, o usuario precisava recarregar a config inteira para ver o novo plot no Preview Plot dropdown. Agora a sincronizacao eh automatica.

## Arquivos

- `src/pipeline_newgen_rev1/ui/legacy/pipeline29_config_gui.py` (modificado — catalogo + signals)

## Validacao

- `py_compile` → OK
- `unittest` → 446 testes, 10 erros pre-existentes, sem regressoes

## Pendencias

- Testar visualmente: adicionar novo plot com y_col KIBOX_ no Plots tab, verificar que aparece no Preview Plot dropdown imediatamente.
- O plot adicionado respeita o workspace/preset existente (Y scale, exclusoes, series styles) porque usa os mesmos mecanismos de `_populate_from_record` + `_session["y_scales"]`.
