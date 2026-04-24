# 2026-04-25 — uB-correlacionado-em-media-de-campanha

Status: ativa e vinculante.

## Decisão

Ao agregar duas observações da **mesma campanha de ensaio** (tipicamente subida + descida ou duas réplicas do mesmo ponto) para produzir uma média por ponto, a componente de incerteza **sistemática (uB)** é tratada como **100 % correlacionada** entre as observações e, portanto, **não encolhe** com o fator 1/√N.

Regra operacional:

```
uA(mean) = √(Σ uAᵢ²) / N              # aleatória, IID entre observações → encolhe
uB(mean) = (1/N) · Σ uBᵢ               # sistemática, mesmo instrumento → NÃO encolhe
uc(mean) = √(uA(mean)² + uB(mean)²)
U(mean)  = k · uc(mean)                # k = 2
```

Fallback para métricas derivadas que só têm `uc` (sem separação uA/uB), como η_th:

```
uc(mean) = (1/N) · Σ ucᵢ               # trata todo o uc como sistemático (mais conservador)
```

## Motivação

Subida e descida de uma mesma campanha compartilham: mesma balança, mesmo dinamômetro, mesmo analisador de gases, mesmo lote de combustível, mesma calibração de sensores. A componente de incerteza que vem dessas fontes (uB, Type B na classificação GUM) tem **coeficiente de correlação ρ = 1** entre as duas observações.

**GUM §F.1.2.4** e **§5.2.2** estabelecem que, ao combinar quantidades correlacionadas, a variância combinada contém o termo `+ 2·ρ·Σᵢⱼ uᵢ·uⱼ`. Para ρ = 1 e N = 2 com uᵢ = u:

```
var(mean) = (u² + u² + 2·u·u) / 4 = 4u²/4 = u²
⇒ u(mean) = u                    (NÃO reduzida)
```

O pipeline legado aplicava `u(mean) = √(u² + u²)/2 = u/√2` a ambas as componentes (uA e uB) indistintamente — matematicamente correto apenas para observações IID. Para uB essa suposição é falsa e produz U sub-reportada por fator √2 (~41 %) na coluna "média × média" de todas as métricas.

Validação empírica em 2026-04-25 com `raw_NANUM`:

| Métrica | U_delta média antes | U_delta média depois |
|---|---:|---:|
| η_th | 1,60 % | 2,26 % |
| Consumo | 0,90 % | 1,02 % |

Após o fix, U_delta da média fica **da mesma ordem** que subida × subida e descida × descida — resultado fisicamente esperado, dado que os três compare usam exatamente o mesmo instrumento e a propagação vem das mesmas fontes sistemáticas.

## Escopo de aplicação

- **Aplica-se a**: qualquer estação que agregue observações do mesmo aparato na mesma campanha de ensaio. Hoje no legado: `_mean_subida_descida_per_campaign` (consumo-específico) e `_mean_subida_descida_per_campaign_metric` (genérico para emissões + η_th). Ambos corrigidos.
- **NÃO se aplica** ao agregador genérico `_aggregate_metric_with_uncertainty`, que agrupa trechos/janelas **dentro** de um mesmo arquivo LabVIEW — nesse nível uB também é correlacionado, mas a convenção GUM permite tratar como IID quando N é interpretado como "repetições temporais do mesmo instrumento" (caso típico de σ/√N como erro padrão). Revisar caso a caso se port futuro mexer.
- **Cuidado em ensaios de campanhas distintas**: ao comparar BL (dia X) vs ADTV (dia Y), uB pode deixar de ser 100 % correlacionado se algo no aparato mudou entre dias (recalibração, troca de sensor). Nesse caso a regra precisa ser revisada com modelo de correlação específico.

## Consequências para o newgen

1. Toda estação que fizer essa agregação (hoje futura `run_compare_iteracoes`, Passo 2d+) nasce com a regra embutida. Não é opcional.
2. Testes de paridade byte-for-byte ou DataFrame-equals pós-port **só valem contra a versão corrigida do legado** (a partir de 2026-04-25). Baselines anteriores ficam caducos nessa coluna.
3. A regra é invariante arquitetural: porting subsequente (Passo 3c) deve carregar essa decisão como teste unitário. Sugestão: fixture em `tests/fixtures/paridade/uB_correlated/` com 2 observações sintéticas e assertion `uc_mean == (uc_1 + uc_2)/2`, não `√(uc_1² + uc_2²)/2`.
4. A classe Stage que expor a agregação precisa documentar explicitamente o modelo de correlação assumido (ρ = 1 para uB, ρ = 0 para uA). Função-card a escrever em `handoff/function_cards/` quando a estação for criada.

## Decisões irmãs

- `2026-04-25-propagacao-delta-via-uc-direto.md` — companheira; uc_delta calculado direto, sem passar por uA/uB. Essa decisão permite que o fix aqui se propague naturalmente para a estação de delta sem branching.
- `2026-04-25-derivadas-expor-uA-uB-separados.md` — elimina o uso do fallback "só uc" para métricas derivadas, aumentando a precisão da regra acima.
