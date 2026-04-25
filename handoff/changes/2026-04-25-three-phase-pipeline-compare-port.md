# 2026-04-25 — three-phase-pipeline-compare-port

## O que mudou

- **Reestruturação em 3 fases**: o pipeline passa de 2 fases (CONFIG + PROCESSING misturado) para 3 fases claras: CONFIG → PROCESSING (só dados/export) → PLOTTING (só visualização). `PROCESSING_STAGE_ORDER` agora contém apenas estações de computação e export; `PLOTTING_STAGE_ORDER` é nova e contém apenas renderers.
- **Feature-flag gating no runner**: o loop de PROCESSING e PLOTTING agora pula stages desabilitados em `ctx.enabled_features` com log `[SKIP]`. CONFIG stages continuam rodando sempre.
- **Split de `run_time_diagnostics`**: a parte de PNGs (20 arquivos) foi extraída para um novo `PlotTimeDiagnosticsStage` (feature_key=`plot_time_diagnostics`) na fase PLOTTING. O stage original fica só com compute + xlsx export.
- **Port nativo de compare_iteracoes**: o antigo `run_compare_iteracoes` (bridge 🟡) foi substituído por dois stages nativos:
  - `compute_compare_iteracoes` (PROCESSING): subpacote `runtime/compare_iteracoes/` com 9 módulos — specs, prepare (campaign/direction extraction, uncertainty col resolution), aggregate (GUM §F.1.2.4 com uB correlacionado), series (6 frames), delta (propagação GUM §5 via uc direto, significância 95%), core (orchestrador), plot_absolute, plot_delta. Exporta `metricas_incertezas.xlsx`.
  - `plot_compare_iteracoes` (PLOTTING): lê `ctx.compare_iteracoes_series` e gera PNGs absolutos + delta.
- **Feature flags atualizados**: `run_compare_iteracoes` removido; 3 novos keys adicionados (`compute_compare_iteracoes`, `plot_compare_iteracoes`, `plot_time_diagnostics`). Total de features: 20 (era 18).
- **Testes**: +35 novos testes cobrindo specs, prepare, aggregate (incluindo uB correlacionado e uc fallback), delta (incluindo métricas derivadas sem uA/uB), series, core end-to-end, stage registry e separação de fases.

## Por quê

O usuário pediu uma regra arquitetural clara: **toda conta antes de todo plot**. O cálculo de delta com incertezas do compare_iteracoes é processamento de dados, não visualização. Além disso, cada etapa deve ser auditável e individualmente habilitável/desabilitável.

A arquitetura anterior misturava `export_excel`, `run_unitary_plots` e `run_compare_iteracoes` na mesma tupla `PROCESSING_STAGE_ORDER`, sem distinção entre o que computa dados e o que gera PNGs. O `run_time_diagnostics` também misturava compute+xlsx+PNGs num único stage.

A reestruturação em 3 fases resolve isso: CONFIG prepara o contexto, PROCESSING computa e exporta dados auditáveis, PLOTTING gera visualizações a partir de dados já prontos. O feature-flag gating no runner dá o toggle explícito que o usuário pediu.

## Arquivos

- `src/pipeline_newgen_rev1/runtime/compare_iteracoes/__init__.py` (novo)
- `src/pipeline_newgen_rev1/runtime/compare_iteracoes/specs.py` (novo)
- `src/pipeline_newgen_rev1/runtime/compare_iteracoes/prepare.py` (novo)
- `src/pipeline_newgen_rev1/runtime/compare_iteracoes/aggregate.py` (novo)
- `src/pipeline_newgen_rev1/runtime/compare_iteracoes/series.py` (novo)
- `src/pipeline_newgen_rev1/runtime/compare_iteracoes/delta.py` (novo)
- `src/pipeline_newgen_rev1/runtime/compare_iteracoes/core.py` (novo)
- `src/pipeline_newgen_rev1/runtime/compare_iteracoes/plot_absolute.py` (novo)
- `src/pipeline_newgen_rev1/runtime/compare_iteracoes/plot_delta.py` (novo)
- `src/pipeline_newgen_rev1/runtime/stages/compute_compare_iteracoes.py` (novo)
- `src/pipeline_newgen_rev1/runtime/stages/plot_compare_iteracoes.py` (novo)
- `src/pipeline_newgen_rev1/runtime/stages/plot_time_diagnostics.py` (novo)
- `src/pipeline_newgen_rev1/runtime/stages/__init__.py` (modificado — 3 tuplas, 13 stages)
- `src/pipeline_newgen_rev1/runtime/stages/run_time_diagnostics.py` (modificado — removida parte de PNGs)
- `src/pipeline_newgen_rev1/runtime/runner.py` (modificado — 3 loops + feature gating)
- `src/pipeline_newgen_rev1/runtime/context.py` (modificado — +3 campos compare_iteracoes)
- `src/pipeline_newgen_rev1/workflows/load_sweep/feature_flags.py` (modificado — +3 features, -1)
- `tests/test_compare_iteracoes.py` (novo — 35 testes)
- `tests/test_feature_flags.py` (modificado — refs atualizadas)
- `tests/test_orchestrator.py` (modificado — refs atualizadas, total_steps=20)

## Validação

- `python -m unittest discover -s tests -p "test_*.py"` → **295 testes OK** (+35 novos)
- Import smoke: `from pipeline_newgen_rev1.runtime.compare_iteracoes import compute_compare_iteracoes` → OK
- `show-plan --mode load` → mostra 3 fases (processing/export/plotting) com separação correta
- Nenhum diretório operacional tocado

## Pendências

- **Paridade end-to-end**: rodar `scripts/compare_cycle.py` com dados reais (`raw_NANUM`) para confirmar que `metricas_incertezas.xlsx` e PNGs do newgen batem com o legado.
- **OneDrive sync**: copiar `src/` e `config/` para a cópia operacional antes do próximo Save & Run.
- **Bridge morta**: `RunCompareIteracoesBridgeStage` ainda existe em `bridges/legacy_runtime.py` mas não é mais importada por ninguém. Pode ser deletada quando todas as bridges saírem.
- **Decisão 3 fases**: formalizar como decisão arquitetural em `handoff/decisions/` se aprovada como regra permanente.
