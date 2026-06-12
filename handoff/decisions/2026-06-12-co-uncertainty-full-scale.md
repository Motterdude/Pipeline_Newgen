# Decisão: Incerteza CO/CO2/O2 — % of Full Scale, não % da leitura

Data: 2026-06-12

## Contexto

O `instruments.toml` configurava a repetibilidade do California Analytical Model 30 (NDIR) como:

```toml
acc_pct = 0.01   # interpretado pelo pipeline como 1% DA LEITURA
resolution = 0.1  # %vol
```

Investigação com o manual do fabricante (600_SERIES_NDIR_OPERATORS_MANUAL_REV_116.pdf) e a tese do Vinícius (Moreira_R13, Tabela C1, pg.153) revelou:

## Evidências do manual do fabricante (Model 600 Series, pg.22)

| Spec | Valor | Unidade |
|---|---|---|
| NOISE | < 1% | of Full Scale |
| REPEATABILITY | < 1% | of Full Scale |
| ZERO & SPAN DRIFT | < 1% | of Full Scale per 24h |
| LINEARITY | < 0.5% | of Full Scale |
| RESOLUTION (display) | 5 significant digits | — |

**Todas as specs de performance são em % of Full Scale, não % da leitura.**

## Impacto numérico

Para CO_pct com Full Scale = 20% CO:

| Leitura | 1% da leitura (errado) | 1% of FS (correto) | Fator |
|---|---|---|---|
| 50 ppm | 0.5 ppm | 2000 ppm | 4000× |
| 100 ppm | 1.0 ppm | 2000 ppm | 2000× |
| 500 ppm | 5.0 ppm | 2000 ppm | 400× |
| 5000 ppm | 50 ppm | 2000 ppm | 40× |

Para leituras baixas (campanha D85B15 com mediana de ~50 ppm), o `acc_pct = 0.01` subestimava a incerteza de acurácia em milhares de vezes.

## A resolução (0.1%) está CORRETA

Os steps de 0.000001 %vol nos xlsx são ruído eletrotérmico digitalizado com alta resolução numérica pelo NI DAQ (16-bit, 0-10V). O DAC transmite o sinal fielmente — incluindo o ruído. O instrumento não tem informação útil abaixo do noise floor (~0.1-0.2% CO com FS=20%).

A cadeia de sinal (manual pg.21):
```
NDIR detector → AC amp → demodulate/filter → DC amp → ADC interno
→ linearize → D/A Converter → 0-10V → NI DAQ → LabVIEW → xlsx
```

O display mostra 5 dígitos significativos (0.001% de resolução numérica), mas os últimos dígitos são ruído puro.

## Decisão

1. **Manter `resolution = 0.1`** — é a resolução efetiva do instrumento (noise-limited), não do display.

2. **Trocar `acc_pct = 0.01` para `acc_abs = 0.2`** para CO_pct, CO2_pct, O2_pct — representando 1% of Full Scale em valor absoluto na unidade de engenharia (%vol).

3. **Aplicar a mesma lógica** para NOx_ppm, NO_ppm, THC_ppm: verificar se suas specs também são % of FS.
   - Manual pg.22 lista specs do Model 600 (CO/CO2). O 400-HCLD (NOx/NO) e 300M-HFID (THC) são instrumentos diferentes com specs próprias.
   - Moreira Tab.C1 lista repetibilidade 0.5% para NOx/NO/THC — mas não especifica se é "of reading" ou "of FS".
   - **Conservadoramente**: para NOx (FS=3000 ppm) com leituras típicas de 100-2000 ppm, a diferença entre 0.5% da leitura e 0.5% do FS é menor (máximo 6×). Manter como está por ora.

4. **Questão do range**: o Model 600 tem range ratio 10:1 e auto-ranging. Se o range de CO no experimento era 0-2% (não 0-20%), o noise floor seria 200 ppm, não 2000 ppm. Sem informação do range real, usar 20% (pior caso) é conservador e metrológicamente defensável.

## Referências

- California Analytical Instruments, "600 SERIES NDIR/O2 USER'S MANUAL", Rev 116, pg.22 (Specifications)
- California Analytical Instruments, ibid., pg.21 (Electronics / Signal chain)
- California Analytical Instruments, ibid., pg.98 (D/A Calibration, output options: 0-1V, 0-5V, 0-10V, 4-20mA, 0-20mA)
- Moreira, V. "R13" (tese), Tabela C1, pg.153 (Apêndice D)
