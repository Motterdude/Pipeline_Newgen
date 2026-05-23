---
name: organize-raw-files
description: Organiza arquivos de medição raw (LabVIEW xlsx + KiBox .open) em pastas padronizadas por direção/tipo/iteração, pareando por kW e validando timestamps. Usar quando receber pastas brutas de LabVIEW e/ou KiBox para integrar ao pipeline.
---

# organize-raw-files

Organiza arquivos de medição brutos (xlsx do LabVIEW e .open do KiBox) em estrutura padronizada compatível com o pipeline. Pareia arquivos por ponto de carga (kW), valida sincronismo por timestamp, e copia com renomeação para a pasta destino.

## Quando usar

- O usuário fornece pastas com xlsx (LabVIEW) e/ou .open (KiBox) para organizar.
- Dados novos de bancada chegaram e precisam entrar no pipeline.
- Reorganização de campanha existente.

## Argumentos esperados

O usuário deve fornecer:
1. **Fonte xlsx** (LabVIEW): pasta com subpastas por iteração contendo `*.xlsx`
2. **Fonte .open** (KiBox): pasta com subpastas por iteração contendo `*.open`
3. **Destino**: pasta onde criar a estrutura organizada
4. **Prefixo de combustível** (default: `D85B15`): usado no nome dos arquivos destino

Se o usuário não fornecer algum deles, perguntar antes de prosseguir.

## Convenções de nome

### Estrutura de pastas destino

```
{destino}/
├── Descendo_Aditivado_1/
├── Descendo_Aditivado_2/
├── Descendo_Aditivado_3/
├── Descendo_Baseline_1/
├── Descendo_Baseline_2/
├── Descendo_Baseline_3/
├── Subindo_Aditivado_1/
├── Subindo_Aditivado_2/
├── Subindo_Aditivado_3/
├── Subindo_Baseline_1/
├── Subindo_Baseline_2/
└── Subindo_Baseline_3/
```

### Nomes de arquivo destino

- xlsx: `{FUEL}_{load}kW.xlsx` (ex: `D85B15_12.5kW.xlsx`)
- .open: `{FUEL}_{load}kW_i.open` (ex: `D85B15_12.5kW_i.open`)

### Normalização de carga

- Valores inteiros sem decimal: `10kW`, `45kW`
- Valores fracionários com ponto: `12.5kW`, `7.5kW`
- Vírgula → ponto: `12,5` → `12.5`

## Passos

### 1. Inventariar fontes

Para cada fonte, listar subpastas e contar arquivos por tipo:

```python
# Padrão xlsx: qualquer nome terminando em .xlsx (ignorar ~$*)
# Padrão .open: qualquer nome terminando em .open
```

Apresentar tabela resumo ao usuário.

### 2. Extrair kW dos nomes

**De xlsx** (variações conhecidas):
- `0kW.xlsx`, `10kW.xlsx`, `12.5kW.xlsx`, `12,5kW.xlsx`
- `D85B15_0kW.xlsx`, `D85B15_10kW.xlsx`
- `10kW_sem_thc.xlsx` (sufixo `_sem_thc` ignorado)

Regex: `^(?:D85B15_)?([\d]+[.,]?\d*)kW(?:_sem_thc)?\.xlsx$` (case-insensitive)

**De .open** (padrão KiBox):
- `NANUM_ADITIVADO_10KW-2026-04-30--19-39-44-582.open`
- `NANUM_10KW-2026-03-06--19-42-46-974.open`

Regex para kW: `_([\d]+[.,]?\d*)KW` (case-insensitive)

### 3. Extrair timestamp do .open

O timestamp real do ensaio está no nome do arquivo .open:
```
NANUM_ADITIVADO_10KW-2026-04-30--19-39-44-582.open
                     ^^^^^^^^^^^  ^^ ^^ ^^
                     data         HH MM SS
```

Regex: `-(\d{4}-\d{2}-\d{2})--(\d{2})-(\d{2})-(\d{2})`

Usar para:
- Validar que todos os .open de uma pasta são da mesma sessão (±1 dia)
- Apresentar cronologia ao usuário

### 4. Parear por kW dentro de cada subpasta

Para cada subpasta (case-insensitive match entre fonte xlsx e fonte .open):
1. Indexar xlsx por kW normalizado
2. Indexar .open por kW normalizado
3. Identificar pares, órfãos xlsx, órfãos .open

**Duplicatas .open**: se dois .open têm o mesmo kW na mesma pasta, manter o primeiro cronologicamente (timestamp mais antigo dentro da mesma sessão — é o ponto "bom", o segundo é reteste).

### 5. Apresentar plano ao usuário

Antes de copiar, mostrar:
- Total de pares matched
- Órfãos (xlsx sem .open ou vice-versa)
- Duplicatas tratadas
- Grid de cargas esperado vs encontrado por pasta

### 6. Executar cópia

```python
import shutil
shutil.copy2(src, dest)  # preserva timestamps
```

- Criar subpastas destino com `mkdir(parents=True, exist_ok=True)`
- Nome Title Case padronizado: `Subindo_Aditivado_1` (não `subindo_aditivado_1`)
- **NUNCA mover** — sempre copiar (preservar fontes intactas)

### 7. Sanity check final

Rodar verificação no destino:
1. Cada pasta: contagem xlsx vs .open — devem ser iguais (exceto órfãos declarados)
2. Grid de cargas: conferir se cobre 0–45 kW em steps de 2.5 (19 pontos)
3. Nenhum arquivo com tamanho 0
4. Nenhum nome duplicado

Apresentar tabela final com status por pasta.

### 8. Invocar /log-change

Registrar a organização no handoff do projeto.

## Tratamento de anomalias

| Situação | Ação |
|----------|------|
| .open sem xlsx correspondente | Copiar .open mesmo assim, marcar como WARN |
| xlsx sem .open correspondente | Copiar xlsx mesmo assim, marcar como WARN |
| 2 .open mesmo kW (reteste) | Manter o 1º cronológico, reportar |
| Grid incompleto (pontos faltando) | Reportar, não inventar dados |
| Pasta fonte vazia | Pular, reportar |
| Nome não parseable | Listar como ERRO, pedir input do usuário |

## Não fazer

- Nunca modificar/mover arquivos fonte — apenas copiar.
- Nunca inventar dados para completar grid.
- Nunca assumir prefixo de combustível sem confirmar (pode ser E94H6, E75H25, E65H35).
- Nunca sobrescrever destino existente sem perguntar.
