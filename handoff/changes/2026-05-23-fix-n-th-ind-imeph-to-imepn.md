# 2026-05-23 — fix-n-th-ind-imeph-to-imepn

## O que mudou

- `build_final_table` em `core.py`: cálculo de eficiência térmica indicada (`n_th_ind`) agora usa **IMEPN** (net = high-pressure + gas exchange) em vez de **IMEPH** (apenas high-pressure loop). Coluna buscada muda de `KIBOX_IMEPH_AVG_1` → `KIBOX_IMEPN_AVG_1`.

## Por quê

A eficiência térmica indicada estava superestimada (~41% a plena carga quando o esperado para diesel turbo é ~37-38%). O problema: IMEPH mede apenas o trabalho do loop de alta pressão (expansão − compressão), excluindo as perdas de bombeamento (admissão/escape). A definição padrão de eficiência indicada usa IMEP net (IMEPH + IMEPL), que desconta o trabalho gasto no gas exchange.

Consequência prática: η_mech (rendimento mecânico = P_eixo / P_indicada) aparecia ~76% a plena carga, fisicamente inconsistente para motor diesel moderno (esperado: 83-88%). Com IMEPN, η_mech sobe para ~83%, alinhado com a literatura.

Dados numéricos no ponto 45 kW D85B15 @ 1800 rpm:

| Métrica | IMEPH (antes) | IMEPN (depois) |
|---|---|---|
| IMEP | 9.33 bar | 8.55 bar |
| P_indicada | 55.9 kW | 51.2 kW |
| η_th,ind | 41.0% | 37.5% |
| η_mech | 76.3% | 83.2% |

## Arquivos

- `src/pipeline_newgen_rev1/runtime/final_table/core.py` (modificado — troca IMEPH→IMEPN no bloco 5a-bis)

## Validação

- `py_compile` → OK
- Análise numérica com dados de saída reais confirmou valores fisicamente consistentes

## Pendências

- Re-rodar pipeline com dados combustão para gerar output atualizado.
- Verificar plots no Preview Plot após re-run.
