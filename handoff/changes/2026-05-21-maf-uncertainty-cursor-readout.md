# 2026-05-21 — maf-uncertainty-cursor-readout

## O que mudou

### 1. Plot MAF com incerteza sd_of_windows
- Nova entrada `maf_vs_power_all.png` no plots.toml com `y_col = MAF_mean_of_windows` e `yerr_col = MAF_sd_of_windows`.
- Mostra a dispersão (±1σ) da leitura do sensor MAF sem componente instrumental (que não está disponível).
- Permite investigar diferenças não justificadas na vazão de ar entre iterações.

### 2. Cursor vertical interativo com tabela de valores
- Botão "Cursor" na top bar (checkable toggle).
- Ao ativar: linha vertical tracejada aparece no gráfico.
- Clique ou arraste com mouse esquerdo → linha segue o cursor.
- Tabela abaixo do canvas mostra o valor interpolado (1 casa decimal) de CADA série na posição X do cursor.
- Header da tabela mostra "@ X.X kW" atualizado em tempo real.
- Performance: usa `set_xdata` + `draw_idle` (não re-renderiza o plot inteiro).
- Ao desativar: linha e tabela somem.

### 3. Dropdown "Y browse" de colunas numéricas
- Novo combo "Y browse:" no painel esquerdo (abaixo de Y col).
- Lista TODAS as colunas numéricas do DataFrame carregado.
- Ao selecionar: preenche automaticamente o campo Y col e dispara render.
- Permite plotar qualquer variável sem depender de records pré-configurados no plots.toml.
- Atualiza automaticamente quando dados são carregados (`_refresh_column_completers`).

## Por quê

O usuário investiga diferenças de vazão de ar entre iterações (baseline 1 vs 2 vs 3) com pressões de coletor similares. Precisa de:
1. Visualizar MAF com dispersão para avaliar se diferenças estão dentro do ruído.
2. Comparar valores exatos entre curvas em pontos específicos de carga (cursor readout).
3. Explorar rapidamente qualquer variável do dataset sem configurar plots.toml previamente.

## Arquivos

- `config/pipeline29_text/plots.toml` (modificado — nova entrada MAF)
- `src/pipeline_newgen_rev1/ui/preview_plot_tab.py` (modificado — cursor + Y browse)

## Validação

- `py_compile` → OK
- `python -m unittest discover` → 445 testes, 0 regressão
- AST parse → 31 nodes, sem erro de sintaxe
- Smoke test np.interp → valores corretos em pontos intermediários

### 4. Layout da cursor table à direita do canvas
- Tabela posicionada à DIREITA do canvas (horizontal, não abaixo).
- Compacta: min 180px, max 260px de largura, font-size 10px, row height 20px.
- Cada linha mostra ícone colorido com marker shape (circle/square/diamond/triangle) + label + valor.
- Ícone desenhado via QPainter com a cor real da série no matplotlib.
- Header vertical oculto para economizar espaço.

## Pendências

- **Teste visual na GUI**: confirmar que cursor move suavemente, tabela atualiza em tempo real, e Y browse popula corretamente.
- **Interação cursor + exclusion mode**: se ambos ativos, pick event pode conflitar com cursor move. Resolver se ocorrer (provavelmente não — pick é por proximidade a ponto, cursor é em qualquer lugar).
- **Blitting optimization**: se performance do cursor não for satisfatória com muitas séries, implementar canvas blitting (salvar background, restaurar + redraw só a linha). Para agora, draw_idle deve ser suficiente.
