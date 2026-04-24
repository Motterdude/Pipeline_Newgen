# CLAUDE.md

Manual operacional do Claude para o repositório `Pipeline_newgen_rev1`.
Este arquivo é lido automaticamente em toda sessão. Mantenha-o estável: mudanças de estado vão para `handoff/`, não para cá.

## Projeto em uma frase

Migrar o monolito `nanum_pipeline_29.py` + `nanum_pipeline_30.py` para um pacote Python limpo `pipeline_newgen_rev1`, **preservando 100% das funcionalidades** (mesmo `lv_kpis_clean.xlsx`, mesmos plots, mesmos Excel de compare).

## Modelo mental: a fábrica

- **Estações (stages)**: cada uma faz UM trabalho (ler LabVIEW, calcular emissões, gerar plots unitários, exportar Excel, aplicar binning de sweep, ...).
- **Esteira (`RuntimeContext`)**: carrega a peça em construção de estação em estação. Cada estação recebe o contexto, faz sua parte, devolve.
- **Plano da linha (`workflows/load_sweep/orchestrator.build_load_sweep_plan`)**: a ordem das estações, filtrada por feature flag (`load` vs `sweep`).
- **Galpão antigo (`src/pipeline_newgen_rev1/legacy_monoliths/`)**: cópia transitória dos monolitos 29/30 que fornece as estações vermelhas via `bridges/legacy_runtime.py` (a "janela de atendimento").

Regra: estação dentro da fábrica nova = código novo limpo. Estação via bridge = chamada ao galpão antigo. Cada port substitui uma bridge por uma estação nova.

## Onde encontrar cada coisa

| Informação | Arquivo |
|---|---|
| Painel de status das estações | `handoff/stages_status.md` |
| Índice cronológico de mudanças | `handoff/CHANGES_INDEX.md` |
| Log de uma sessão de mudança | `handoff/changes/YYYY-MM-DD-slug.md` |
| Decisões arquiteturais permanentes | `handoff/decisions/YYYY-MM-DD-slug.md` |
| Cards operacionais por função (low-context) | `handoff/function_cards/*.fnctx.md` |
| Formato dos cards | `handoff/FUNCTION_CONTEXT_FORMAT.md` |
| Estado atual narrativo + histórico | `handoff/HANDOFF_MASTER.md` |
| Visão macro da migração | `docs/MIGRATION_STATUS.md` |
| Comandos operacionais | `README.md` |
| Tabela de âncoras para o monolito legado | `src/pipeline_newgen_rev1/bridges/legacy_pipeline30.py` |

## Convenções

### Idioma
- Código, nomes de arquivo, function_cards: inglês técnico.
- Handoff, changes, decisions, conversa com o usuário: português.

### Antes de editar código
1. Ler `handoff/stages_status.md` para saber o estado da estação a ser tocada.
2. Ler a `function_card` correspondente, se existir.
3. Ler a decisão mais recente aplicável em `handoff/decisions/`.

### Durante a edição
1. Os testes em `tests/` devem continuar passando. Se um teste quebra, investigar antes de seguir.
2. Stage nova segue o protocolo em `src/pipeline_newgen_rev1/runtime/stages/_base.py` (quando existir).
3. Stage nova remove a entrada correspondente em `bridges/legacy_pipeline30.py` e (eventualmente) o arquivo legado de `legacy_monoliths/` quando for a última dependência dele.

### Depois da edição
1. Rodar: `python -m unittest discover -s tests -p "test_*.py"`.
2. Invocar `/log-change` (skill) ou seguir o ritual manualmente.
3. Se mudou status de estação, atualizar `handoff/stages_status.md`.
4. Se a mudança vale como regra permanente, criar arquivo em `handoff/decisions/`.

## Ritual de registro

Toda sessão que toca código cria:

1. `handoff/changes/YYYY-MM-DD-<slug>.md` com seções fixas: **O que mudou**, **Por quê**, **Arquivos**, **Validação**, **Pendências**.
2. Uma linha no topo de `handoff/CHANGES_INDEX.md`: `- 2026-MM-DD — <slug> — <resumo de uma linha>`.
3. Se tocar uma estação: atualizar a linha correspondente em `handoff/stages_status.md`.
4. Se virou regra: `handoff/decisions/YYYY-MM-DD-<slug>.md`.

A skill `/log-change` automatiza os passos 1 e 2 e lembra dos 3 e 4.

## Comandos operacionais rápidos

```powershell
# Testes
python -m unittest discover -s tests -p "test_*.py"

# Smoke compile do pacote inteiro
Get-ChildItem -Recurse -Filter *.py | ForEach-Object { python -m py_compile $_.FullName }

# Abrir GUI migrada
$env:PYTHONPATH='src'
python -m pipeline_newgen_rev1.cli launch-config-gui

# Run-load-sweep (summary-oriented enquanto a fábrica ainda não está completa)
python -m pipeline_newgen_rev1.cli run-load-sweep `
  --config-dir .\config\pipeline29_text `
  --process-dir E:\raw_pyton\raw_NANUM `
  --out-dir E:\out_Nanum_rev2 `
  --json
```

## Duplo working copy

Este repo existe em duas cópias vivas:

- **Git / desenvolvimento**: `C:\Temp\np28_git_main_20260422\Pipeline_newgen_rev1`
- **Operacional / runs reais**: `C:\Users\sc61730\OneDrive - Stellantis\Pessoal\pipeline_newgen`

Mudança em `src/` ou `config/` precisa ser sincronizada antes de qualquer `Save & Run` real.

## Galpão antigo (referência)

- Local: `C:\Temp\np28_git_main_20260422\nanum-pipeline-28-main\`
- GitHub: https://github.com/Motterdude/nanum-pipeline-28
- Arquivos-chave: `nanum_pipeline_29.py`, `nanum_pipeline_30.py`, `pipeline29_config_gui.py`, `pipeline29_config_backend.py`, `kibox_open_to_csv.py`
- Blueprint da arquitetura alvo: `<legacy>/docs/PIPELINE_VNEXT_BLUEPRINT.md`
- Histórico: `<legacy>/HANDOFF_GLOBAL.md`, `<legacy>/CHANGELOG.md`
