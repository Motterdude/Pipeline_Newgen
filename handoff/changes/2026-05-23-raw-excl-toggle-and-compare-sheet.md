# 2026-05-23 — raw-excl-toggle-and-compare-sheet

## O que mudou

### Feature 1: Toggle Raw / Excl no Preview Plot

- `preview_plot_tab.py` — segunda barra de dados (Raw / Excl) com Browse Raw, Browse Excl, botões ↺ e combo "Ativo: [raw | excl]".
- 5 novos campos em `__init__`: `_raw_path`, `_raw_df`, `_excl_path`, `_excl_df`, `_active_source = "raw"`.
- `_session["data_source"]` expandido com `"raw_path"`, `"excl_path"`, `"active_source"`.
- `_get_effective_df()` reescrito com prioridade: raw_df → excl_df → loaded_df → fallback.
- Novos métodos: `_load_raw_excl_file`, `_browse_raw_file`, `_reload_raw_data`, `_browse_excl_file`, `_reload_excl_data`, `_on_active_source_changed`, `_sync_rawexcl_combo`.
- `_sync_ui_to_session()`: salva raw_path, excl_path, active_source.
- `_restore_session_to_ui()`: reseta `_raw_df`, `_excl_df` e restaura dos paths salvos; chama `_sync_rawexcl_combo`.
- `_on_workspace_double_click`: inclui reset de `_raw_df`, `_excl_df`, `_raw_path`, `_excl_path`.
- **Removido** `chk_apply_exclusions` (checkbox "Aplicar excl.") e seus handlers `_on_apply_exclusions_toggled`, `_update_exclusions_checkbox_label`. O `ExclusionStore` interativo continua funcionando normalmente.

### Feature 2: Sheet "compare" embutida no lv_kpis_clean.xlsx

- `compute_compare_iteracoes.py`: após salvar o arquivo separado `compare_iteracoes_metricas_incertezas.xlsx`, appenda o mesmo DataFrame como sheet `"compare"` no `lv_kpis_clean.xlsx` via `pd.ExcelWriter(..., mode="a", if_sheet_exists="replace")`. Usa `getattr(ctx, "lv_kpis_path", None)` para ser seguro se o stage export_excel não tiver rodado.
- `load_data_from_file()`: após carregar Sheet1, tenta `pd.read_excel(path, sheet_name="compare")`. Se existir com colunas `Metrica`/`Comparacao`, chama `_load_compare_from_df` automaticamente — sem Browse separado para compare.

## Por quê

O usuário identificou que o checkbox "Aplicar excl." não fazia sentido: ao carregar o arquivo já processado com exclusion list, não há como "des-aplicar" uma exclusão que aconteceu no pipeline. A abordagem correta é ter dois arquivos (raw e pós-exclusão) e alternar entre eles via toggle.

O compare mode até então exigia dois Browse manuais (lv_kpis + compare xlsx separado). Como ambos são gerados na mesma execução do pipeline, embedar o compare como segunda aba do lv_kpis_clean.xlsx elimina esse passo e torna o Preview Plot autossuficiente com um único arquivo.

## Arquivos

- `src/pipeline_newgen_rev1/ui/preview_plot_tab.py` (modificado — Feature 1 + Feature 2)
- `src/pipeline_newgen_rev1/runtime/stages/compute_compare_iteracoes.py` (modificado — Feature 2)

## Validação

- `python -m py_compile` → OK em ambos os arquivos
- `python -m unittest discover -s tests -p "test_*.py"` → 446 testes, 10 erros pré-existentes (bridges)
- Script headless de validação:
  - raw_df: 222 rows (com ADTV Sub 1) | excl_df: 203 rows (sem) → delta=19 ✓
  - toggle raw=222, excl=203 ✓
  - `_get_effective_df` com todos os 4 cenários de toggle ✓
  - `_load_raw_excl_file` com arquivo inexistente retorna False sem crash ✓
  - ExcelWriter append: Sheet1 intacta (203×699), compare sheet (612×29), Metrica+Comparacao presentes ✓
  - Auto-detect: `ValueError` ao ler sheet 'compare' ausente é capturado pelo try/except ✓

## Pendências

- Compare sheet só será embutida nos próximos runs do pipeline (próximo Save & Run). Os arquivos existentes não têm a aba; nesse caso o Preview Plot funciona como antes (sem compare auto-detect).
- Se o usuário quiser embutir retroativamente numa saída já gerada, pode rodar manualmente `pd.ExcelWriter(lv_kpis_path, mode="a")` ou simplesmente re-rodar o pipeline.
- Thumbnails do compare mode continuam sendo gerados somente para `compare_bl_vs_adtv` (pendência antiga).
