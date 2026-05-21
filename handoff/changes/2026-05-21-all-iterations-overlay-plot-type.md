# 2026-05-21 — all-iterations-overlay-plot-type

## O que mudou

- **`src/.../runtime/unitary_plots/renderer_all_iterations.py`** (novo) — renderer `plot_all_iterations()` que agrupa linhas do lv_kpis_clean.xlsx por identidade de série (campaign + sentido + iteração) e plota todas as curvas sobrepostas com cores por campanha (azul=BL, vermelho=ADTV) e markers por direção (o=subida, s=descida).
- **`src/.../ui/preview_plot_tab.py`** (modificado — 6 pontos cirúrgicos):
  1. Import do novo renderer.
  2. `"all_iterations_yx"` adicionado ao combo de plot_type.
  3. Preset builtin "Nanum All Iterations" (Load_kW 0-55, step 5, plot_type fixado).
  4. Guard de navegação: quando Lock X ativo E plot_type é `all_iterations_yx`, setas NÃO sobrescrevem o plot_type (preserva modo ao navegar entre métricas).
  5. Dispatch no `_call_renderer()` encaminha para `plot_all_iterations`.
  6. Auto-discover de dados quando preset builtin é selecionado sem dados carregados.
- **`src/.../ui/_backups/preview_plot_tab_2026-05-21.py`** (novo) — cópia de segurança antes das modificações.

## Por quê

O handoff anterior (revert-compare-mode-preview) removeu a tentativa de misturar compare mode no Preview Plot tab por instabilidade. O usuário quer a funcionalidade mais simples primeiro: **ver todas as iterações sobrepostas** (BL sub/des, ADTV sub/des) sem agregação nem deltas — apenas plotar os pontos raw do lv_kpis_clean.xlsx com cada dataset como curva separada.

Isso é conceitualmente distinto de "compare" (que requer agregação + propagação de incerteza + cálculo de delta). Aqui é apenas visualização direta: Y vs Load_kW, uma curva por série, cores e símbolos distinguem a qual campanha/direção/iteração pertence.

O preset e o guard de navegação garantem que o modo persista ao navegar entre métricas (setas mudam Y, mas não saem do all_iterations), sem afetar os fluxos existentes (mestrado, Lambda Sweep, etc.).

## Arquivos

- `src/pipeline_newgen_rev1/runtime/unitary_plots/renderer_all_iterations.py` (novo — ~160 linhas)
- `src/pipeline_newgen_rev1/ui/preview_plot_tab.py` (modificado — +27 linhas, -7 linhas)
- `src/pipeline_newgen_rev1/ui/_backups/preview_plot_tab_2026-05-21.py` (novo — backup)

## Validação

- `python -m py_compile` nos dois arquivos → OK, sem erros.
- `python -m unittest discover -s tests -p "test_*.py"` → **445 testes**, 10 errors pré-existentes (bridges mortas), **zero regressão** introduzida.
- Smoke test com DataFrame sintético (4 séries × 10 loads): renderer retorna Figure com 4 curvas, labels corretas (`BL Sub 1`, `BL Des 1`, `ADTV Sub 1`, `ADTV Des 1`).
- Smoke test de fallback (DataFrame sem BaseName): renderer delega para `plot_all_fuels()` sem crash.
- AST parse do preview_plot_tab.py: 29 top-level nodes, sem erros de sintaxe.

## Pendências

- **Teste visual na GUI**: rodar a GUI real (`launch-config-gui`), selecionar preset "Nanum All Iterations", carregar dados reais (`E:\out_Nanum_rev2\lv_kpis_clean.xlsx`), confirmar render visual e navegação com setas.
- **Próximo passo — compares**: com o overlay de iterações funcionando, o próximo passo será plotar deltas (absolutos e percentuais) e compares de média vs média — esses requerem os dados já processados por `compute_compare_iteracoes`, não apenas o lv_kpis_clean.xlsx direto.

---

## Adições na mesma sessão (2026-05-21, segunda rodada)

### Series Colors na top bar + persistência no preset
- Botão "Series Colors..." movido para a top bar (à direita do Reload).
- Cores/markers escolhidos são gravados dentro do user preset em `"series_styles": {...}`.
- Ao carregar um preset, series_styles são restaurados automaticamente.

### Y-scale memory (`y_scale_memory.json`)
- Novo arquivo `config/pipeline29_text/y_scale_memory.json` persiste escalas Y por y_col.
- Ao navegar entre plots, salva a escala atual e recarrega a escala memorizada para o novo y_col.
- Prioridade: record com escala explicita > memória > vazio (auto-scale).
- `editingFinished` nos campos Y-min/max/step dispara save na memória.

### Fix nan nos campos
- `_clean_nan()` limpa strings "nan"/"none"/"inf" para vazio ao popular campos.

### Fix glitch de step (ticks excessivos)
- Guard `_MAX_TICKS = 80` em `_apply_fixed_x/y/y_ax/x_ax` e `_apply_y_tick_step`: se step geraria > 80 ticks, ignora (auto-scale).
- Debounce de 700ms específico para campos `x_step` e `y_step` (vs 150ms para os demais).

### Arquivos adicionais modificados
- `src/pipeline_newgen_rev1/runtime/unitary_plots/renderers.py` (guard _MAX_TICKS em 5 funções)
