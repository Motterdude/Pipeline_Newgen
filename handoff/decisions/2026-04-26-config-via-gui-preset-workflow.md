# Decisao: Toda config editavel pelo usuario deve passar pelo workflow GUI/preset

**Data:** 2026-04-26

## Regra

Qualquer configuracao que o usuario possa gerenciar via GUI e salvar como preset TOML
**nao deve ser inserida manualmente via edicao direta do arquivo TOML pelo desenvolvedor**.

O fluxo correto e:
1. O codigo cria as **colunas computadas** (ex: `n_th_ind_pct`, `P_ind_kW`)
2. O **usuario** adiciona os plots/configs desejados via GUI e salva no preset
3. O preset `.toml` e a unica fonte de verdade para configuracoes de runtime

## Justificativa

Editar o TOML diretamente quebra o workflow: o preset carregado pela GUI pode divergir
do que esta no disco, causando duplicatas ou entradas orfas quando o usuario salva
pelo caminho normal. O pipeline deve tratar os `.toml` de config como **output da GUI**,
nao como arquivo editado por humanos.

## Excecoes

- `defaults.toml`: chaves de feature flag (`GUI_KNOCK_*_ENABLED`) podem ser adicionadas
  pelo desenvolvedor porque a GUI as le/escreve por key individual, sem risco de conflito.
- `knock_thresholds.toml`: criacao inicial do arquivo quando a feature e nova (bootstrap).
- Schemas e metadados (`schema_version`): sempre editados pelo desenvolvedor.

## Aplicacao

Quando o pipeline cria novas colunas computadas (ex: `n_th_ind_pct`, `n_mech_pct`):
1. Adicionar o calculo no `core.py` ou stage correspondente
2. **NAO** adicionar entradas em `plots.toml` — o usuario faz isso pela GUI
3. Documentar as novas colunas disponiveis no log de mudancas para que o usuario
   saiba quais colunas pode plotar

Se for necessario fornecer plots default para uma feature nova (ex: knock exceedance),
adicionar como **template/exemplo** no change log, nao diretamente no preset ativo.
