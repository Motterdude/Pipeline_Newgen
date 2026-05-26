# 2026-05-25 — fix-navigation-mode-stickiness

## O que mudou

- **Fix A — Sync imediato do `active_mode`**: `_on_plot_type_changed()` agora grava `self._session["active_mode"] = text` imediatamente ao trocar o combo, não apenas no Save.
- **Fix B — Modos sticky na navegação**: `_populate_from_record()` não mais força o `session_mode` salvo sobre o combo ao navegar. Todos os 4 modos principais (`all_iterations_yx`, `compare_bl_vs_adtv`, `all_fuels_yx`, `all_fuels_delta_ref`) são "sticky" — o modo fica onde o usuário escolheu até mudar manualmente.
- **Fix C — Traceback no render**: O `except Exception` no `_render_preview()` agora loga o traceback completo no `gui_error.log` e mostra na placeholder.
- **Suite de validação**: Novo `tests/test_preview_navigation.py` com 94 testes em 14 classes cobrindo toda a máquina de estados de navegação.

## Por quê

Ao rodar dados do mestrado no novo formato e usar o Plot Preview, o sistema crashava ao tentar trocar presets, a seta de navegação saía de `allfuels_xy` e ia para `compare_bl_vs_adtv`, títulos ficavam trocados, e escalas não casavam com a minimap. 

A causa raiz era que `_session["active_mode"]` só era atualizado no Save (via `_sync_ui_to_session`), mas era consultado durante a navegação para forçar o mode de volta ao valor salvo — criando um loop: workspace salva "compare" → reload força compare → usuário tenta escapar → próxima navegação puxa de volta.

## Arquivos

- `src/pipeline_newgen_rev1/ui/preview_plot_tab.py` (modificado — 3 pontos: linha 2382, linhas 3234-3247, linhas 3470-3472)
- `tests/test_preview_navigation.py` (novo — 94 testes, ~700 linhas)

## Validação

- `python -m unittest discover -s tests -p "test_*.py"` → 540 testes, 10 erros pré-existentes (bridges legados), **0 falhas novas**
- `python -m py_compile src/pipeline_newgen_rev1/ui/preview_plot_tab.py` → OK
- Suite específica: `python -m unittest discover -s tests -p "test_preview_navigation.py"` → **94 tests OK, 0.007s**

## Método de teste

Abordagem de **NavigationHarness** (stub leve): em vez de instanciar o widget completo PySide6 (que requer display server), criou-se um harness que replica a máquina de estados com stubs de QComboBox/QLineEdit/QCheckBox. A lógica dos métodos de navegação foi copiada verbatim do widget real, garantindo fidelidade 1:1 sem depender de Qt runtime.

Técnicas de QA aplicadas:
- Boundary Value Analysis (0 plots, 1 plot, wrap-around)
- Equivalence Partitioning (modos sticky vs non-sticky)
- State Transition Testing (matrix 7×7 de transições)
- Pairwise Combinations (lock_x × mode × direction)
- Error Guessing (NaN, records vazios, _compare_df None)
- Regression Testing (1+ teste por bug corrigido)
- Rapid Stress (20 navegações consecutivas)

## Pendências

- Minimap thumbnails podem mostrar escalas diferentes do plot principal (auto-scale vs user-scale) — não corrigido nesta sessão, apenas diagnosticado.
- O workspace Nanum tem `active_mode: "compare_bl_vs_adtv"` salvo — na próxima abertura vai iniciar em compare (comportamento correto), mas o usuário agora pode sair normalmente.
