# 2026-05-23 — Sessão completa: GUI Preview Plot, exclusões, logging, performance

## Resumo da sessão

Sessão longa de refinamento intenso do Preview Plot e do workflow de configuração da GUI. Foram 8+ changes individuais consolidadas neste resumo. O foco foi: corrigir bugs de persistência (presets/workspace), melhorar UX de exclusões, adicionar logging, padronizar gráficos, e sincronizar o fluxo Plots↔Preview Plot.

---

## O que mudou (cronológico)

### 1. Fix η_th,ind — IMEPH→IMEPN
- `runtime/final_table/core.py`: eficiência térmica indicada usava IMEPH (gross, apenas compressão+expansão) em vez de IMEPN (net, inclui bombeamento). Corrigido: η_th,ind cai de ~41% para ~37.5%, η_mech sobe de 76% para 83%.

### 2. Exclusion list — prompt duplicado removido
- `ui/legacy/pipeline29_config_gui.py`: removido combobox de exclusion list do Sweep/Load Helper (ficava duplicado com o Point Filter dialog). Agora só aparece uma vez, no momento correto.

### 3. Log de erros persistente (gui_error.log)
- `ui/legacy/pipeline29_config_gui.py`: `_setup_gui_logging()` com RotatingFileHandler (2 MB × 3 backups), sys.excepthook para exceções não-capturadas, qInstallMessageHandler para warnings Qt.
- Arquivo: `config/pipeline29_text/gui_error.log`

### 4. Dimensão fixa dos gráficos (10×6 inches)
- `runtime/unitary_plots/renderers.py`: todos os `plt.figure()` e `plt.subplots()` agora com `figsize=(10, 6)`.
- `ui/preview_plot_tab.py`: canvas usa `tight_layout()` + `setMinimumSize(200, 120)` + `updateGeometry()`.

### 5. Fix layout — gráfico "saindo da tela"
- Canvas com `setMinimumSize(200, 120)` baixo + `updateGeometry()` após draw.
- Left panel com `setMaximumWidth(420)`.
- `tight_layout()` protegido com try/except.

### 6. Fix Y scale — workspace priority sobre plots.toml
- `_populate_from_record`: invertida prioridade — session/workspace ganha sobre plots.toml.
- Y scales agora salvam **per-plot**: y_min, y_max, y_step, x_col, x_min, x_max, x_step, show_uncertainty.
- Garante que escalas configuradas pelo user não se perdem ao navegar.

### 7. Fix 0 kW no output
- `runtime/stages/export_excel.py`: `ExportExcelStage` aplica `apply_plot_point_filter` antes de exportar lv_kpis_clean.xlsx. Pontos desmarcados no filtro de pontos não aparecem mais no output.

### 8. Exclusões globais (não per-plot) + review colapsável
- `ui/point_exclusion.py`: reescrito — ExclusionKey = (series_label, load_kw) sem y_col. Toda exclusão remove a linha de TODOS os plots.
- `ui/preview_plot_tab.py`: review dialog com QTreeWidget — séries completas colapsáveis com seta, pontos individuais no nível raiz.
- `config/pipeline29_text/point_exclusions.json`: migrado para v3, deduplicado (27→23 entries).

### 9. Dropdown do Plots tab com colunas KIBOX + auto-sync
- `ui/legacy/pipeline29_config_gui.py`:
  - Catálogo de variáveis puxa do DataFrame do Preview Plot (lv_kpis_clean.xlsx carregado).
  - `on_rows_changed` callback no plots_table → refresh_plot_selector() no Preview.
  - Sugestão de eixo (axis suggestion) com fallback para Preview Plot loaded_df.
  - `plot_type` options: adicionados `all_iterations_yx` e `all_fuels_delta_ref`.

### 10. Fix draft_overrides stale (mistura de plots)
- `refresh_plot_selector()` limpa `_draft_overrides` e preserva seleção por filename (não por índice numérico).

