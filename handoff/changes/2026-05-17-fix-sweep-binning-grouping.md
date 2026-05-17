# 2026-05-17 — fix-sweep-binning-grouping

## O que mudou

Corrigido bug crítico no sweep mode: a agregação de MoTeC e KiBox não preservava o `Sweep_Value` como chave de agrupamento, fazendo com que todos os pontos de lambda sweep de um mesmo combustível fossem fundidos numa média única. Resultado: o binning encontrava apenas 2 bins (um por fuel) em vez dos 7 esperados (um por lambda setpoint).

## Por quê

Ao rodar um lambda sweep (E65H35 + E94H6, lambdas 1.0→1.3 em passos de 0.05) com dados de KiBox, MoTeC e LabVIEW na mesma pasta, o pipeline produzia `Sweep_Bin_Value` com apenas 2 valores (~1.149 e ~1.192) — as médias de TODOS os lambdas por combustível. Os 7 centros de varredura eram destruídos na etapa de agregação.

Causa raiz: `MOTEC_GROUP_COLS_PONTO` e `GROUP_COLS_PONTO` (LabVIEW) não incluíam `Sweep_Value`. O MoTeC ponto colapsava 7×2=14 pontos em apenas 2 linhas. O merge subsequente em `build_final_table` produzia duplicatas ou dados inconsistentes.

## Arquivos

| Arquivo | Mudança |
|---|---|
| `src/.../runtime/trechos_ponto/constants.py` | +`Sweep_Value` em `GROUP_COLS_TRECHOS` e `GROUP_COLS_PONTO` |
| `src/.../runtime/trechos_ponto/core.py` | Filtragem defensiva `active_*_cols` — só agrupa por colunas presentes no df |
| `src/.../runtime/motec_stats.py` | +`Sweep_Value` em `MOTEC_GROUP_COLS_TRECHOS` e `MOTEC_GROUP_COLS_PONTO` + filtragem defensiva |
| `src/.../runtime/stages/prepare_upstream_frames.py` | +`Sweep_Value` em `KIBOX_GROUP_COLS` |
| `src/.../runtime/final_table/core.py` | Merge condicional: inclui `Sweep_Value` como `extra_on` quando dados de sweep estão presentes |
| `src/.../runtime/sweep_binning.py` | Nova `_resolve_x_col()` com fallback inteligente para colunas suffixadas (`_mean_of_windows_x`) |

## Validação

- 445 testes: 435 OK, 10 erros pré-existentes em bridges legados (não relacionados)
- Simulação end-to-end sweep mode: 14 linhas → 7 bins corretos (1.0, 1.05, 1.1, 1.15, 1.2, 1.25, 1.3)
- Simulação end-to-end load mode: 3 linhas → sem explosão cartesiana, sem regressão
- Fallback de binning funcional: quando `sweep_x_col` configurada não existe na final_table, resolve para `Sweep_Value_mean_of_windows_x`

## Pendências

- Re-rodar o pipeline real em `E:\raw_pyton\raw_Lean_Sweep` para confirmar bins corretos com dados reais
- Verificar se o output de datasets anteriores (NANUM load mode) não sofre regressão
