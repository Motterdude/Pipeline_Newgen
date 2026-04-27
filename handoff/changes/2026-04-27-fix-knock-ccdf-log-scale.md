# 2026-04-27 — fix-knock-ccdf-log-scale

## O que mudou

- `compute_kpeak_exceedance()` substituida: metodo anterior (linspace + searchsorted) trocado por CCDF empirica com posicoes de Weibull (`(n - rank + 1) / (n + 1)`). Um ponto por observacao, nunca zero, seguro para escala log.
- Parametro `n_points` removido de `compute_kpeak_exceedance` e `plot_knock_histogram` (nao mais necessario — a curva tem um ponto por ciclo KiBox).
- `ylim` adaptativo para modos log10/log2: piso = `max(0.05, 50/n_total)`, teto = 150. Garante range estavel independente do tamanho da amostra.
- Pendencia de 2026-04-26 (`fuel-colors-knock-features`) marcada como resolvida.

## Por que

O metodo anterior de calculo da CCDF tinha 3 problemas nas escalas logaritmicas:

1. **Zeros**: `linspace` gerava pontos de x acima do maior KPEAK, resultando em exceedance = 0%. `log(0) = -inf` — a curva simplesmente desaparecia na cauda.
2. **Escada (staircase)**: `searchsorted` retorna contagens inteiras. Com n=1000 ciclos, os degraus de 0.1% sao invisiveis na escala linear mas enormes na log (0.1% → 0.2% = fator 2x visual).
3. **ylim instavel**: sem limites definidos para log, o matplotlib auto-escalava. O mesmo combustivel plotado com 200 vs 5000 ciclos dava graficos visualmente incomparaveis.

A CCDF empirica (Weibull) resolve os 3 de uma vez: nunca gera zero, cada ponto tem rank unico (sem escada), e o ylim adaptativo estabiliza a apresentacao.

## Arquivos

- `src/pipeline_newgen_rev1/runtime/knock_histogram.py` (modificado)
- `handoff/changes/2026-04-26-fuel-colors-knock-features.md` (modificado — pendencia fechada)

## Validacao

- `python -m unittest discover -s tests -p "test_*.py"` → 445 testes, 0 falhas novas (10 erros pre-existentes de bridges removidas)
- Smoke test sintetico: 2 combustiveis × 1000 ciclos, 3 escalas (linear, log10, log2) — todos os PNGs gerados OK
- Verificacao numerica: exceedance range [0.0999%, 99.9001%], zero zeros, monotonicidade confirmada

## Pendencias

- Nenhuma.