### 11. Fix workspace load — y_col vazio ao recarregar preset
- `_restore_session_to_ui`: chama `refresh_plot_selector()` + popula primeiro record se y_col vazio.
- Signal connections movidas para depois de `_load_initial_bundle()`.

### 12. Fix comentários indexados por plot
- `_populate_from_record`: ao navegar embora, salva comment do plot anterior por y_col. Ao entrar, restaura comment do novo y_col.

### 13. Sync Preview Plot ↔ Plots table ↔ Save
- `_on_axis_col_changed`: ao mudar x_col ou y_col (inclui seleção do completer), auto-preenche labels + sincroniza para Plots table.
- `_save_workspace`: agora chama `save_text_bundle()` (persiste plots.toml) + `_sync_current_to_plots_table()`.
- `active_mode` do workspace preservado ao navegar (não resetado pelo record do plots.toml).

### 14. Fix performance — lazy loading de xlsx
- `_restore_session_to_ui`: carrega apenas o xlsx ativo (excl ou raw). Os outros ficam lazy (path salvo, df=None, carregado on-demand no `_get_effective_df`).
- Compare só carrega se diferente do principal.

---

## Arquivos modificados (src)

| Arquivo | Natureza |
|---|---|
| `runtime/final_table/core.py` | Fix IMEPH→IMEPN |
| `runtime/stages/export_excel.py` | Aplica plot_point_filter antes do export |
| `runtime/stages/compute_trechos_ponto.py` | Exclusion list integration |
| `runtime/stages/compute_compare_iteracoes.py` | Compare sheet embedding |
| `runtime/unitary_plots/renderers.py` | figsize=(10,6) padronizado |
| `runtime/plot_point_filter.py` | Exclusion prompt no point filter |
| `runtime/runner.py` | Exclusion list from dialog integration |
| `runtime/context.py` | exclusion_list_path field |
| `ui/point_exclusion.py` | Reescrito — exclusões globais v3 |
| `ui/preview_plot_tab.py` | ~1800 linhas adicionadas/modificadas (a maior parte das features) |
| `ui/legacy/pipeline29_config_gui.py` | Logging, catalog, sync, exclusion removal |
| `adapters/open_to_csv.py` | Fix stale settings detection |

## Arquivos de configuração/dados

| Arquivo | Conteúdo |
|---|---|
| `config/pipeline29_text/point_exclusions.json` | Migrado para v3 (global, deduplicado) |
| `config/pipeline29_text/plots.toml` | Novos plots KiBox adicionados pelo user |
| `config/pipeline29_text/preview_workspace.json` | Workspace session state |
| `config/pipeline29_text/exclusion_list_1.json` | Exclusion list exportada |
| `config/pipeline29_text/*.json` | Workspaces nomeados |
| `config/pipeline29_text/gui_error.log` | Log de erros rotativo |

## Validação

- `py_compile` → OK em todos os .py
- `unittest` → 446 testes, 10 erros pré-existentes (bridges legadas), sem regressões
- Teste manual: GUI abre, presets carregam, plots renderizam, exclusões globais, escalas persistem

## Decisões arquiteturais desta sessão

1. **Exclusões são globais**: um ponto excluído some de todos os plots. y_col no JSON é metadata histórica.
2. **Workspace salva state completo per-plot**: y_scales dict agora inclui x_col, x/y min/max/step, show_uncertainty por y_col.
3. **Save no Preview = Save tudo**: workspace JSON + plots.toml + sync com Plots table.
4. **Lazy loading**: xlsx só é carregado quando efetivamente necessário (on-demand no _get_effective_df).
5. **Plot point filter afeta export**: pontos desmarcados não vão para lv_kpis_clean.xlsx.

## Pendências

- Testar em cenário completo: adicionar plot → configurar → salvar → fechar → reabrir → verificar tudo preservado.
- Monitorar gui_error.log para issues pós-sessão.
- O "sair da tela" pode persistir em edge cases — monitorar.
