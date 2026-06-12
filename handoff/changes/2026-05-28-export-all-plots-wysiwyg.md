# 2026-05-28 — export-all-plots-wysiwyg

## O que mudou

Export All Plots agora exporta **exatamente o que o usuário vê no preview** (WYSIWYG), corrigindo 3 bugs:

### 1. Combustível errado (fuels_override ignorado)

`plot_all_iterations` recebia `fuels_override` mas não filtrava o DataFrame.
Agora aplica `fuel_plot_groups()` antes de iterar pelas séries de iteração,
removendo do plot quaisquer combustíveis não listados em `filter_h2o_list`.

### 2. Deltas do compare não exportavam

O export não tinha caminho para records `compare_bl_vs_adtv`. Novo método
`_export_compare_plots(plot_dir)` itera todas as métricas do `_compare_df`
e gera um PNG por métrica (`compare_delta_{metrica}.png`), respeitando o
filtro de par (media/subida/descida) e a flag de incerteza.

Records `all_fuels_delta_ref` em modo `all_iterations_yx` são redirecionados
para o renderer de iterações (consistente com o preview).

### 3. Escalas erradas no export (y_scales da sessão ignorados)

O export usava apenas valores do `plots.toml`, ignorando ajustes que o
usuário fez no preview (guardados em `self._session["y_scales"]`).
Agora faz merge: `y_scales[y_col]` tem prioridade sobre o record base —
mesma lógica de `_populate_from_record`. Inclui: y_min/y_max/y_step,
x_min/x_max/x_step, show_uncertainty, y_tol_plus/y_tol_minus.

Adicionado `_sync_ui_to_session()` antes do export para capturar o estado
mais recente da UI.

### Lógica de modo ativo

O export agora lê `self.combo_plot_type.currentText()` (o modo que o usuário
está visualizando). Se = `all_iterations_yx`, redireciona records
`all_fuels_yx`, `all_fuels_delta_ref` para usar `plot_all_iterations` com
`style_overrides`. Records `compare_bl_vs_adtv` seguem caminho próprio
independente do modo.

## Por quê

O usuário exportava e recebia plots agrupados por combustível (modo antigo)
em vez dos plots separados por iteração/campanha que via ao vivo. Escalas
customizadas na sessão eram perdidas no export.

## Arquivos

| Arquivo | Mudança |
|---|---|
| `src/pipeline_newgen_rev1/ui/preview_plot_tab.py` | `_export_all_plots` reescrito; novo `_export_compare_plots`; merge y_scales |
| `src/pipeline_newgen_rev1/runtime/unitary_plots/renderer_all_iterations.py` | `plot_all_iterations` agora filtra por `fuels_override` via `fuel_plot_groups` |

## Validação

- `py_compile` OK em ambos os arquivos
- 546 testes: 536 pass, 10 erros pré-existentes (bridge tests sem legacy)
- Teste manual de `fuels_override` em `plot_all_iterations`: filtro reduz séries corretamente

## Pendências

- Testar Export All na GUI com dados reais (NANUM) para confirmar visualmente
- Verificar se `_auto_discover_compare_xlsx` encontra o arquivo na configuração Mestrado
