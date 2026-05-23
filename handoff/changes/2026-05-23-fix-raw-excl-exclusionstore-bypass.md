# 2026-05-23 — fix-raw-excl-exclusionstore-bypass

## O que mudou

- `_render_preview` em `preview_plot_tab.py`: bloco `apply_exclusions` agora só executa quando `_active_source != "raw"`. Em modo raw, o filtro do ExclusionStore é completamente bypassed — os dados aparecem sem nenhuma filtragem, incluindo os pontos excluídos.

## Por quê

O toggle raw/excl não mostrava diferença visível por dois motivos que se somavam:

1. O ExclusionStore (`point_exclusions.json`) tem ADTV Sub 1 com `y_col="*"` (global), o que significa que `apply_exclusions` removia as 19 linhas de ADTV Sub 1 do raw_df da mesma forma que do excl_df. Raw(222) → 203, Excl(203) → 203: ambos saíam com 203 linhas.

2. Como resultado, `Air_kg_h` (e qualquer outra métrica) também "sumia" em raw porque os pontos de ADTV Sub 1 eram removidos pelo filtro de preview, mesmo que o usuário quisesse ver o dado original.

A semântica correta: `raw = dados originais, sem nenhum filtro`. O filtro de preview (ExclusionStore) só deve se aplicar ao modo padrão e ao modo excl (onde o usuário está analisando os dados filtrados interativamente).

## Arquivos

- `src/pipeline_newgen_rev1/ui/preview_plot_tab.py` (modificado — 1 guard em `_render_preview`)

## Validação

- `py_compile` → OK
- `unittest` → 446 testes, 10 erros pré-existentes
- Validação headless com dados reais:
  - active=raw: 222 linhas, ADTV Sub 1 presente (19 rows), Air_kg_h: 222 pontos ✓
  - active=excl: 203 linhas, ADTV Sub 1 ausente (0 rows), Air_kg_h: 203 pontos ✓

## Pendências

- Nenhuma.
