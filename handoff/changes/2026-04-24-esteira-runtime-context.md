# 2026-04-24 — esteira-runtime-context

## O que mudou

- Criado `src/pipeline_newgen_rev1/runtime/context.py` — dataclass `RuntimeContext` (esteira) com `from_kwargs` que empacota todos os parâmetros do `run_load_sweep` e reserva os slots que as estações preenchem (bundle, state, input/output dirs, selection, discovery, rows, errors, summary paths).
- Criado `src/pipeline_newgen_rev1/runtime/stages/_base.py` — protocolo `Stage` com `feature_key: str` e `run(ctx) -> None`, mais helper `stage_is_enabled`.
- Criado `src/pipeline_newgen_rev1/runtime/stages/__init__.py` — `STAGE_REGISTRY` (dict por feature_key) e `STAGE_PIPELINE_ORDER` (tupla, ordem de invocação).
- Criadas 3 estações nativas extraídas do corpo do antigo runner:
  - `stages/load_text_config.py` → `LoadTextConfigStage` (carrega `ConfigBundle`)
  - `stages/sync_runtime_dirs.py` → `SyncRuntimeDirsStage` (resolve `input_dir`/`output_dir`, aplica overrides, popula `feature_selection`/`enabled_features`)
  - `stages/show_runtime_preflight.py` → `ShowRuntimePreflightStage` (gated por `ctx.use_preflight`; atualiza `ctx.selection`)
- Reescrito `src/pipeline_newgen_rev1/runtime/runner.py` — agora é loop sobre `STAGE_PIPELINE_ORDER` + 4 helpers core não-feature-gated (`_finalize_runtime_state`, `_discover_and_read_inputs`, `_apply_plot_filter`, `_write_summary_artifacts`). Sem lógica de domínio dentro de `run_load_sweep`.
- Atualizado `src/pipeline_newgen_rev1/runtime/__init__.py` — re-exporta `RuntimeContext` além de `run_load_sweep`/`RuntimeExecutionResult`.
- Atualizado `handoff/stages_status.md` — infraestrutura (esteira, plano, registry, runner) marcada como 🟢.
- Criados 5 function_cards novos (`runtime_context`, `stages_registry`, `stage_load_text_config`, `stage_sync_runtime_dirs`, `stage_show_runtime_preflight`) e atualizado `runtime_runner.fnctx.md`.

## Por quê

A decisão arquitetural de 2026-04-23 (`handoff/decisions/2026-04-23-arquitetura-fabrica.md`) exige que o runner seja um loop sobre o plano do orchestrator e que cada feature do `LOAD_SWEEP_FEATURE_SPECS` vire uma estação com a mesma assinatura. Sem essa esteira, o Passo 2 (bridges para o galpão antigo) não tem onde plugar — cada estação bridge precisa do contrato `run(ctx)`.

Passo 1 é intencionalmente mínimo: 3 estações 🟢 que o runner já chamava inline são as únicas portadas; discovery, leitura de inputs e escrita do summary continuam inline como helpers privados (viram estações nomeadas nos passos seguintes, com fixtures de paridade). A mudança é **zero comportamento novo** — os 52 testes passam sem alteração.

## Arquivos

- `src/pipeline_newgen_rev1/runtime/context.py` (novo)
- `src/pipeline_newgen_rev1/runtime/stages/_base.py` (novo)
- `src/pipeline_newgen_rev1/runtime/stages/__init__.py` (novo)
- `src/pipeline_newgen_rev1/runtime/stages/load_text_config.py` (novo)
- `src/pipeline_newgen_rev1/runtime/stages/sync_runtime_dirs.py` (novo)
- `src/pipeline_newgen_rev1/runtime/stages/show_runtime_preflight.py` (novo)
- `src/pipeline_newgen_rev1/runtime/runner.py` (reescrito)
- `src/pipeline_newgen_rev1/runtime/__init__.py` (atualizado)
- `handoff/stages_status.md` (atualizado — infra 🟢)
- `handoff/function_cards/runtime_context.fnctx.md` (novo)
- `handoff/function_cards/stages_registry.fnctx.md` (novo)
- `handoff/function_cards/stage_load_text_config.fnctx.md` (novo)
- `handoff/function_cards/stage_sync_runtime_dirs.fnctx.md` (novo)
- `handoff/function_cards/stage_show_runtime_preflight.fnctx.md` (novo)
- `handoff/function_cards/runtime_runner.fnctx.md` (atualizado)

## Validação

- `python -m unittest discover -s tests -p "test_*.py"` → **52 testes, OK** (antes e depois).
- `compileall` do pacote `src/pipeline_newgen_rev1` → OK.
- `PYTHONPATH=src python -m pipeline_newgen_rev1.cli show-plan --mode load` → mesma saída de antes.
- Smoke run-load-sweep em `raw_NANUM` não foi re-executado nesta sessão (refactor puramente estrutural; assinatura pública e campos do summary preservados byte-for-byte).

## Pendências

- **Próximo (Passo 2)**: copiar `nanum_pipeline_29.py`, `nanum_pipeline_30.py`, `kibox_open_to_csv.py` para `src/pipeline_newgen_rev1/legacy_monoliths/`; criar `bridges/legacy_runtime.py` com o contrato `run(ctx)`; plugar 3 estações bridge (`build_final_table`, `run_unitary_plots`, `export_excel`) para produzir `lv_kpis_clean.xlsx` real via newgen.
- Promover `_discover_and_read_inputs`, `_apply_plot_filter`, `_write_summary_artifacts` a estações nomeadas quando fizer sentido (provável que já no Passo 2, com feature_keys internos do tipo `discover_inputs`, `read_inputs`, `write_runtime_summary`).
- Sincronizar repo git com a cópia operacional no OneDrive antes de qualquer Save & Run real (regra durable de `memory/workflow_dual_copy.md`).
