---
name: audit-raw-folder
description: Audita uma pasta raw organizada do pipeline — verifica sincronismo xlsx↔.open, grid de cargas, integridade de arquivos, e reporta anomalias. Usar para validar que uma pasta está pronta para processamento.
---

# audit-raw-folder

Valida a integridade e completude de uma pasta raw organizada (estrutura `Subindo/Descendo × Baseline/Aditivado × 1/2/3`). Verifica que cada xlsx tem seu .open e vice-versa, que o grid de cargas está completo, e que não há arquivos corrompidos.

## Quando usar

- Antes de rodar o pipeline numa pasta raw nova.
- Após `/organize-raw-files` para confirmar resultado.
- Quando o usuário pede "verifica a pasta", "confere os arquivos", "sanity check".

## Argumentos

O usuário deve fornecer o caminho da pasta a auditar. Se não fornecer, perguntar.

Opções:
- `--fix`: além de reportar, corrigir problemas simples (renomear vírgulas→pontos, remover duplicatas)
- `--compare <outra-pasta>`: comparar contagem/grid entre duas pastas (ex: _renamed vs _renamed_combustion)

## Passos

### 1. Verificar estrutura de pastas

Conferir que existem as 12 subpastas esperadas:
```
{Subindo,Descendo}_{Aditivado,Baseline}_{1,2,3}
```

Aceitar variações de case. Reportar pastas extras ou faltantes.

### 2. Contagem por pasta

Para cada subpasta:
- Contar `*.xlsx` (ignorar `~$*`)
- Contar `*.open`
- Contar `*_i.csv` (CSVs já convertidos do .open)
- Contar `*_m.csv` (MoTeC, se houver)

### 3. Verificar sincronismo

Para cada subpasta, extrair kW do nome de cada arquivo e conferir:
- Cada xlsx `{FUEL}_{load}kW.xlsx` tem um .open `{FUEL}_{load}kW_i.open`?
- Cada .open tem xlsx correspondente?
- Se houver `_i.csv`, bate com os .open?

Reportar: OK, WARN (órfão), ERRO (inconsistência grave).

### 4. Verificar grid de cargas

Grid padrão: `0, 2.5, 5, 7.5, 10, 12.5, 15, 17.5, 20, 22.5, 25, 27.5, 30, 32.5, 35, 37.5, 40, 42.5, 45` (19 pontos, step 2.5 kW).

Para cada pasta, reportar:
- COMPLETO (19/19)
- INCOMPLETO: listar pontos faltantes

### 5. Verificar integridade

- Nenhum arquivo com tamanho 0 bytes
- Nenhum nome com caracteres problemáticos
- xlsx legíveis (tentar `pd.read_excel(..., nrows=0)`)
- .open não corrompidos (tamanho > 1 KB)

### 6. Apresentar relatório

Formato tabela:

```
Pasta                | xlsx | .open | _i.csv | sync | grid    | saúde
Descendo_Aditivado_1 |   19 |    19 |     19 |   OK | 19/19   | OK
Subindo_Baseline_2   |   18 |    19 |      0 | WARN | 18/19   | OK
```

Seguido de lista de anomalias e ações sugeridas.

### 7. Comparação entre pastas (se --compare)

Mostrar tabela lado-a-lado comparando:
- Quais iterações/cargas existem em uma mas não na outra
- Diferenças de contagem
- Qual tem dados MoTeC e qual não

## Checks adicionais

| Check | Critério | Severidade |
|-------|----------|-----------|
| Duplicata de kW na mesma pasta | 2 arquivos com mesmo kW | ERRO |
| Vírgula no nome | `12,5kW` em vez de `12.5kW` | WARN (--fix corrige) |
| Prefixo inconsistente | Mix de `D85B15_` e `E94H6_` na mesma pasta | ERRO |
| Arquivo muito grande | xlsx > 50 MB | WARN |
| Arquivo muito pequeno | xlsx < 10 KB ou .open < 1 KB | WARN |

## Não fazer

- Nunca deletar arquivos, mesmo com `--fix`.
- Nunca modificar conteúdo de xlsx/.open.
- `--fix` apenas renomeia (vírgula→ponto, padroniza case).
