# 2026-05-17 — Preview Plot Tab + Workspace Presets + Sweep Binning Fix

## Resumo

Sessão com foco em três frentes:
1. **Nova aba "Preview Plot"** — renderização matplotlib inline na GUI para iterar visuais sem re-processar
2. **Sistema de presets/workspaces** — salva/carrega arquivo de dados + eixos + escalas por tipo de ensaio
3. **Fix sweep binning** — bug crítico na agregação que destruía bins em lambda sweep

---

## Mudanças Detalhadas

### 1. Preview Plot Tab (`src/pipeline_newgen_rev1/ui/preview_plot_tab.py`) — NOVO

Widget PySide6 completo (~1100 linhas) para preview inline de plots sem rodar o pipeline:

**Layout:**
- Painel esquerdo (controles) com QSplitter arrastável para ajustar largura
- Painel direito (FigureCanvasQTAgg) com renderização matplotlib
- Barra de progresso para export batch

**Funcionalidades:**
- Auto-discover do `lv_kpis_clean.xlsx` mais recente
- Debounce 150ms — editar qualquer campo re-renderiza automaticamente
- Navegação por setas (Left/Right) via eventFilter em TODOS os widgets filhos
- Draft state (`_draft_overrides`) — preserva edits ao navegar entre plots
- Checkbox "Show uncertainty bars" per-plot
- Checkbox "Lock X axis" — mantém X col/scale ao navegar
- Campo `series_col` para grouping customizado (sweep mode)
- QCompleter com MatchContains em todos os campos de coluna
- Copy to clipboard (PNG via QImage)
- Export single / Export All com progress bar
- Apply Back + Save Config — aplica TODOS drafts e persiste em disco

**Sistema de Presets/Workspaces:**
- Arquivo JSON persistido em `{config_dir}/preview_presets.json`
- Templates builtin (Load kW, Lambda Sweep, Spark Sweep) — apenas mudam eixo X, sem data_path
- Presets de usuário (workspaces completos) — salvam: arquivo de dados + todos os eixos + escalas + filtros
- ComboBox no topo para quick-apply (templates marcados com `[template]`)
- QListWidget embaixo com workspaces salvos — duplo-clique carrega dados + config de uma vez
- Save exige arquivo de dados carregado e mostra qual no dialog
- Delete funciona em qualquer preset do usuário

**Colunas corretas:**
- Lambda: `Motec_Exhaust Lambda_mean_of_windows` (com espaço, escala 0.95–1.35 step 0.05)
- Spark: `Motec_Ignition Timing_mean_of_windows` (step 2)

### 2. Renderers — `return_fig` parameter (`runtime/unitary_plots/renderers.py`)

Adicionado `return_fig: bool = False` como último param nas 4 funções de plot:
- `plot_all_fuels()`
- `plot_all_fuels_xy()`
- `plot_all_fuels_with_value_labels()`
- `plot_all_fuels_delta_ref()`

Quando `return_fig=True`: retorna `Figure` sem salvar em disco, sem `mkdir`. Nenhuma mudança de comportamento com default.

### 3. Matplotlib backend guard

Substituído `matplotlib.use("Agg")` top-level por guard condicional em:
- `runtime/unitary_plots/renderers.py`
- `runtime/fuel_colors.py`
- `runtime/knock_histogram.py`
- `runtime/time_diagnostics/plots.py`

```python
import matplotlib
if not matplotlib.get_backend():
    matplotlib.use("Agg")
```

Permite coexistência do backend QtAgg (GUI) com Agg (CLI headless).

### 4. GUI Wiring (`ui/legacy/pipeline29_config_gui.py`)

- Import e instanciação do `PreviewPlotTab` com todos os callbacks
- `get_config_dir=self._current_config_dir` para persistência de presets
- `QTimer.singleShot(200, self.preview_plot_tab.auto_discover_data)` para carga inicial
- Auto-sync: seleção na aba Plots → Preview carrega automaticamente
- `plot_scope="none"` no Save & Run exit (evita gerar PNGs ao rodar via .bat)

### 5. CLI — Save & Run sem plots (`cli.py`)

Adicionado `plot_scope="none"` na chamada `run_load_sweep()` após exit code do GUI Save & Run. O .bat agora só processa dados; PNGs são gerados via Export no Preview.

### 6. Sweep Binning Fix (`runtime/sweep_binning.py`)

**Bug:** `apply_sweep_binning()` recebia `x_col="Sweep_Value"` mas a coluna real no DataFrame pós-merge era `Sweep_Value_mean_of_windows_x` (sufixada pelo pandas merge). Resultado: bins vazios, todos os pontos de lambda/spark em NaN.

