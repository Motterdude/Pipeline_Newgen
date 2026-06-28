# 2026-06-28 — Remove tolerance lines dos gráficos

## O que mudou

- **`preview_plot_tab.py`**: campos `edit_y_tol_plus` / `edit_y_tol_minus` ocultados da UI (`.setVisible(False)`). `_apply_tolerance_to_fig` retorna imediatamente sem desenhar nada.
- **`renderers.py`**: `_add_y_tolerance_guides` retorna 0 sem desenhar axhlines.

## Por quê

Linhas vermelhas tracejadas de tolerância poluíam visualmente os gráficos e não eram utilizadas na análise do mestrado.

## Arquivos

- `src/pipeline_newgen_rev1/ui/preview_plot_tab.py`
- `src/pipeline_newgen_rev1/runtime/unitary_plots/renderers.py`

## Validação

- `py_compile` OK nos dois arquivos.
- Compatibilidade mantida: workspaces antigos que guardam `y_tol_plus`/`y_tol_minus` continuam carregando sem erro (valores são ignorados silenciosamente).

## Pendências

- Nenhuma.
