# 2026-04-24 — bridge-scaffolding (Passo 2a)

## O que mudou

- **Copiados 4 arquivos do galpão antigo** para `src/pipeline_newgen_rev1/legacy_monoliths/`:
  - `nanum_pipeline_29.py` (9.619 linhas — o motor)
  - `nanum_pipeline_30.py` (10.035 linhas — variante sweep)
  - `kibox_open_to_csv.py` (dep do 29/30)
  - `pipeline29_config_backend.py` (dep dos siblings via bare import)
- Criado `legacy_monoliths/__init__.py` com `ensure_on_path()` — prepende o diretório a `sys.path` para resolver os bare imports (`from pipeline29_config_backend import ...`) entre os siblings legado sem precisar patchar o código.
- Criado `src/pipeline_newgen_rev1/bridges/legacy_runtime.py` — módulo de bridges. Contém:
  - `_load_legacy_pipeline29()` — lazy import por `importlib`, pagando o custo de ~10k linhas + matplotlib/numpy apenas quando o primeiro bridge stage é exercitado.
  - `ExportExcelBridgeStage(feature_key="export_excel")` — primeira estação bridge. Semântica: se `ctx.final_table is None`, loga "nothing to write" e retorna; caso contrário, chama `safe_to_excel(ctx.final_table, ctx.output_dir / "lv_kpis_clean.xlsx")` do legado e popula `ctx.lv_kpis_path`.
- Adicionado ao `RuntimeContext`: slots `final_table: Optional[pd.DataFrame]` e `lv_kpis_path: Optional[Path]` — a categoria "produzido por bridge stages".
- Registrado `"export_excel": ExportExcelBridgeStage()` em `STAGE_REGISTRY` e acrescentado a `STAGE_PIPELINE_ORDER` — a estação roda a cada invocação; sendo no-op enquanto `final_table` não existe.
- Novo teste `tests/test_bridge_export_excel.py` com 3 casos:
  - skip quando `final_table is None` (não escreve nada)
  - raise quando `output_dir is None` mas `final_table` presente
  - escreve `lv_kpis_clean.xlsx` e valida conteúdo linha-a-linha via `openpyxl` (skipado no dev-env se matplotlib ausente)
- `pyproject.toml` ganha extra `legacy = ["matplotlib>=3.8"]` — a dep que o monolito 29/30 puxa no import. Instala-se com `pip install .[legacy]`.
- Atualizado `handoff/stages_status.md` — `Cópia dos monolitos` 🟡→🟢, `Bridge runtime` 🟡→🟢 (scaffolding), `Export Excel` ainda 🟡 parcial (bridge pronto, falta alimentação de `final_table`).
- Criados 2 function_cards novos (`bridge_legacy_runtime.fnctx.md`, `stage_export_excel.fnctx.md`).

## Por quê

Passo 2 da migração exige que existam bridges funcionais para as estações 🔴 antes do porting nativo começar — é a "janela de atendimento" da fábrica. Em vez de tentar portar fim-a-fim em uma sessão, fatiamos em 2a/2b/2c:

- **2a (agora)**: infraestrutura + 1 bridge trivial (`export_excel` wrappeando `safe_to_excel`) — valida o padrão de bridge stage sem depender de dataframe real.
- **2b (próximo)**: construir a cadeia de alimentação para `build_final_table` (ponto stats + fuel properties + kibox_agg + motec_ponto) e ligar o bridge `export_excel` à saída real.
- **2c**: bridge stages `run_unitary_plots` e `run_time_diagnostics`.

Com isso, os 55 testes permanecem verdes (52 antigos + 3 novos, 1 skip por matplotlib ausente no dev-env), a esteira já rota a estação bridge sem efeito observável, e qualquer sessão futura pode mexer em `ctx.final_table` e ver `lv_kpis_clean.xlsx` sair no disco.

## Arquivos

- `src/pipeline_newgen_rev1/legacy_monoliths/__init__.py` (novo)
- `src/pipeline_newgen_rev1/legacy_monoliths/nanum_pipeline_29.py` (cópia)
- `src/pipeline_newgen_rev1/legacy_monoliths/nanum_pipeline_30.py` (cópia)
- `src/pipeline_newgen_rev1/legacy_monoliths/kibox_open_to_csv.py` (cópia)
- `src/pipeline_newgen_rev1/legacy_monoliths/pipeline29_config_backend.py` (cópia)
- `src/pipeline_newgen_rev1/bridges/legacy_runtime.py` (novo)
- `src/pipeline_newgen_rev1/runtime/context.py` (2 slots novos)
- `src/pipeline_newgen_rev1/runtime/stages/__init__.py` (registra `export_excel`)
- `tests/test_bridge_export_excel.py` (novo)
- `pyproject.toml` (extra `legacy`)
- `handoff/stages_status.md` (atualizado)
- `handoff/function_cards/bridge_legacy_runtime.fnctx.md` (novo)
- `handoff/function_cards/stage_export_excel.fnctx.md` (novo)

## Validação

- `python -m unittest discover -s tests -p "test_*.py"` → **55 testes, OK, 1 skipped** (o skip é o `test_writes_lv_kpis_when_frame_present` que requer matplotlib; passa no env operacional).
- `PYTHONPATH=src python -m pipeline_newgen_rev1.cli show-plan --mode load` → saída inalterada.
- Assinatura de `run_load_sweep` preservada; campos do `summary` idênticos ao baseline.
- Circular import entre `bridges.legacy_runtime` e `runtime.context` resolvido via `TYPE_CHECKING` no import de `RuntimeContext` dentro do bridge.

## Pendências

- **Passo 2b (próximo)**: no-op da bridge `export_excel` some quando `ctx.final_table` for alimentado. Plano:
  1. Identificar no `main()` do 29 as funções de preparação — `compute_ponto_stats`, `load_fuel_properties_lookup`, `kibox_aggregate`, agregação MoTeC — e mapear seus insumos.
  2. Criar bridge helper `_build_legacy_intermediate_frames(ctx)` em `bridges/legacy_runtime.py` que roda essa cadeia e devolve os 4 DataFrames.
  3. Criar `BuildFinalTableBridgeStage(feature_key=...)` — escolher feature_key (provável interna, tipo `build_final_table`, nova entrada em `LOAD_SWEEP_FEATURE_SPECS`; ou reusar alguma já existente como gancho).
  4. Ordem em `STAGE_PIPELINE_ORDER`: `build_final_table` antes de `export_excel`. Conferir se precisa mover o stage loop para depois dos helpers core de leitura.
- **Passo 2c**: bridges para `run_unitary_plots` (consome `ctx.final_table`) e `run_time_diagnostics` (consome `ctx.labview_frames`).
- `pip install .[legacy]` é pré-requisito na cópia operacional do OneDrive para o bridge funcionar com write real.
- Sincronizar git ↔ OneDrive antes de rodar Save & Run.
