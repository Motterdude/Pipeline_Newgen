# 2026-05-23 — fix-preview-plot-workspace-robustness

## O que mudou

### Fix 1 — Toggle "Aplicar excl." na barra superior
- `_setup_ui`: adicionado `QCheckBox("Aplicar excl.")` ao lado do botão "Exclusions..."; tooltip explica o comportamento.
- `_connect_signals`: conectado `chk_apply_exclusions.stateChanged` a `_on_apply_exclusions_toggled`.
- `_on_apply_exclusions_toggled`: novo handler — chama `_update_exclusions_checkbox_label` e `_schedule_render`.
- `_update_exclusions_checkbox_label`: novo método — atualiza o texto do checkbox com a contagem ativa (`"Aplicar excl. (19)"`) e pinta de laranja quando há exclusões e o filtro está ativo.
- `_render_preview`: o bloco `apply_exclusions` só executa se `chk_apply_exclusions.isChecked()` for True.
- `_restore_session_to_ui` e `_restore_one`/`_restore_all` no dialog: chamam `_update_exclusions_checkbox_label` para manter o label atualizado.

### Fix 2 — Double-click workspace: FULL REPLACE em vez de merge
- `_on_workspace_double_click`: substituído `self._session[key].update(data[key])` por RESET completo do `_session` ao template padrão, seguido de `_session[key] = data[key]` para cada chave presente no arquivo.
- Também reseta `_loaded_df`, `_loaded_path`, `_compare_df`, `_compare_path`, `_draft_overrides`, `_series_style_overrides` antes de `_restore_session_to_ui`.
- Efeito: cada workspace é um estado limpo e independente; y_scales, series_styles, comments e data paths de workspaces anteriores não contaminam o recém-carregado.

### Fix 3 — Browse limpa series_styles e draft_overrides
- `_browse_data_file`: após `load_data_from_file`, reseta `_series_style_overrides = {}`, `_session["series_styles"] = {}`, `_draft_overrides = {}`.
- Efeito: ao abrir um novo arquivo, estilos de cores/markers do arquivo anterior não persistem.

### Fix 4 — `_restore_session_to_ui` limpa `_loaded_df` antes de recarregar
- `_restore_session_to_ui`: seta `_loaded_df = None` e `_loaded_path = None` no início, antes de tentar carregar o path do workspace.
- Efeito: se o path do workspace não existir, o render usa o fallback (dados da GUI) em vez de exibir silenciosamente os dados do Browse anterior.

## Por quê

### Evidências coletadas (subagentes + dados reais):
- `exclusion_list_1.json`: 19 entradas, série "ADTV Sub 1", y_col="*", razão "[SERIE] vazão_de_ar_baixa" ✓
- `point_exclusions.json`: identicamente 19 entradas de "ADTV Sub 1" com y_col="*" (pós-migração v1→v2)
- `out_nanum_post_injector_fix_renamed_combustion_excl_list/lv_kpis_clean.xlsx`: **203 linhas, sem Subindo_Aditivado_1** ✓ — pipeline funcionou
- `out_nanum_post_injector_fix_renamed_combustion/lv_kpis_clean.xlsx`: **222 linhas, com Subindo_Aditivado_1** (arquivo pré-exclusão)

### Causa raiz dos bugs no Preview Plot (todos confirmados por análise de código):
1. **ExclusionStore bleeding** (Bug #2 do subagente): `_get_exclusion_store()` cria singleton a partir de `point_exclusions.json`. Ao carregar o arquivo antigo (222 linhas, tem ADTV Sub 1), `apply_exclusions` ainda filtrava a série porque `point_exclusions.json` retinha as exclusões. Resultado: ADTV Sub 1 desaparecia do arquivo antigo mesmo sem ter sido excluída lá.
2. **Workspace merge** (Bug #1): `dict.update()` em `_on_workspace_double_click` mesclava y_scales, series_styles, comments do workspace anterior no recém-carregado.
3. **Browse stale styles** (Bug #3): `_browse_data_file` não limpava `series_style_overrides`.
4. **Stale _loaded_df** (Bug #4): `_restore_session_to_ui` não resetava `_loaded_df` antes de recarregar.

## Arquivos

- `src/pipeline_newgen_rev1/ui/preview_plot_tab.py` (modificado — 4 fixes, ~80 linhas)

## Validação

- `python -m py_compile` → OK
- `python -m unittest discover` → 446 testes, 10 erros pré-existentes (bridges)

## Pendências

- Para o usuário: agora com o checkbox `Aplicar excl. (19)` desmarcado → ADTV Sub 1 aparece no arquivo antigo; marcado → filtrado.  Para comparar os dois arquivos limpos, use: (1) desmarque exclus., (2) Browse para o arquivo antigo, (3) ve a série.
