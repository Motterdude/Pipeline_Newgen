# 2026-04-26 — Análise do pico de Ignition Delay no E65H35 ~24 kW

## O que mudou

Análise investigativa (sem alteração de código). O gráfico `ignition_delay_vs_upd_power_all.png` do output mestrado mostrava um pico anômalo na curva E65H35: de ~15.3° CA em 20 kW para **17.3° CA** em 25 kW, depois caindo para 14.3° em 30 kW.

## Por quê

Pico inesperado no ignition delay do E65H35 no bin de ~24 kW levantou dúvida se era erro de processamento ou dado real.

## Arquivos investigados

- `Out_mestrado/plots/ignition_delay_vs_upd_power_all.png` (gráfico)
- `Out_mestrado/lv_kpis_clean.xlsx` (tabela consolidada — 49 linhas, 946 colunas)
- `raw_mestrado/25kw_e65h35_m.csv` (MoTeC cru)
- `raw_mestrado/TESTE_25KW_E65H35-2026-01-25--19-56-59-859_i.csv` (KiBox cru)
- `src/pipeline_newgen_rev1/runtime/final_table/core.py:442-452` (fórmula do ignition delay)

## Validação

### Breakdown numérico (3 bins vizinhos, E65H35)

| Bin   | Motec Ign Timing (°BTDC) | KIBOX AI05 (°ATDC) | Delay (°CA) | Engine Load (mg) | sd EngLoad |
|-------|--------------------------|---------------------|-------------|-------------------|------------|
| 20 kW | 16.0                     | -0.672              | 15.33       | 384               | 5.6        |
| 25 kW | **17.5**                 | -0.204              | **17.30**   | **230**           | **27.5**   |
| 30 kW | 15.0                     | -0.679              | 14.32       | 532               | 7.0        |

### Diagnóstico

1. **Driver dominante (>90%)**: avanço de ignição = 17.5° BTDC em vez dos ~15.5° esperados por interpolação.
2. **Dado cru confirmado**: MoTeC mostra 17.5° constante (sd=0.000) em todo o ensaio — não é artefato de média.
3. **Engine Load anômalo**: 230 mg no bin de 25 kW (< que o bin de 10 kW, 258 mg). Desvio padrão 27.5 mg (5× o normal). Indica split H2/etanol diferente do esperado.
4. **IMEPN coerente**: 5.07 bar segue a progressão perfeita — motor fez a potência correta.
5. **Interpretação**: ECU "viu" carga de injeção baixa (~230 mg ≈ mapa do 10 kW) e comandou avanço do mapa de carga baixa (17.5°). O motor compensou com mais H2.

### Conclusão

**Não é erro do pipeline.** Dado real. O pico reflete avanço de ignição alto causado por split de combustível anômalo no ensaio. Recomendação: verificar log do banco se o fluxo de H2 no ensaio de 25 kW E65H35 estava correto.

## Pendências

- [ ] Verificar com engenheiro de testes se o fluxo de H2 no ensaio 25kW E65H35 (25/01/2026) estava conforme.
- [ ] Ponto de 50 kW E65H35 também apresenta Engine Load anômalo (268 mg, Fuel Trim 22.3%) — investigar na mesma batida.
