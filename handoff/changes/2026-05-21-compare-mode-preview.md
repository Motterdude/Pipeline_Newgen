# 2026-05-21 — compare-mode-preview

## O que mudou

- **Novo plot_type `compare_bl_vs_adtv`** no Preview Plot tab — visualização de compares BL vs ADTV com dual-panel (absoluto em cima, delta % embaixo).
- **Combos dedicados** "Metrica" e "Comparacao" no painel esquerdo (visíveis apenas no compare mode).
- **Auto-discover** do `compare_iteracoes_metricas_incertezas.xlsx` no diretório de output.
- **Navegação com setas** cicla entre métricas (11 disponíveis) dentro do compare mode.
- **Preset "Nanum Compare"** builtin para ativar o modo diretamente.
- **Guard de navegação** preserva plot_type `compare_bl_vs_adtv` quando Lock X está ativo.

## Por quê

O usuário quer visualizar os compares (média BL vs ADTV) diretamente no Preview Plot sem depender dos PNGs batch. O compare xlsx já está pronto (produzido pelo pipeline), e os renderers (`preview_renderers.py`) já existiam — faltava apenas a integração na GUI como plot_type separado.

## Arquivos

- `src/pipeline_newgen_rev1/ui/preview_plot_tab.py` (modificado — compare mode integration)

## Validação

- `py_compile` → OK
- `python -m unittest discover` → 445 testes, 0 regressão
- Smoke test com xlsx real: 600 rows, 11 métricas, 3 pares → rendering OK

## Status: NÃO FUNCIONOU COMO ESPERADO

Teste visual na GUI revelou problemas — não renderizou corretamente. Requer investigação e ajuste na próxima sessão.

## Pendências (prioridade para retomada)

- **Debug do rendering**: o dual-panel não apareceu como esperado. Possíveis causas: (1) cópia de linhas do fig_abs/fig_delta para o dual-panel perde errorbar containers, (2) auto-discover não encontrou o xlsx, (3) combos não popularam corretamente.
- **ErrorBar no dual-panel**: os renderers usam errorbar internamente, mas a cópia para dual-panel copia apenas linhas (`get_lines()`) sem as barras de erro. Precisa usar os renderers diretamente nos axes do dual-panel em vez de copiar artists.
- **Compare overlay**: adicionar opção de ver todas as 3 comparações sobrepostas (usa `render_compare_all_overlay`).
- **Investigar**: se o problema é no auto-discover, no rendering, ou na interação com outros modos (cursor/filter).
