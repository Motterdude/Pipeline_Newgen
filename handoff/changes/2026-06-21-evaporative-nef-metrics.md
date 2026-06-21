# 2026-06-21 — evaporative-nef-metrics

## O que mudou

Novo módulo `_evaporative_nef.py` no pacote `runtime/final_table/` implementa os cálculos de:

1. **Potencial evaporativo do combustível**: h_fg(T) para etanol e água via correlação de Watson a partir de 298.15 K, blend h_fg, Qdot_evap_pot, q_evap_pot_kJ_kWh.
2. **Evaporative-cooling effectiveness**: razão entre o calor realmente retirado do ar (Q_EVAP_NET) e o potencial latente máximo do blend.
3. **Net Energy Factor (Fagundez et al.)**: conversão massa→volume, interpolação ED dos 5 pontos tabelados, NEF_chem e NEF_e.
4. **Sanity flags**: dT>0 sem resfriamento, effectiveness negativa, effectiveness >1.2, diesel N/A, ED fora da faixa Fagundez.

### Colunas novas no `lv_kpis_clean.xlsx`

| Coluna | Descrição |
|---|---|
| `delta_T_air_K` | T_E_CIL_AVG − T_ADMISSAO (negativo = resfriamento) |
| `q_air_cool_kJ_kWh` | Calor sensível retirado do ar por kWh elétrico |
| `T_evap_ref_K` | Temperatura de referência para h_fg |
| `h_fg_ethanol_kJ_kg` | Entalpia de vaporização do etanol a T_ref |
| `h_fg_water_kJ_kg` | Entalpia de vaporização da água a T_ref |
| `h_fg_blend_kJ_kg` | h_fg ponderado do blend |
| `Qdot_evap_pot_kW` | Potência evaporativa potencial máxima |
| `q_evap_pot_kJ_kWh` | Potencial evaporativo por kWh elétrico |
| `evap_cooling_effectiveness` | |Q_air_cool| / Qdot_evap_pot |
| `Q_manifold_evap_kW` | Calor latente já absorvido no coletor (medido via cooling do ar) |
| `q_manifold_evap_kJ_kWh` | Idem, normalizado por kWh elétrico |
| `Q_chamber_available_kW` | Potencial latente restante para charge cooling na câmara |
| `q_chamber_available_kJ_kWh` | Idem, normalizado por kWh elétrico |
| `evap_sanity_flags` | Flags de sanidade evaporativa |
| `ethanol_vv_pct_for_ED` | Fração v/v etanol para interpolação ED |
| `ED_MJ_kg` | Energia de destilação (Fagundez) |
| `NEF_chem` | Net Energy Factor químico |
| `NEF_e` | Net Energy Factor efetivo (com η_f) |
| `NEF_flag` | Flag NEF (extrapol, diesel, etc.) |

## Por quê

Métricas essenciais para a qualificação da dissertação (consumo, eficiência de conversão, efeito evaporativo, Net Energy Factor). O pipeline anterior já calculava SFC e η_f mas não tinha potencial evaporativo nem NEF.

## Arquivos

- **Novo**: `src/pipeline_newgen_rev1/runtime/final_table/_evaporative_nef.py`
- **Editado**: `src/pipeline_newgen_rev1/runtime/final_table/core.py` (import + chamada entre blocos 10 e 11)

## Validação

Smoke test com dados do mestrado (`raw_mestrado/raw`), 49 pontos (D85B15 + E65H35 + E75H25 + E94H6), sem exclusion list:

### SFC e η_f (cross-check manual confirma 100% match)
- D85B15: BSFC 272–985 g/kWh, η_f 8.8–31.8%
- E65H35: BSFC 602–1542 g/kWh, η_f 13.4–34.2%
- E75H25: BSFC 514–1345 g/kWh, η_f 13.3–34.8%
- E94H6: BSFC 425–1099 g/kWh, η_f 13.3–34.5%

### Evaporativo
- delta_T: Diesel +0.5 a +4.3°C (aquecimento); Etanóis −32 a −48°C (forte resfriamento)
- Effectiveness: E65H35 ~17%, E75H25 ~23%, E94H6 ~40% (cresce com teor de etanol — esperado)
- Qdot_evap_pot: E65H35 3–12 kW, E75H25 2–9 kW, E94H6 1.5–6 kW

### NEF
- E65H35: ED=17.5 MJ/kg, NEF_chem≈1.0 (break-even energético)
- E75H25: ED=24.0 MJ/kg, NEF_chem≈0.84
- E94H6: ED=89.8 MJ/kg (clamped HEF), NEF_chem≈0.27 (flagged)

### Consistência física
- Q_EVAP_NET recompute manual (mdot_air·cp·ΔT) confirma valores com <5% de desvio (diferença é cp_moist vs cp=1.005)
- Effectiveness entre 0 e 0.5 é fisicamente plausível para evaporação parcial no coletor
- NEF_chem E65H35 ≈ 1 confirma que a energia para destilar esse blend é ~igual ao LHV obtido
- E94H6 acima do range Fagundez é tratado com clamping + flag

## Atualização 2 — Split manifold/chamber + cleanup plots

### Colunas adicionais
- `Q_manifold_evap_kW`: calor latente já absorvido pela evaporação no coletor de admissão
- `q_manifold_evap_kJ_kWh`: idem normalizado por kWh
- `Q_chamber_available_kW`: potencial latente que resta para charge cooling na câmara
- `q_chamber_available_kJ_kWh`: idem normalizado por kWh

### Plots.toml
- **Removidos**: 3 plots legados Q_EVAP_NET (all_iterations_yx, não geravam)
- **Adicionados**: 4 plots novos (manifold abs + kJ/kWh, chamber abs + kJ/kWh)
- Total de plots evaporativos/NEF na GUI: 11

### Balanço físico
```
Qdot_evap_pot = Q_manifold_evap + Q_chamber_available
```
Q_manifold é o que o sensor de temperatura captura (resfriamento do ar medido).
Q_chamber é o que entra líquido no cilindro e faz charge cooling (suprime knock).

## Pendências

1. **Incerteza propagada** para Qdot_evap_pot, effectiveness e NEF (RSS relativo como as demais métricas)
2. **h_fg T-dependente avançado**: Watson com n=0.38 é adequado para a faixa 35–45°C; para temperaturas fora dessa faixa, considerar correlação polinomial
3. **Validação Diesel Q_EVAP_NET positivo**: no diesel o ar aquece (sem evaporação); flag dT>0 ativo, métricas evaporativas corretamente NaN
