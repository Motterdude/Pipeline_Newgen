# 2026-05-24 — session2-compare-metrics-tolerance-fixes

## O que mudou

### 1. Compare metrics expandido (37 metricas)
- Adicionados ao `specs.py`: BSFC, n_th_ind, MFB_10_50 (novo), MFB_50_90 (novo), MFB_10_90, AI10, AI50, AI90, P_COLETOR, P_E_TURB, P_S_COMP, P_S_TURB, T_ADMISSAO, T_E_COMP, T_E_TURB, T_S_AGUA, T_S_COMP, T_S_TURB, APMAX, PMAX, AQMAX, RMAX, IMEPH, IMEPL, IMEPN, IMEPN_COV.
- Novos canais calculados em `final_table/core.py`: `MFB_10_50 = AI50 - AI10`, `MFB_50_90 = AI90 - AI50`.

### 2. Fix compare media com dados parciais
- `aggregate.py`: media agora aceita pontos de UMA direcao quando a outra nao existe (antes exigia sub E des). Merge `outer` + fallback para valor unico. Cargas como 40 kW (so descida ADTV) agora aparecem no compare media.

### 3. Tolerance lines redesenhado
- Campos `tol+` e `tol-` agora sao valores Y absolutos (coordenadas diretas, nao offsets do zero).
- Linhas vermelhas pontilhadas `dash_capstyle="butt"` (sem arredondamento).
- `_apply_tolerance_to_fig` chamado apos QUALQUER render (all_fuels, all_iterations, compare, kibox).
- Salvo per-plot no workspace (`y_tol_plus`, `y_tol_minus` na session y_scales).
- Restaurado ao navegar entre plots/metricas.

### 4. Fix titulo/label bleeding no compare
- Titulos no compare sao SEMPRE auto-gerados (`"Delta — {metric}"`) e nunca persistidos na session.
- Removidos 111 campos `title`/`x_label_compare`/`y_label_compare` stale do workspace.
- Elimina bug onde titulo de uma metrica contaminava outra ao navegar.

### 5. Compare pair toggle
- Combo "Comparacao:" com opcoes: Todos (overlay), Media vs Media, Subida vs Subida, Descida vs Descida.
- Filtro passado ao renderer via `comparacoes_filter`. Persistido como `compare.active_pair`.

### 6. Fix escalas compare perdidas ao trocar modo
- `_on_plot_type_changed`: ao entrar em compare, restaura y_min/y_max/y_step/tol da metrica ativa.
- `_on_compare_metric_changed`: salva scales+tol do metric anterior, restaura do novo.

### 7. Compare renderer aceita title/x_label/y_label da UI
- `render_compare_delta_all_overlay` agora recebe parametros opcionais `title`, `x_label`, `y_label`.
- Campos da UI sao passados ao renderer — user pode customizar titulo do compare.

### 8. Fix crash ao preencher escala parcialmente
- Guard `if 0 < n_ticks < 200` em `_apply_y_scale_to_fig` e `_apply_x_scale_to_fig`.
- Evita `np.arange` com milhoes de ticks quando min/max estao indefinidos.

### 9. Exclusion list dialog com quick-pick
- Ao clicar "Gerar Graficos" no point filter, mostra lista de exclusion lists do config_dir.
- Mostra nome + contagem de exclusoes. Double-click ou OK para selecionar.
- Botao "Browse outro..." para navegacao manual.

### 10. Fix Browse nao atualizando excl_path
- Browse principal agora atualiza `_raw_path`, `_excl_path` e `_loaded_path` simultaneamente.
- Resolve bug onde preset carregava xlsx antigo por excl_path stale.

### 11. Logging level corrigido
- Mudado de DEBUG para WARNING. Elimina flood de findfont que causava travamento.

### 12. Cursor table formatacao
- Largura dinamica (min 180, max 320px). Coluna valor ResizeToContents.
- Font size aplicado ao inicializar e restaurar preset.

### 13. Y-axis drag rescale
- Arrastar na margem Y cria selecao visual → aplica nice Y scale ao soltar.
- Steps granulares (1, 1.5, 2, 2.5, 3, 5, 10...). Divisor /8 para mais ticks.
- Botao ↩ (undo) para voltar escala anterior (stack ilimitado).
- Cursor muda para SizeVerCursor na zona Y e volta a ArrowCursor dentro do plot.

### 14. Hover tooltip com SD%
- SD percentual para todas as variaveis (Consumo, Rotacao, T_E_TURB, P_E_TURB, P_COLETOR).

### 15. GUI limpa (hidden fields) + Lock X per-axis + busca sem acento

## Arquivos

- `src/pipeline_newgen_rev1/runtime/compare_iteracoes/specs.py` (37 metricas)
- `src/pipeline_newgen_rev1/runtime/compare_iteracoes/aggregate.py` (media parcial)
- `src/pipeline_newgen_rev1/runtime/compare_iteracoes/preview_renderers.py` (title/labels params)
- `src/pipeline_newgen_rev1/runtime/final_table/core.py` (MFB_10_50, MFB_50_90)
- `src/pipeline_newgen_rev1/runtime/unitary_plots/renderers.py` (tolerance redesign)
- `src/pipeline_newgen_rev1/runtime/plot_point_filter.py` (excl list quick-pick dialog)
- `src/pipeline_newgen_rev1/ui/preview_plot_tab.py` (maior parte das features)
- `src/pipeline_newgen_rev1/ui/point_exclusion.py` (exclusion by BaseName)
- `src/pipeline_newgen_rev1/ui/legacy/pipeline29_config_gui.py` (logging, catalog, accent search)
- `tests/test_compare_iteracoes.py` (spec count update 11→37)
- `config/pipeline29_text/preview_workspace.json` (cleaned stale titles)

## Validacao

- `py_compile` OK
- `unittest` 446 testes, 10 erros pre-existentes, sem regressoes
- Verificado: compare output New_Metrics com 37 metricas corretas
- O2 especifico: confirmado que nao faz sentido fisico, nao criado

## Pendencias

- Re-rodar pipeline para efeito do fix de media parcial (40kW, 25kW, 10kW)
- Testar visualmente tolerance lines + compare pair toggle
