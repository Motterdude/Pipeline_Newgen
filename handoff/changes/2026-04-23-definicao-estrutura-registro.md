# 2026-04-23 — definicao-estrutura-registro

## O que mudou

- Criado `CLAUDE.md` na raiz do repo — manual operacional do Claude, carregado automaticamente em toda sessão.
- Criado `handoff/stages_status.md` — painel de controle vivo das estações da fábrica (infra, Fase 1 entrada, Fase 2 processamento, Fase 3 plots, Fase 4 saída, Fase 5 superfície), com marcadores 🟢 / 🟡 / 🔴.
- Criado `handoff/CHANGES_INDEX.md` — índice cronológico inverso das mudanças.
- Criada pasta `handoff/changes/` e este arquivo como primeira entrada.
- Criada pasta `handoff/decisions/` e `handoff/decisions/2026-04-23-arquitetura-fabrica.md` — registro da decisão arquitetural permanente da fábrica nova.
- Criada skill `.claude/skills/log-change/SKILL.md` — automatiza o ritual de registrar uma mudança.
- Criada memória `memory/migration_ritual.md` — garante que sessões futuras do Claude sigam o ritual sem o usuário precisar lembrar.
- Atualizada `memory/MEMORY.md` com o novo ponteiro de ritual.

## Por quê

O usuário pediu explicitamente que, a cada mudança ou port de código, a migração fique **logada e streamlined** — retomar trabalho e debugar devem ser rápidos mesmo em sessões futuras. Escolhemos `handoff/` como fonte de verdade cronológica e documental (em vez de `README` ou `CHANGELOG`) porque:

- o projeto já tem a convenção `handoff/` ativa, com `HANDOFF_MASTER.md` e `function_cards/`;
- o blueprint legado (`PIPELINE_VNEXT_BLUEPRINT.md`) recomenda justamente essa divisão (current_state / changes / decisions / archive);
- `handoff/changes/` e `handoff/decisions/` são versionáveis em git, legíveis por humano e por AI.

`CLAUDE.md` entra como camada complementar estável (não muda entre sessões) que aponta para as fontes vivas. A skill `/log-change` + a memória `migration_ritual.md` fecham o loop automatizando o ritual.

## Arquivos

- `CLAUDE.md` (novo)
- `handoff/stages_status.md` (novo)
- `handoff/CHANGES_INDEX.md` (novo)
- `handoff/changes/2026-04-23-definicao-estrutura-registro.md` (novo — este arquivo)
- `handoff/decisions/2026-04-23-arquitetura-fabrica.md` (novo)
- `.claude/skills/log-change/SKILL.md` (novo)
- `C:\Users\sc61730\.claude\projects\C--Temp-np28-git-main-20260422-Pipeline-newgen-rev1\memory\migration_ritual.md` (novo, fora do repo)
- `C:\Users\sc61730\.claude\projects\C--Temp-np28-git-main-20260422-Pipeline-newgen-rev1\memory\MEMORY.md` (atualizado)

## Validação

- `py_compile` não aplicável (só doc).
- Testes não aplicável (só doc).
- Verificação manual: abrir `handoff/stages_status.md` e confirmar que as 🟢 batem com o que `src/pipeline_newgen_rev1/` já tem.

## Pendências

- **Próximo passo**: começar o Passo 1 (esteira) — criar `runtime/context.py` + `runtime/stages/__init__.py` + `runtime/stages/_base.py` e refatorar `runtime/runner.py` para ser loop sobre o registry. Mantém comportamento + mantém 52 testes verdes.
- Depois do Passo 1: atualizar `handoff/stages_status.md` marcando a esteira como ⚪→🟢 e abrir change `2026-XX-XX-esteira-runtime-context.md`.
- Passo 2 em seguida: copiar monolitos para `legacy_monoliths/`, criar `bridges/legacy_runtime.py`, plugar as primeiras bridges (build_final_table + unitary + export_excel) para chegar em Save & Run end-to-end com `lv_kpis_clean.xlsx`.
- Também falta sincronizar o repo git com a cópia operacional no OneDrive quando esta sessão for ao código.