**Fix:** Nova função `_resolve_x_col()` que busca fallback hierárquico:
1. Coluna exata
2. `Sweep_Value` (base)
3. Sufixadas com `_mean` e `_x`
4. Qualquer sufixada

### 7. Agregação com Sweep_Value como groupby

**Arquivos:** `runtime/motec_stats.py`, `runtime/trechos_ponto/core.py`, `runtime/trechos_ponto/constants.py`

Adicionado `"Sweep_Value"` às listas de GROUP_COLS (TRECHOS e PONTO). Refatorado para usar `active_*_cols = [c for c in GROUP_COLS if c in df.columns]` — fallback graceful se a coluna não existir (ensaio de carga normal não tem Sweep_Value).

### 8. Config text atualizado

- `config/pipeline29_text/defaults.toml` — paths atualizados para raw/out atuais
- `config/pipeline29_text/metadata.toml` — timestamp atualizado
- `config/pipeline29_text/plots.toml` — edições de plots (campos ajustados via Apply Back)

---

## Arquivos Criados/Modificados

| Arquivo | Status |
|---------|--------|
| `src/pipeline_newgen_rev1/ui/preview_plot_tab.py` | **NOVO** |
| `src/pipeline_newgen_rev1/ui/legacy/pipeline29_config_gui.py` | Modificado |
| `src/pipeline_newgen_rev1/cli.py` | Modificado |
| `src/pipeline_newgen_rev1/runtime/unitary_plots/renderers.py` | Modificado |
| `src/pipeline_newgen_rev1/runtime/fuel_colors.py` | Modificado |
| `src/pipeline_newgen_rev1/runtime/knock_histogram.py` | Modificado |
| `src/pipeline_newgen_rev1/runtime/time_diagnostics/plots.py` | Modificado |
| `src/pipeline_newgen_rev1/runtime/sweep_binning.py` | Modificado |
| `src/pipeline_newgen_rev1/runtime/motec_stats.py` | Modificado |
| `src/pipeline_newgen_rev1/runtime/trechos_ponto/core.py` | Modificado |
| `src/pipeline_newgen_rev1/runtime/trechos_ponto/constants.py` | Modificado |
| `src/pipeline_newgen_rev1/runtime/final_table/core.py` | Modificado |
| `src/pipeline_newgen_rev1/runtime/stages/prepare_upstream_frames.py` | Modificado |
| `config/pipeline29_text/defaults.toml` | Modificado |
| `config/pipeline29_text/metadata.toml` | Modificado |
| `config/pipeline29_text/plots.toml` | Modificado |
| `handoff/changes/2026-05-17-preview-plot-tab-and-presets.md` | **NOVO** |
| `handoff/changes/2026-05-17-fix-sweep-binning-grouping.md` | **NOVO** |

---

## Dependências

Nenhuma dependência nova. Stack existente:
- PySide6 (já no ambiente)
- matplotlib (já no ambiente)
- pandas, numpy, openpyxl/calamine (já no ambiente)

---

## Como testar

1. **GUI Preview Plot:**
   ```
   Pipeline_Newgen.bat
   ```
   Aba "Preview Plot" entre "Plots" e "Knock Thresholds". Verificar:
   - Auto-load do xlsx mais recente
   - Navegação setas esquerda/direita
   - Debounce render ao editar campos
   - Lock X funciona ao navegar
   - Export All gera PNGs na pasta out

2. **Presets/Workspaces:**
   - Browse → carregar xlsx de carga → Save → "Load"
   - Browse → carregar xlsx de lambda → ajustar X → Save → "Lambda"
   - Duplo-clique entre "Load" e "Lambda" na lista embaixo troca dados + eixos

3. **Sweep binning:**
   ```
   python -m pipeline_newgen_rev1.cli run-load-sweep --aggregation-mode sweep
   ```
   Verificar que bins de lambda aparecem corretamente no lv_kpis_clean.xlsx

4. **CLI headless (backend Agg):**
   ```
   python -m pipeline_newgen_rev1.cli run-load-sweep --plot-scope all
   ```
   Verificar que PNGs são gerados normalmente sem erro de backend

---

## Riscos / Pontos de atenção

- Presets JSON é por máquina (paths absolutos). Se mover dados para outra pasta, presets ficam inválidos → mensagem de erro clara na status bar
- `series_col` em branco = agrupa por fuel (comportamento padrão). Preenchido = agrupa pela coluna indicada
- QSplitter não salva posição entre sessões (reset ao reabrir GUI)
