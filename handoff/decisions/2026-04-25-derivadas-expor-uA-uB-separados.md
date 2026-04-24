# 2026-04-25 — derivadas-expor-uA-uB-separados

Status: ativa e vinculante.

## Decisão

Toda métrica **derivada** incluída no `final_table` — ou seja, calculada via propagação analítica a partir de grandezas medidas diretamente — **deve expor**, no mesmo nível do `final_table`, as 4 colunas de incerteza **separadas**:

- `uA_<metric>` — componente aleatória (agregável por 1/√N)
- `uB_<metric>` — componente sistemática (correlacionada no mesmo aparato)
- `uc_<metric>` — combinada (`√(uA² + uB²)`)
- `U_<metric>` — expandida (`k · uc`, k = 2)

Não basta expor só `uc` e `U`. A separação uA/uB é requisito do contrato entre a estação de cálculo e as estações de agregação downstream (média campanha, delta, compare iteracoes).

Aplicável a, no mínimo, as seguintes métricas derivadas já presentes no legado:

- `n_th_pct` — eficiência térmica
- `BSFC_g_kWh` — consumo específico freio
- `Economia_vs_Diesel_R_h` e `Economia_vs_Diesel_pct` — economia monetária
- `Consumo_L_h` (derivada de `Consumo_kg_h` / densidade)
- Emissões específicas em `g/kWh` (`CO2_g_kWh`, `CO_g_kWh`, `NOx_g_kWh_*`, `THC_g_kWh`) — derivadas de concentração × vazão / potência

## Motivação

As decisões irmãs (`uB-correlacionado-em-media-de-campanha`, `propagacao-delta-via-uc-direto`) definem regras de propagação que **discriminam** uA de uB em tempo de execução — uA encolhe por 1/√N, uB não encolhe. Se a métrica expuser só `uc` sem separação, o agregador cai num branch de fallback "conservador" que trata todo o uc como sistemático (não encolhe nada). Isso:

1. **Sub-reporta a redução legítima de uA** por média temporal ou entre iterações.
2. **Perde informação diagnóstica** — não se vê mais qual componente domina o erro.
3. **Quebra simetria** com as métricas medidas diretamente (Consumo_kg_h, NOX_mean_of_windows, etc.), que têm as 4 colunas completas.

Exemplo concreto do caso-gatilho (2026-04-25): `η_th = P_kW / (ṁ · LHV)`. O uc vem de `√((ucP/P)² + (ucF/F)² + (uBL/LHV)²)`. Cada uma dessas fontes tem a sua própria breakdown uA/uB:

- `P_kW`: uA vem da σ de leitura do dinamômetro entre janelas; uB vem da calibração da célula de carga. Ambas já existem no final_table como `uA_P_kw` e `uB_P_kw`.
- `Consumo_kg_h`: idem — `uA_Consumo_kg_h` da σ entre janelas, `uB_Consumo_kg_h` da resolução da balança. Ambas presentes.
- `LHV`: puramente uB (valor tabelado ou medido externamente, sem réplicas temporais).

A propagação de η_th pode e deve propagar essas breakdowns separadamente:

```
uA_n_th = n_th · √( (uA_P/P)² + (uA_Consumo/Consumo)² + 0 )      # LHV não contribui p/ uA
uB_n_th = n_th · √( (uB_P/P)² + (uB_Consumo/Consumo)² + (uB_LHV/LHV)² )
```

Hoje o legado só computa a combinada `uc_n_th = n_th · √(sum_of_squares_of_rel_uc)`. A separação é trivial mas ainda não é feita.

## Forma da entrada

No port nativo de `build_final_table` (Passo 3b), cada cálculo de derivada precisa substituir o padrão atual:

```python
# Padrão atual (legado, a ser corrigido no port nativo):
rel_uc = ((ucP / PkW) ** 2 + (ucF / Fkgh) ** 2 + (uBL / LHVv) ** 2) ** 0.5
df["uc_n_th"] = df["n_th"] * rel_uc
df["U_n_th"] = K_COVERAGE * df["uc_n_th"]
```

pelo padrão correto:

```python
# Padrão alvo pós-port:
rel_uA = ((uAP / PkW) ** 2 + (uAF / Fkgh) ** 2) ** 0.5      # LHV é uB-only
rel_uB = ((uBP / PkW) ** 2 + (uBF / Fkgh) ** 2 + (uBL / LHVv) ** 2) ** 0.5
df["uA_n_th"] = df["n_th"] * rel_uA
df["uB_n_th"] = df["n_th"] * rel_uB
df["uc_n_th"] = (df["uA_n_th"] ** 2 + df["uB_n_th"] ** 2) ** 0.5
df["U_n_th"] = K_COVERAGE * df["uc_n_th"]
# E versões _pct: multiplicar cada um por 100 quando expor em ponto percentual.
```

## Consequências para o newgen

1. O port nativo de `build_final_table` (Passo 3b) carrega essa regra como parte do contrato de cada cálculo derivado. Não é opcional.
2. Uma vez que a regra esteja aplicada, o branch de fallback em `_mean_subida_descida_per_campaign_metric` (para uc sem uA/uB) pode ser removido — passa a ser dead code. Isso fica como **pendência** do port nativo da agregação (Passo 3c).
3. O teste de paridade do port nativo deve verificar que as 4 colunas (uA, uB, uc, U) estão presentes para **todas** as métricas derivadas listadas no Escopo acima.
4. No lado do legado (galpão antigo), a versão corrigida pode ser espelhada nas copies em `legacy_monoliths/` para benefício imediato — ou pode ficar só no port nativo, já que o legado seria removido ao fim da migração. **Recomendação**: não mexer mais no legado além do mínimo; o port nativo absorve essa decisão.

## Decisões irmãs

- `2026-04-25-uB-correlacionado-em-media-de-campanha.md` — requer que uA/uB venham separados para aplicar a regra de correlação corretamente.
- `2026-04-25-propagacao-delta-via-uc-direto.md` — funciona com ou sem separação uA/uB; esta decisão complementa reduzindo o uso do fallback.
