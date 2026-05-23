# 2026-05-22 — unified-workspace-persistence

## O que mudou

### Compare Mode
- **Removido dual-panel** (absoluto+delta) que não funcionava. Agora renderiza UM plot por métrica com todos os pares sobrepostos via `render_compare_delta_all_overlay()`, com errorbars.
- **Y MIN/MAX/STEP funcional no compare**: `_apply_y_scale_to_fig()` e `_apply_x_scale_to_fig()` aplicam escalas pós-render.
- **Y scale per-metric**: ao trocar de métrica, salva escala anterior e restaura a nova do session state.
- **Browse detecta compare xlsx**: ao carregar xlsx com colunas "Metrica"/"Comparacao", popula `_compare_df` automaticamente.

### Persistência Unificada
- **Workspace único** (`preview_workspace.json`): substituídos 4 arquivos JSON fragmentados por um único arquivo com todo o estado.
- **Session state em memória** (`_session` dict): todo estado vivo na RAM — navegar entre plots/métricas/modos nunca perde dados.
- **Botão Save único**: um clique serializa session state inteiro. Remove "Save Preset" + "Apply Back".
- **Save As...**: salva workspace nomeado.
- **Lista de workspaces salvos**: QListWidget com duplo-clique para carregar.
- **Migração automática**: primeira abertura migra de `preview_presets.json` + `y_scale_memory.json` + `preview_comments.json`.
- **Restauração completa ao reabrir**: `_restore_session_to_ui()` recarrega dados, escalas, comentários, modo ativo, e dispara render.

### Comentários
- **Per-plot** (`_session["comments"]`): dict indexado por chave de plot (métrica ou y_col). Cada gráfico tem comentário independente.
- **Dialog rico** (`CommentDialog`): editor multi-linha, tamanho fonte, bold, itálico, cor, posição (4 cantos), botão Apply (sem fechar).
- **Botão "Comment..."** sempre visível no top bar (funciona para qualquer plot type).

### Navegação e Thumbnails
- **Scroll do mouse** sobre canvas ou strip navega entre plots/métricas instantaneamente.
- **Setas esquerda/direita** continuam funcionando.
- **Thumbnail strip** (painel 180px entre controles e canvas):
  - Mini-gráficos reais (linhas sem markers, DPI 150, fundo escuro).
  - Renderização lazy (1 thumbnail por tick de timer, não trava a GUI).
  - Cache em memória (só re-renderiza se dados mudam).
  - Highlight cyan no ativo, auto-scroll para manter visível.
  - Clique navega direto.
- **Render instantâneo** na troca de métrica: `_on_compare_metric_changed` chama `_render_preview()` direto sem debounce.
- **Refresh otimizado**: se a lista de métricas não mudou, só atualiza borda sem reconstruir widgets.

### Fixes de estabilidade
- **Timer order**: debounce timers criados ANTES de `_connect_signals` e `_restore_session_to_ui`.
- **`_populating` guard preservado**: `_load_compare_xlsx` e `_load_compare_from_df` usam `was_populating` pattern.
- **`_show_status` protegido**: guard `hasattr(self, "status")` no `Pipeline29ConfigEditor`.
- **`_remember_y_scale` removido**: substituído por escrita direta em `_session["y_scales"]`.
- **`_y_scale_memory` referência removida**: `_populate_from_record` usa `_session["y_scales"]`.

## Por quê

O sistema anterior era fragmentado (4 arquivos + 2 botões de save), causava perda de estado ao navegar, data paths errados ao recarregar, e Y scales que sumiam. O compare mode dual-panel nunca funcionou. O usuário queria: um Save, tudo persistido, nada perdido ao trocar de contexto, navegação fluida com previews visuais.

## Arquivos

- `src/pipeline_newgen_rev1/ui/preview_plot_tab.py` (modificado — refactor completo: ~1050 linhas alteradas)
- `src/pipeline_newgen_rev1/ui/legacy/pipeline29_config_gui.py` (modificado — guard `_show_status`)
- `config/pipeline29_text/preview_presets.json` (modificado — removido Y hardcoded)
- `config/pipeline29_text/y_scale_memory.json` (modificado — limpa entradas incorretas)
- `config/pipeline29_text/preview_workspace.json` (novo — workspace unificado)
- `config/pipeline29_text/preview_comments.json` (novo — legado migração)

## Validação

- `python -m py_compile` → OK em todos os .py
- `python -m unittest discover` → 445 testes, 10 erros pré-existentes (bridges)
- Smoke tests: workspace round-trip, Y scale apply, compare renderer, thumbnail rendering
- GUI: abre sem crash, Browse detecta compare, Save persiste, reabrir restaura, scroll navega

## Pendências

- Thumbnails para modo normal (all_iterations, all_fuels) — atualmente só compare gera mini-plots
- Avaliar gerar thumbnails com imagem real em background thread (QThread) para zero impacto
- Templates de eixo X (combo "X Preset") mantidos como helpers simples
- Point exclusions em arquivo separado (globais ao dataset)
