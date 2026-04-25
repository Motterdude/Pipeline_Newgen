# 2026-04-25 — Arquitetura de 3 fases do pipeline

## Decisão

O pipeline de execução é dividido em **3 fases sequenciais obrigatórias**:

1. **CONFIG** — prepara o contexto (leitura de config, diretórios, preflight). Roda sempre.
2. **PROCESSING** — computa dados e exporta artefatos auditáveis (xlsx). Gated por feature flags.
3. **PLOTTING** — gera visualizações (PNGs) a partir de dados já prontos no contexto. Gated por feature flags.

## Princípio vinculante

**Toda conta antes de todo plot.** Nenhum stage da fase PLOTTING pode computar dados novos; ele apenas lê o que a fase PROCESSING depositou no `RuntimeContext` e renderiza. Nenhum stage da fase PROCESSING pode gerar PNGs.

## Consequências

1. **Tuplas de ordenação separadas**: `CONFIG_STAGE_ORDER`, `PROCESSING_STAGE_ORDER`, `PLOTTING_STAGE_ORDER`. A tupla `STAGE_PIPELINE_ORDER` é a concatenação das três.

2. **Feature-flag gating no runner**: o loop de PROCESSING e PLOTTING verifica `ctx.enabled_features` antes de executar cada stage. Stages desabilitados recebem log `[SKIP]`. Stages de CONFIG rodam sempre (não são gated).

3. **Nomenclatura de stages**: stages de processamento usam prefixo `compute_*` ou nome descritivo sem prefixo de plot. Stages de visualização usam prefixo `plot_*` ou `run_*_plots`.

4. **Auditabilidade**: como todo dado é computado e exportado (xlsx) antes dos plots, é possível auditar os resultados intermediários sem depender da renderização visual.

5. **Toggles individuais**: cada stage (compute ou plot) tem seu próprio `feature_key` e pode ser habilitado/desabilitado independentemente. Desabilitar `plot_compare_iteracoes` não afeta a exportação do xlsx de métricas; desabilitar `compute_compare_iteracoes` faz o plot stage receber `None` e pular silenciosamente.

6. **Stages existentes afetados**:
   - `run_time_diagnostics` foi split: compute+xlsx fica em PROCESSING, PNGs vão para `plot_time_diagnostics` em PLOTTING.
   - `run_compare_iteracoes` (bridge) foi substituído por `compute_compare_iteracoes` (PROCESSING) + `plot_compare_iteracoes` (PLOTTING).

## Motivação

O usuário pediu explicitamente: "O processamento de dados vem primeiro de tudo. Só plotamos dados processados para não ter etapas quebradas ou impossibilidade de auditar o ponto de conta. Todas as contas devem ser feitas antes de plotar, toda etapa deve ser auditável."

A arquitetura anterior (2 fases) misturava `export_excel`, `run_unitary_plots` e `run_compare_iteracoes` na mesma tupla `PROCESSING_STAGE_ORDER`, sem distinção entre o que computa dados e o que gera PNGs.
