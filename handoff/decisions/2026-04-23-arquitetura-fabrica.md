# 2026-04-23 — arquitetura-fabrica

Status: ativa e vinculante.

## Decisão

A migração de `nanum_pipeline_29/30` para `pipeline_newgen_rev1` segue o modelo **fábrica**:

1. **Esteira (`RuntimeContext`)** — dataclass que carrega todo o estado mutável da execução (bundle, state, dirs, discovery, frames, artefatos, erros). Substitui o uso de variáveis globais e locais soltas que hoje existem no `runner.py` e no monolito legado.
2. **Estações (`runtime/stages/*.py`)** — uma estação por entrada em `LOAD_SWEEP_FEATURE_SPECS`. Cada estação tem assinatura `run(ctx: RuntimeContext) -> None` e altera somente o que lhe diz respeito no contexto.
3. **Plano da linha (`orchestrator.build_load_sweep_plan`)** — filtra o registro de estações pelo modo (`load` ou `sweep`) e pelas flags ativas. Passa a ser lido pelo runner (hoje só descreve).
4. **Runner (`runtime/runner.py`)** — loop curto: percorre o plano, chama a estação correspondente no registro, propaga o contexto. Não contém lógica de domínio.
5. **Galpão antigo (`src/pipeline_newgen_rev1/legacy_monoliths/`)** — cópia transitória dos arquivos do monolito legado (`nanum_pipeline_29.py`, `nanum_pipeline_30.py`, `kibox_open_to_csv.py`). Fica dentro do pacote para tornar o newgen autocontido.
6. **Janela de atendimento (`bridges/legacy_runtime.py`)** — wrappers que traduzem chamadas das estações ainda não portadas em chamadas ao galpão antigo, com assinatura igual à das estações nativas. Uma linha aqui = uma estação terceirizada.
7. **Tabela de âncoras (`bridges/legacy_pipeline30.py`)** — lista viva; cada entrada é removida quando a estação correspondente atinge paridade dentro do newgen.

## Princípio vinculante

**Paridade funcional total com `nanum_pipeline_29/30`.** Newgen não é uma versão diferente; é uma versão **mais limpa com as mesmas saídas**. Nenhuma estação pode ser considerada portada sem que sua saída bata (byte a byte, quando possível; ou numericamente dentro de tolerância em floats) com a do legado.

## Modos

- `load` é o default operacional. Herda todo o rigor do `pipeline29` (plot_scope, compare por config, compare_iteracoes expandido, plots especiais de carga).
- `sweep` é uma alternativa opt-in. Herda o fluxo do `pipeline30` (preflight + binning + seletor de duplicatas + reescrita do eixo de plot). Não substitui `load`; muda o recorte do processamento e dos plots quando ativada.

## Sequência de implementação

1. **Esteira + plano + registro** (`runtime/context.py` + `runtime/stages/*` + refatoração de `runner.py`). Não toca estações vermelhas. Testes verdes obrigatórios antes e depois.
2. **Bridge operacional** (`legacy_monoliths/` + `bridges/legacy_runtime.py` + estações terceirizadas para `build_final_table`, `run_unitary_plots`, `export_excel`). Primeira vez que Save & Run produz `lv_kpis_clean.xlsx` + plots reais dentro do newgen.
3. **Port por estação, uma por vez.** Ordem sugerida, por impacto operacional e facilidade de validar:
   1. `run_time_diagnostics`
   2. `build_final_table` (KPI aggregation + fuel properties + KiBox aggregation + airflow + emissions + ETA_V + machines + uncertainty)
   3. `export_excel`
   4. `run_unitary_plots` (dispatcher + primitives + unitary)
   5. `run_compare_plots`
   6. `run_compare_iteracoes`
   7. `run_special_load_plots`
   8. `apply_sweep_binning`
   9. `prompt_sweep_duplicate_selector`
   10. `rewrite_plot_axis_to_sweep`
   11. `parse_sweep_metadata`
4. **CLI completo** — `--plot-scope`, `--compare-iter-pairs`, `--config-source`, env vars.
5. **Limpeza** — remove `legacy_monoliths/` e `bridges/legacy_runtime.py` quando a última âncora sair de `bridges/legacy_pipeline30.py`.

## Regras de ouro

- Cada port de estação tem antes uma fixture mínima em `tests/fixtures/paridade/` e um `tests/test_parity_<stage>.py` comparando a saída newgen com a saída legado. Se não bater, não mescla.
- `load` nunca pode regredir enquanto `sweep` evolui. A feature flag `rewrite_plot_axis_to_sweep` só roda em `sweep`, por definição.
- GUI legada (`ui/legacy/`) permanece enquanto a reescrita não começa. Refactor de GUI é outra decisão futura.
- Nenhum `print` novo. Em nova estação, usar `logging` — ou ao menos um helper futuro central que substitua os `print` legados em bloco.

## Consequências

- Qualquer mudança que viole a paridade é tratada como bug, não como "melhoria".
- Qualquer tentativa de adicionar stage fora do registro (`LOAD_SWEEP_FEATURE_SPECS`) requer uma nova entrada no registro e justificativa em um `handoff/decisions/` posterior.
- Quando a migração fechar, este documento vira histórico e `handoff/stages_status.md` fica como única fonte de verdade.
