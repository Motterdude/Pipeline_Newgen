# 2026-05-23 — fix-exclusion-ycol-scope-and-restore-all

## O que mudou

### `point_exclusion.py` — redesign do ExclusionKey com escopo y_col

- `ExclusionKey` muda de `(series_label, load_kw)` para `(series_label, load_kw, y_col)`.
- `y_col="*"` = exclusão global (aplica-se a todos os plots); `y_col=<coluna>` = só afeta aquele plot.
- Novo método `active_keys_for_ycol(y_col)`: retorna apenas os pares `(series, load)` relevantes ao y_col atual (inclui "*" e exato).
- `apply_exclusions` ganha parâmetro `y_col` e usa `active_keys_for_ycol` em vez do set global.
- Novo método `remove_all()`.
- Migração automática de v1 ao carregar JSON: entradas com razão `[SERIE]` → `y_col="*"`; demais → mantém `y_col` específico armazenado.
- `_save` grava `"version": 2`.

### `preview_plot_tab.py` — três correções

- `_render_preview`: passa `y_col=y_col` para `apply_exclusions` (antes não passava).
- `_prompt_series_exclusion`: exclusão de série usa `y_col="*"` (antes usava o y_col do plot ativo, causando bleeding para outros plots).
- `_open_exclusions_review`:
  - **Restore All**: botão com confirmação que chama `store.remove_all()`.
  - **Fix row-shift**: tabela reconstruída a cada restore via `_rebuild()` em vez de `table.removeRow(i)` com índice fixo. Elimina o bug de linhas erradas sendo removidas em sessões de restauração múltipla.
  - **Render imediato**: cada restore individual dispara `QTimer.singleShot(0, self._render_preview)` para o plot atualizar sem fechar o diálogo.
  - Coluna "Detectado em" renomeada para "Escopo (y_col)"; mostra "GLOBAL" para entradas `"*"`.

## Por quê

O sistema de exclusões usava `(series_label, load_kw)` como chave — sem y_col. Isso causava **bleeding**: uma exclusão feita num plot de `Air_g_s` subia para `n_th_pct`, `NOx`, etc. O usuário relatou que pontos sumiam de plots onde não havia feito nenhuma exclusão, e ao restaurar um ponto o efeito aparecia em outros plots também.

O redesign com `y_col` no key resolve o isolamento. Exclusões de série inteira (`[SERIE]`) continuam sendo globais (y_col="*") porque representam "corrida ruim, dado inválido" — correto excluir de todos os plots. Exclusões de ponto único ficam restritas ao plot onde foram criadas.

O bug de row-shift era silencioso: ao restaurar múltiplos pontos sem fechar o diálogo, `table.removeRow(i)` usava o índice original (estático), enquanto a tabela já havia se contraído. A tabela exibia linhas erradas sendo removidas visualmente. O store estava correto, mas o feedback visual induzia o usuário a erros.

## Arquivos

- `src/pipeline_newgen_rev1/ui/point_exclusion.py` (modificado — redesign ExclusionKey + remove_all + apply_exclusions com y_col)
- `src/pipeline_newgen_rev1/ui/preview_plot_tab.py` (modificado — 3 correções no sistema de exclusões)

## Validação

- `python -m py_compile` → OK em ambos os arquivos
- `python -m unittest discover -s tests -p "test_*.py"` → 446 testes, 10 erros pré-existentes (bridges), sem regressão

## Pendências

- O JSON existente `point_exclusions.json` em `config/pipeline29_text/` será migrado automaticamente na primeira abertura da GUI (v1 → v2): [SERIE] → y_col="*", pontos únicos → y_col específico. O arquivo será regravado como v2 no próximo Save ou exclusão/restauração.
- Verificar comportamento de exclusões existentes de série (Air_g_s, T_E_COMP) após migração — devem continuar excluindo de todos os plots via y_col="*".
