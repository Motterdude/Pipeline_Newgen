# 2026-05-21 — Revert Compare Mode no Preview Plot Tab

## Resumo

Tentativa de adicionar modo compare (Nanum: baseline vs aditivado, subida/descida/media) ao Preview Plot tab foi revertida. A implementação introduzia bugs no fluxo normal (Load_kW e Lambda Sweep) e não atingiu estabilidade suficiente para uso.

## O que foi tentado

1. **Compare mode com 4 plot types**: compare_absolute, compare_delta_pct, compare_all_overlay, compare_delta_all_overlay
2. **Auto-discover de compare data**: busca automática do `compare_iteracoes_metricas_incertezas.xlsx`
3. **Preset guard**: proteger compare mode quando presets regulares eram selecionados
4. **Auto-scale on browse**: detecção automática de range do eixo X ao carregar novos arquivos
5. **Default X-axis**: Load_kW 0-50 step 5 como default para compare mode

## Problemas encontrados

- **Crash ao navegar**: `_populate_from_record()` mudava `combo_plot_type` incondicionalmente, saindo de compare mode ao usar setas
- **X-axis instável**: auto-scale lutava com valores de plot records do plots.toml (Lambda sweep x_col sobrescrevia Load_kW)
- **Presets conflitantes**: presets do mestrado (Lambda) aplicados sobre dados de Nanum (Load_kW) causavam visualizações erradas
- **Complexidade acumulada**: cada fix introduzia efeitos colaterais em outros fluxos (startup, browse, navigate, preset apply)

## Decisao

Revertido `preview_plot_tab.py` e `pipeline29_config_gui.py` para commit `60adc25` (2026-05-17) — última versão estável com:
- Load (kW) preset funcional
- Lambda Sweep preset funcional  
- Spark Sweep preset funcional
- Salvamento de presets de usuario funcional
- Auto-discover do lv_kpis_clean.xlsx mais recente
- Sem qualquer codigo de compare_iteracoes

## Arquivo não importado preservado

`src/pipeline_newgen_rev1/runtime/compare_iteracoes/preview_renderers.py` continua no repositório (untracked) com os renderers de compare prontos para uso futuro. As funções são independentes e testadas:
- `load_compare_xlsx()`
- `available_metrics()` / `available_comparacoes()`
- `render_compare_absolute_preview()`
- `render_compare_delta_preview()`
- `render_compare_all_overlay()`
- `render_compare_delta_all_overlay()`

## Proximos passos (alternativas para compare mode)

Ideias para reimplementar de forma mais limpa:

1. **Aba separada** — em vez de misturar compare com o preview de plots unitários, criar uma aba dedicada "Compare" que não compartilha estado com a aba Preview Plot
2. **Modo exclusivo** — ao entrar em compare, desabilitar completamente o plot selector e navigation arrows (não faz sentido navegar entre plot records em compare mode)
3. **Workflow linear** — Browse compare XLSX → selecionar metrica → selecionar par → renderizar. Sem interação com presets/records de plots unitarios
4. **Dados separados** — não misturar `_loaded_df` (unitarios) com `_compare_df` no mesmo widget

## Estado atual do repositório

```
git status:
  ?? src/pipeline_newgen_rev1/runtime/compare_iteracoes/preview_renderers.py  (untracked)
  Nenhuma modificação tracked
```

Tudo limpo em `main`, HEAD em `60adc25`.
