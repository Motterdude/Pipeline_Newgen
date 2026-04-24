---
name: log-change
description: Registra uma mudança de código no handoff do projeto Pipeline_newgen_rev1. Gera handoff/changes/YYYY-MM-DD-slug.md, atualiza CHANGES_INDEX.md, e atualiza stages_status.md se a mudança tocou uma estação. Invocar após editar código.
---

# log-change

Use esta skill imediatamente após uma sessão de edição de código no repositório `Pipeline_newgen_rev1`, antes de terminar a conversa, para garantir que a mudança fique rastreável.

## Passos

### 1. Levantar o que mudou

Rode em paralelo:

```bash
git status
git diff --stat
git diff
```

Identifique:
- arquivos modificados / criados / removidos
- uma descrição curta do efeito combinado (ex: "adiciona RuntimeContext", "porta time_diagnostics para processing/")
- quais estações do `handoff/stages_status.md` foram tocadas (se houver)

### 2. Propor o slug

O slug vai no nome do arquivo e é a chave de busca. Formato:
- `kebab-case`
- 2–5 palavras
- começa com o substantivo principal da mudança

Exemplos bons: `esteira-runtime-context`, `port-time-diagnostics`, `fix-labview-calamine-fallback`, `bridge-final-table`.

Se o usuário já mencionou o slug na conversa, use o dele. Se não, proponha um e confirme **apenas se estiver ambíguo** — senão siga em frente.

### 3. Gerar o arquivo de mudança

Crie `handoff/changes/YYYY-MM-DD-<slug>.md` com a data de hoje e as seções fixas abaixo. Use português.

```markdown
# YYYY-MM-DD — <slug>

## O que mudou

- <bullet curto por mudança, mencionar arquivos pelo caminho>

## Por quê

<1–3 parágrafos. Motivação real — o que o usuário pediu, qual problema resolve, qual contexto.>

## Arquivos

- `caminho/1.py` (novo | modificado | removido)
- `caminho/2.md` (...)

## Validação

- `python -m unittest discover -s tests -p "test_*.py"` → <status>
- `py_compile` → <status>
- <qualquer outro comando rodado: rerun com raw_NANUM, smoke, etc>

## Pendências

- <o que sobrou, o que ainda precisa ser feito, bloqueios>
- <se aplicável: próximo passo esperado>
```

Tamanho alvo: 30–80 linhas. Se crescer muito, provavelmente cabe uma `handoff/decisions/` separada.

### 4. Atualizar o índice

Insira uma linha no topo da seção do mês corrente em `handoff/CHANGES_INDEX.md`:

```markdown
- **YYYY-MM-DD** — [<slug>](changes/YYYY-MM-DD-<slug>.md) — <resumo de uma linha>
```

Se o mês atual ainda não tem seção, adicione `## YYYY-MM` antes.

### 5. Atualizar stages_status quando aplicável

Se a mudança tocou uma estação de `handoff/stages_status.md`, atualize a linha:
- muda o emoji de status (🔴 → 🟡 para bridge; 🟡/🔴 → 🟢 para port completa).
- atualiza a coluna "Última mudança" com a data de hoje.
- preenche a coluna "newgen" com o caminho do arquivo novo, se for port direto.

Se a mudança criou uma nova linha na tabela (nova estação decidida), adicione ao final da seção correta.

### 6. Promover para decisão se for regra

Se a mudança estabelece uma regra arquitetural que vai além desta sessão (ex: "toda stage nova obrigatoriamente vem com teste de paridade"), crie também `handoff/decisions/YYYY-MM-DD-<slug>.md` com o mesmo corpo reescrito como regra (`Decisão` / `Princípio vinculante` / `Consequências`).

### 7. Reporte final

Diga ao usuário em uma linha: "Change registrada em `handoff/changes/YYYY-MM-DD-<slug>.md`. Índice e painel atualizados. [+ decisão nova, se houver]."

## Não fazer

- Não inventar mudanças que não estão no diff.
- Não editar `HANDOFF_MASTER.md` direto — ele é narrativo e raro; change fica em `changes/`.
- Não criar change se não houve edição real de código ou de doc de estado (por exemplo, só leituras).
- Não duplicar conteúdo entre `changes/` e `decisions/` — change conta a sessão, decision declara a regra.
