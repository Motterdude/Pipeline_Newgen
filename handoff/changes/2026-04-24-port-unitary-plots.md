# 2026-04-24 — port-unitary-plots

## O que mudou

- Criado subpacote `runtime/unitary_plots/` com 5 módulos (~900 linhas):
  - `fuel_groups.py` — agrupamento por combustível (D85B15, E94H6, E75H25, E65H35) com filtro H2O e suporte a `series_col`.
  - `config_parsing.py` — parse de axis specs com conversão de unidades, resolução de incerteza (yerr), variantes with/without uncertainty, derivação de filenames/titles.
  - `renderers.py` — 3 renderers matplotlib: `plot_all_fuels` (scatter+errorbar), `plot_all_fuels_xy` (free-axis), `plot_all_fuels_with_value_labels` (com anotações box/tag/marker/badge).
  - `dispatch.py` — loop principal que itera `plots_df` e despacha para o renderer correto (suporta plot types: `all_fuels_yx`, `all_fuels_xy`, `labels`, `kibox_all`).
  - `__init__.py` — exporta `make_plots_from_config_with_summary`.
- Criada stage nativa `runtime/stages/run_unitary_plots.py` (`RunUnitaryPlotsStage`) que substitui `RunUnitaryPlotsBridgeStage`.
- Registry em `runtime/stages/__init__.py` atualizado: import nativo, bridge removida.
- 41 testes unitários adicionados em `tests/test_unitary_plots.py`.

## Por quê

`run_unitary_plots` era a penúltima bridge — gerava os plots unitários chamando `legacy.make_plots_from_config_with_summary()` no monolito de 10k linhas. Portar elimina essa dependência e traz todo o fluxo de geração de plots para dentro do pacote novo. Reutiliza funções já portadas (`resolve_col`, `_fuel_blend_labels`, constantes de combustível) sem duplicação. Simplifica removendo lógica de mestrado runtime (não usada neste projeto).

## Arquivos

- `src/pipeline_newgen_rev1/runtime/unitary_plots/__init__.py` (novo)
- `src/pipeline_newgen_rev1/runtime/unitary_plots/fuel_groups.py` (novo)
- `src/pipeline_newgen_rev1/runtime/unitary_plots/config_parsing.py` (novo)
- `src/pipeline_newgen_rev1/runtime/unitary_plots/renderers.py` (novo)
- `src/pipeline_newgen_rev1/runtime/unitary_plots/dispatch.py` (novo)
- `src/pipeline_newgen_rev1/runtime/stages/run_unitary_plots.py` (novo)
- `tests/test_unitary_plots.py` (novo)
- `src/pipeline_newgen_rev1/runtime/stages/__init__.py` (modificado — troca bridge → nativa)
- `handoff/stages_status.md` (modificado — run_unitary_plots 🟡→🟢, dispatcher 🔴→🟢)

## Validação

- `python -m unittest discover -s tests -p "test_*.py"` → **260 tests OK** (+41)
- `py_compile` de todos os módulos novos → OK
- Testes cobrem: fuel grouping (6), config parsing (11), uncertainty (8), renderers (7), dispatch (6), stage integration (3)

## Pendências

- Validação de paridade via `scripts/compare_cycle.py` com dados reais (pendrive não disponível agora). Esperado: 37/37 PNGs unitários byte-idênticos.
- Bridge `RunUnitaryPlotsBridgeStage` pode ser removida de `bridges/legacy_runtime.py` quando `RunCompareIteracoesBridgeStage` (última bridge) também for portada.
- Próximo passo: port nativo de `run_compare_iteracoes` (última bridge restante).
