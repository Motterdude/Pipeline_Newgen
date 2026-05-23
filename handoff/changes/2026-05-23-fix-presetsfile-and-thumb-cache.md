# 2026-05-23 — fix-presetsfile-and-thumb-cache

## O que mudou

- `_get_exclusion_store`: substituiu chamada `self._presets_file_path()` (método removido na refatoração de 22/05) por `self._workspace_file_path()`.
- `_invalidate_thumb_cache`: adicionou `self._thumb_items_snapshot = []` para forçar reconstrução dos widgets de thumbnail ao trocar de dataset.

## Por quê

Após importar novos arquivos no tool e renderizar no Preview Plot, o tab exibia "Erro no render: object has no attribute '_presets_file_path'". O método `_presets_file_path` foi removido na refatoração do workspace unificado (2026-05-22), mas `_get_exclusion_store` ainda o referenciava. Como `_get_exclusion_store` é chamado em **todo** `_render_preview` (linha 2600), nenhum plot conseguia ser gerado.

O segundo problema era thumbnails travadas no compare anterior. `_invalidate_thumb_cache` limpava `_thumb_cache` mas não resetava `_thumb_items_snapshot`. Como `_refresh_thumbnails` só reconstrói widgets se `items != _thumb_items_snapshot`, quando o novo compare tinha as mesmas métricas do anterior o fast-path era tomado e os mini-plots não eram re-renderizados.

## Arquivos

- `src/pipeline_newgen_rev1/ui/preview_plot_tab.py` (modificado — 2 linhas)

## Validação

- `python -m py_compile src/pipeline_newgen_rev1/ui/preview_plot_tab.py` → OK
- `python -m unittest discover -s tests -p "test_*.py"` → 446 testes, 10 erros pré-existentes nos bridges (sem regressão)

## Pendências

- Sem pendências introduzidas por esta mudança.
