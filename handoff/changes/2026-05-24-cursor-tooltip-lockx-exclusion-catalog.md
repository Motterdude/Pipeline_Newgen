# 2026-05-24 — cursor-tooltip-lockx-exclusion-catalog

## O que mudou

### 1. Lock X inteligente por eixo
- `_populate_from_record`: Lock X agora so aplica entre plots que compartilham o MESMO eixo X. Se o plot tem x_col diferente (ex: Consumo_kg_h vs Load_kW), ignora o lock e usa o eixo do plot.
- Cada plot salva seu x_col/x_min/x_max/x_step no workspace per-y_col.

### 2. Cursor adaptativo (Exact match vs Interpolating)
- Deteccao automatica: >40 pontos X unicos = modo interpolating (cursor livre, interpola linearmente). <=40 = modo exact match (snap to nearest point).
- Header da tabela cursor mostra `[Exact match]` ou `[Interpolating]` + usa x_label do plot atual (nao mais "kW" hardcoded).
- No modo interpolating, cursor se move livremente (sem snap grid).

### 3. Hover tooltip sobre pontos (600ms delay)
- Passar mouse sobre um ponto por 600ms mostra tooltip color-coded com:
  Load_kW, SD Consumo, Rotacao + SD, T_E_TURB + SD, P_E_TURB + SD, P_COLETOR + SD
- Posicao: segue cursor real via QCursor.pos() + offset.
- Fonte: 15px. Desabilitado automaticamente no modo exclusion.
- Robusto: busca ponto mais proximo no espaco de tela (15px threshold).

### 4. Tabela cursor — formatacao
- Largura dinamica (min 180, max 320px). Coluna valor com ResizeToContents.
- Font size do campo `edit_cursor_font` aplicado ao inicializar e ao restaurar preset.

### 5. Exclusoes robustas — match por BaseName
- `apply_exclusions`: agora faz match PRIMARIO por BaseName (identificador unico absoluto). Funciona independente de plot_type, x_col, ou series_label.
- Fallback por (series_label, Load_kW) para casos sem BaseName.
- Fix critico: antes, exclusoes nao funcionavam em plots com x_col != Load_kW (Consumo vs T_E_TURB).

### 6. GUI limpa — campos escondidos
- Filter H2O, Series col, Label variant: widgets hidden (funcionalidade rodando internamente com valores default/salvos).

### 7. Plots helper — catalogo completo + busca sem acento
- Catalogo de variaveis puxa de `_loaded_df`, `_excl_df` ou `_raw_df` (o que existir).
- Filtro do VariableSelectorDialog normaliza acentos (NFKD). Buscar "rotacao" encontra "Rotacao".

### 8. plot_type expandido + session mode sticky
- Opcoes no helper: adicionados `all_iterations_yx` e `all_fuels_delta_ref`.
- `active_mode` do workspace preservado ao navegar (nao resetado pelo record do plots.toml).

### 9. Sync Preview <-> Plots table
- Trocar x_col/y_col no Preview (via completer ou browse) auto-preenche labels e propaga para Plots table.
- Save no Preview salva workspace JSON + plots.toml simultaneamente.

### 10. Performance — lazy loading
- Startup carrega apenas 1 xlsx (o ativo). Outros lazy-loaded on demand via `_get_effective_df`.

## Arquivos

- `src/pipeline_newgen_rev1/ui/preview_plot_tab.py` (maior parte das features)
- `src/pipeline_newgen_rev1/ui/point_exclusion.py` (match por BaseName)
- `src/pipeline_newgen_rev1/ui/legacy/pipeline29_config_gui.py` (catalogo, busca sem acento, plot_type options)

## Validacao

- `py_compile` OK em todos os .py
- `unittest` 446 testes, 10 erros pre-existentes, sem regressoes
- Teste direto: `apply_exclusions` com x_col=Consumo remove o ponto corretamente

## Pendencias

- Testar visualmente tooltip, Lock X cross-axis, interpolating cursor
- Monitorar gui_error.log para issues pos-sessao
