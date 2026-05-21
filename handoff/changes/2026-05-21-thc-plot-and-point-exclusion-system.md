# 2026-05-21 — thc-plot-and-point-exclusion-system

## O que mudou

### 1. THC ppm plot adicionado ao plots.toml
- Nova entrada `thc_vs_power_all.png` com `y_col = THC_mean_of_windows` seguindo padrão de CO/NOx/O2 ppm.
- Corrige lacuna: todas as emissões raw (ppm) agora têm plot definido.

### 2. Sistema de exclusão interativa de pontos
- **`src/.../ui/point_exclusion.py`** (novo) — módulo completo:
  - `PointExclusion` dataclass com series_label, load_kw, reason, timestamp
  - `ExclusionStore` com persistência JSON (add/remove/query)
  - `apply_exclusions()` filtra DataFrame por (series_label, load_kw) global
  - Persiste em `config/pipeline29_text/point_exclusions.json`

- **`src/.../ui/preview_plot_tab.py`** (modificado):
  - Botões "Exclude Points" (toggle) e "Exclusions..." na top bar
  - Pick event handler via `mpl_connect('pick_event', ...)` no canvas
  - Highlight com X vermelho no ponto selecionado
  - Dialog de justificativa obrigatória (QInputDialog)
  - Filtering global em `_render_preview()` antes do renderer
  - Review dialog com tabela e botão [Restore] por ponto

- **`src/.../runtime/unitary_plots/renderers.py`** (modificado):
  - `picker=5` em todos os `plt.plot()` e `plt.errorbar()` calls
  - Guard `_MAX_TICKS = 80` (da sessão anterior — já estava)

- **`src/.../runtime/unitary_plots/renderer_all_iterations.py`** (modificado):
  - `picker=5` nos plot/errorbar calls

### 3. Escopo da exclusão: GLOBAL
- Excluir um ponto remove de TODOS os gráficos (não só da variável onde foi detectado).
- O campo `y_col` é salvo como contexto ("detectado em NOx") mas o filtro aplica em todos.

## Por quê

O usuário precisa:
1. Ver THC em ppm (faltava no config original — oversight da migração).
2. Navegar gráficos, identificar outliers visualmente, e removê-los com justificativa de engenharia documentada. Pontos ficam no dataset original mas somem da visualização. Persistência entre sessões garante reprodutibilidade.

## Arquivos

- `config/pipeline29_text/plots.toml` (modificado — +22 linhas, nova entrada THC)
- `src/pipeline_newgen_rev1/ui/point_exclusion.py` (novo — ~110 linhas)
- `src/pipeline_newgen_rev1/ui/preview_plot_tab.py` (modificado — +120 linhas)
- `src/pipeline_newgen_rev1/runtime/unitary_plots/renderers.py` (modificado — picker=5)
- `src/pipeline_newgen_rev1/runtime/unitary_plots/renderer_all_iterations.py` (modificado — picker=5)

## Validação

- `py_compile` em todos os arquivos → OK
- `python -m unittest discover` → 445 testes, 0 regressão
- Smoke test ExclusionStore: add/remove/persist/reload/apply_exclusions → todos passam
- Smoke test apply_exclusions: DataFrame de 6 rows filtrado para 5 corretamente

## Pendências

- **Teste visual na GUI**: ativar "Exclude Points", clicar num ponto, confirmar dialog, verificar que some do plot.
- **Review dialog**: testar [Restore] e confirmar que ponto volta.
- **Batch export**: exclusões atualmente só aplicam no Preview — batch export (Save & Run) gera todos os pontos. Decidir se exclusões devem aplicar também no export.
- **Fuel-mode fallback**: se DataFrame não tem BaseName (mestrado com fuel_label), o filtro de exclusão pula. Pode ser expandido no futuro.
