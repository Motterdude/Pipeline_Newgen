# 2026-06-12 — co-delta-mode-diff

## O que mudou

- `runtime/compare_iteracoes/specs.py`: `delta_mode` das duas métricas de CO trocado de `ratio` para `diff`:
  - `metric_id: "co"` (CO medido)
  - `metric_id: "co_g_kwh"` (CO específico)
- Comentários explicativos adicionados no spec do `co` (causa raiz) e referência cruzada no `co_g_kwh`.
- `tests/test_compare_iteracoes.py`: 3 testes novos
  - `test_co_metrics_use_diff_mode` — trava de regressão: garante que ambas as métricas de CO usam `diff`.
  - `test_delta_diff_mode_propagates_uncertainty` — prova que o modo `diff` propaga a incerteza via GUM (`U_delta = K·√(uc_l² + uc_r²)`) e marca significância.
  - `test_delta_diff_survives_near_zero_baseline` — prova que o ponto com Baseline ~0 (que estourava no `ratio`) produz delta absoluto finito e pequeno no `diff`.

## Por quê

Nos últimos resultados (`out_nanum_post_injector_fix_..._New_Metrics`), os deltas de CO na aba `compare` apareciam com spikes absurdos (−10687%, −6593%, +2287%...) que não existiam no overlay das curvas. Investigação confirmou que **não são spikes físicos**: o CO dessa campanha vive no chão de ruído do analisador (mediana ~0.005 %vol, ~37% das leituras negativas oscilando em torno de zero, incerteza expandida U_CO ≈ 0.058 %vol maior que o próprio sinal). O delta percentual `100·(adt/base − 1)` explode quando o Baseline ≈ 0 — é um artefato matemático de divisão por quase-zero, não um fenômeno.

O usuário queria mostrar honestamente que "o CO já era baixo e a diferença ficou dentro da incerteza", sem o delta percentual passando por zero. Avaliadas as opções (clamp de negativos — rejeitada por introduzir viés de +12% na média; gating por LOQ; ler `significancia_95pct`; ratio com clamp de denominador), a escolha foi **delta absoluto (`diff`)** porque: (1) é a métrica honesta para sinal no chão de ruído, (2) o ramo `diff` já existente em `delta.py` propaga e expõe a incerteza de medição (mesmo caminho de CO2/O2/n_th/MFB), atendendo o requisito "com incerteza demonstrada", e (3) não altera quais séries são comparadas.

Validação numérica no ponto que estourava (27.5kW média): `ratio` dava −10729% (U=15M%); `diff` dá +0.0087 %vol (U=0.163 %vol). Mesma conclusão (dentro de U), agora legível.

## Arquivos

- `src/pipeline_newgen_rev1/runtime/compare_iteracoes/specs.py` (modificado)
- `tests/test_compare_iteracoes.py` (modificado)

## Validação

- `python -m unittest discover -s tests -p "test_*.py"` → 549 testes, 10 erros **pré-existentes** em `test_bridge_*` (importam classes de bridge removidas em 2026-04-25; sem relação com esta mudança). Nenhuma falha nova.
- `tests/ → python -m unittest test_compare_iteracoes` → **47 testes, OK** (inclui os 3 novos).
- Simulação com valores reais do Excel comprovou: spike −10729% → +0.0087 %vol com U_delta=0.163 propagado.

## Pendências

- **Re-rodar o pipeline** sobre a campanha (com o `adt_sub_3` já removido pelo offset) para regenerar `lv_kpis_clean.xlsx` com a aba `compare` usando o novo `diff`. Mudança em `src/` precisa ser sincronizada com a cópia git antes de qualquer Save & Run real (duplo working copy).
- Os 10 testes `test_bridge_*` órfãos merecem uma limpeza própria (fora do escopo desta sessão) — referenciam bridges já portados.
- Relacionado: `project_co_resolution_fix_pending` — o U_CO ≈ 0.058 pode estar inflado pela `resolution=0.1` do `instruments.toml`; mesma raiz (CO de baixíssima leitura mal condicionado).
