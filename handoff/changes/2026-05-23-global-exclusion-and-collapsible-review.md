# 2026-05-23 — global-exclusion-and-collapsible-review

## O que mudou

1. **Exclusoes agora sao globais**: quando um ponto eh excluido, ele some de TODOS os plots (nao so do plot onde foi criado). O campo `y_col` no JSON virou metadata puro — nao filtra mais. A key de exclusao passou de `(series_label, load_kw, y_col)` para `(series_label, load_kw)`.

2. **Review dialog com tree colapsavel (QTreeWidget)**:
   - Series completas (`[SERIE]`) aparecem colapsadas com seta expansivel, mostrando o numero de pontos
   - Pontos individuais aparecem no nivel raiz
   - Botao Restore por serie (remove todos os pontos da serie) ou por ponto individual
   - Informacoes de cada ponto filho (kW, basename) visiveis ao expandir

3. **Migracao do point_exclusions.json para v3**:
   - Todas as entries com y_col especifico convertidas para `y_col="*"` (global)
   - Deduplicacao por `(series_label, load_kw)`: 27 → 23 entries (4 duplicatas do ADTV Des 2 @ 0kW removidas)
   - Version bump: 2 → 3

## Por que

A logica anterior permitia excluir um ponto so de um plot (BSFC), mas nao de outros (CO, NOx...). Isso nao faz sentido fisico: se um ponto operacional eh instavel, a instabilidade afeta todas as metricas. O usuario tinha que repetir a mesma exclusao N vezes em N plots diferentes.

## Arquivos

- `src/pipeline_newgen_rev1/ui/point_exclusion.py` (reescrito — ExclusionKey 2-tuple, filtragem global, helpers series/point)
- `src/pipeline_newgen_rev1/ui/preview_plot_tab.py` (modificado — QTreeWidget no review dialog)
- `config/pipeline29_text/point_exclusions.json` (migrado — v3, deduplicado)

## Validacao

- `py_compile` → OK
- `unittest` → 446 testes, 10 erros pre-existentes, sem regressoes
- Migracao de dados: 27 → 23 entries (4 duplicatas consolidadas)

## Pendencias

- Testar visualmente o review dialog (tree expandivel)
- Confirmar que exclusoes previamente per-metric agora aparecem em todos os plots
