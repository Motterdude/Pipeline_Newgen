# 2026-05-23 — fix-excl-duplicate-prompt-and-gui-logging

## O que mudou

1. **Exclusion list removida do Sweep/Load Helper**: combobox, botoes "Ver lista..." e "Browse...", persistencia e leitura no `main()` foram removidos. A exclusion list agora so eh perguntada no Point Filter dialog (ao clicar "Gerar Graficos").

2. **Log de erros persistente**: `gui_error.log` rotativo (2 MB x 3 backups) criado automaticamente no config dir ao abrir a GUI. Captura:
   - Excecoes nao-capturadas (traceback completo via `sys.excepthook`)
   - Warnings/errors do Qt (via `qInstallMessageHandler`) — inclui geometry warnings
   - Inicio e fim de sessao

3. **Dimensao fixa dos graficos (10x6 inches)**: todos os renderers (`plot_all_fuels`, `plot_all_fuels_xy`, `plot_all_fuels_with_value_labels`, `plot_all_fuels_delta_ref`) agora criam figuras com `figsize=(10, 6)`. O canvas do Preview Plot usa `tight_layout()` + `setMinimumSize(200, 120)` para nao empurrar o layout.

4. **Fix layout: canvas empurrando interface**: o canvas agora tem minimum size baixo (200x120) + `tight_layout()`. O painel esquerdo (controles) tem `setMaximumWidth(420)` para nunca ser empurrado para fora. Resolve o bug de "lado direito come os botoes e legenda" ao trocar de plot.

5. **Fix Y scale: workspace tem prioridade sobre plots.toml**: invertida a logica em `_populate_from_record` — agora a escala Y salva no workspace/session tem precedencia sobre os valores hardcoded no plots.toml. Antes, o plots.toml sempre ganhava se tivesse valores nao-vazios, ignorando o que o usuario tinha configurado via GUI e salvo no preset.

6. **Fix 0 kW no output: plot_point_filter agora filtra a final_table antes do export**: `ExportExcelStage` aplica `apply_plot_point_filter` usando `ctx.selected_plot_points` antes de escrever o `lv_kpis_clean.xlsx`. Pontos desmarcados no filtro (ex: 0 kW) nao aparecem mais no output nem no Preview Plot.

## Por que

- **Exclusion list 2x**: usuario era perguntado no Helper tab e novamente no dialog de pontos ao rodar — contra-producente e confuso. O dialog do Point Filter eh o ponto correto (momento da geracao dos graficos).
- **Log de erros**: crashes e warnings sumiam no terminal; sem trail para diagnostico post-mortem. Agora basta ler `gui_error.log`.
- **Dimensao dos graficos**: inconsistencia visual entre tipos de plot (default matplotlib 6.4x4.8 vs all_iterations 10x6) e graficos que mudavam de tamanho ao redimensionar a janela.

## Arquivos

- `src/pipeline_newgen_rev1/ui/legacy/pipeline29_config_gui.py` (modificado — remoção excl helper, adição logging)
- `src/pipeline_newgen_rev1/runtime/unitary_plots/renderers.py` (modificado — figsize=(10,6) nos 4 renderers)
- `src/pipeline_newgen_rev1/ui/preview_plot_tab.py` (modificado — tight_layout, min/max widths, Y scale priority fix)
- `src/pipeline_newgen_rev1/runtime/stages/export_excel.py` (modificado — aplica plot_point_filter antes do export)

## Validacao

- `py_compile` → OK (3 arquivos)
- `unittest` → 446 testes, 10 erros pre-existentes (bridges legadas), sem regressoes

## Pendencias

- Testar GUI manualmente para confirmar:
  - Helper nao tem mais exclusion list
  - Point Filter continua com prompt
  - `gui_error.log` criado ao abrir
  - Graficos com proporcao consistente
