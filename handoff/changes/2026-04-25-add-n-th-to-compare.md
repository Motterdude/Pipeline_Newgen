# 2026-04-25 — add-n-th-to-compare

## O que mudou

### 1. Adição funcional — métrica n_th no compare_iteracoes

- **`nanum-pipeline-28-main/nanum_pipeline_29.py`** (galpão antigo):
  - +1 linha após `U_n_th_pct`: `df["uc_n_th_pct"] = df["uc_n_th"] * 100.0` — expõe o uc em ponto percentual que o agregador genérico do compare busca por convenção `uc_<metric_col>`.
  - +8 linhas em `COMPARE_ITER_METRIC_SPECS`: nova entrada com `metric_id="n_th"`, `metric_col="n_th_pct"`, `value_name="n_th_pct"`, label "Eficiencia termica" e filename_slug "n_th_pct".
- **`src/pipeline_newgen_rev1/legacy_monoliths/nanum_pipeline_29.py`** (cópia transitória no newgen): mesmas edições, sincronia manual.
- **`config/pipeline29_text/compare.toml`**: 3 entradas novas (media-vs-media, subida-vs-subida, descida-vs-descida) para `metric_id = "n_th"`, todas habilitadas.

### 2. Fix estatístico — uc_delta_pct via partials × uc direto (GUM §5)

- Fix em `_build_compare_metric_delta_table` (~linhas 6940-6950 do legado, espelhado em `legacy_monoliths/`).
- `uc_delta_pct` agora é calculado direto via `sqrt((∂δ/∂r · uc_r)² + (∂δ/∂l · uc_l)²)` em vez de `sqrt(uA_delta² + uB_delta²)`. Matematicamente idêntico quando uA/uB estão presentes, mas também funciona para métricas derivadas (η_th) cujo uc veio por propagação analítica e não tem uA/uB separados. Fallback para o caminho antigo se `uc` estiver ausente.
- Formalizado em `handoff/decisions/2026-04-25-propagacao-delta-via-uc-direto.md`.

### 3. Fix estatístico — uB sistemático NÃO encolhe na média subida+descida

- Fix em `_mean_subida_descida_per_campaign_metric` (genérico) e `_mean_subida_descida_per_campaign` (consumo-específico) — ambos no legado e em `legacy_monoliths/`.
- **Antes**: `uB(mean) = √(uB_sub² + uB_des²) / 2` (trata como IID, encolhe por √2).
- **Depois**: `uB(mean) = (uB_sub + uB_des) / 2` (trata como 100% correlacionado — mesmo instrumento, mesma campanha, ρ=1).
- uA continua reduzido por 1/√N (aleatório, IID entre janelas) — inalterado.
- Fallback para uc (quando uA/uB ausentes, caso n_th): `uc(mean) = (uc_sub + uc_des)/2`.
- **Afeta** todas as métricas na coluna "média × média": consumo, CO, CO2, NOx, O2, THC, n_th. Subida×subida e descida×descida **não** são afetadas (n=1 por ponto, agregador não é chamado).
- Formalizado em `handoff/decisions/2026-04-25-uB-correlacionado-em-media-de-campanha.md`.
- Impacto empírico em U_delta média: η_th 1,60→2,26 %; consumo 0,90→1,02 %.

### 4. Tooling e plots de apresentação

- **`scripts/run_legacy_compare_n_th.py`** (novo — ~220 linhas): driver que roda o legado end-to-end em tempdir sobre `E:\raw_pyton\raw_NANUM`, monkey-patcha os popups, isola `LOCALAPPDATA`, copia config com `RAW_INPUT_DIR`/`OUT_DIR` sobrescritos. Lê o `compare_iteracoes_metricas_incertezas.xlsx` gerado, recomputa delta_pct a partir dos valores unitários de `lv_kpis_clean.xlsx`, e confirma consistência. Gera 3 PNGs de análise + CSV de recompute-vs-report.
- **`scripts/replot_n_th_individual.py`** (novo): 3 absolutos + 3 deltas pra η_th em padrão de apresentação. BL azul, ADTV vermelho, delta verde, 4:3 (1280×960 @ dpi 200). Escala absoluta travada 8-33% step 2; escala delta compartilhada entre rampas step 2.
- **`scripts/replot_consumo_individual.py`** (novo): análogo para consumo, com nota interpretativa "negativo = melhor consumo".
- **`scripts/compare_cycle.py`** (novo, sessão anterior mas validado hoje): driver de paridade legado×newgen em tempdir.
- **`scripts/plot_uncertainty_consumption.py`**, **`scripts/diagnose_nox_inversion.py`**, **`scripts/evaluate_media_comparison.py`** (novos): suporte a análises do dia — investigação do "viés entre dias" que causava inversão aparente de NOx subida/descida, confirmado como problema de dados (campanhas em dias diferentes), não de processamento.

## Por quê

O usuário pediu um plot de eficiência térmica dentro da compare BL×ADTV, e pediu pra validar que o resultado da compare faz sentido vs os valores unitários de η_th plotados anteriormente por iteração (`plots/compare/<ramp> vs <ramp>/nth_vs_power_all.png`).

Como o `run_compare_iteracoes` ainda é 🔴 no stages_status (não tem bridge nem estação nativa), a única via pra ter o plot novo hoje é editar o monolito legado. O caminho é 20× mais barato que bridgear compare_iteracoes primeiro: a infra genérica (`_prepare_compare_metric_points`, `_aggregate_compare_metric_with_uncertainty`, `_plot_compare_metric_absolute`, `_plot_compare_metric_delta_pct`) já resolve qualquer métrica do final_table que tenha `metric_col`, `U_<metric_col>` e `uc_<metric_col>` disponíveis. A η_th já tinha `n_th_pct`, `U_n_th_pct`, `uc_n_th` — só faltava `uc_n_th_pct` para fechar a convenção.

Durante a implementação, apareceram **dois bugs estatísticos** que não eram imediatos no primeiro diagnóstico:

1. **U_delta_pct saía NaN para η_th** porque a propagação do delta usava o caminho uA/uB-separados, e η_th só expõe uc. Fix 2 acima corrige via caminho direto por uc (GUM §5).
2. **U_delta_media saía menor que U_delta_subida e U_delta_descida** para todas as métricas, tipicamente por fator √2. Investigação revelou que o agregador tratava uB (sistemática, compartilhada pelo mesmo instrumento em subida e descida da mesma campanha) como aleatória independente, aplicando incorretamente a redução 1/√N. Fix 3 corrige usando a regra GUM §F.1.2.4 para grandezas correlacionadas.

Ao rodar o driver, três coisas ficaram provadas:

1. **Consistência numérica**: o delta_pct recomputado a partir dos valores unitários do `lv_kpis_clean.xlsx` bate com o reportado em `compare_iteracoes_metricas_incertezas.xlsx` a **0,0000 pct absoluto em todos os 54 pares** (18 loads × 3 rampas × n_th). A agregação do compare não introduz distorção; ela é matematicamente equivalente ao plot unitário pré-existente `nth_vs_power_all.png`.
2. **Coerência física**: o delta η_th fica em ±3 % em todas as rampas e cargas, enquanto o NOx da mesma raw dava ±20 % e o consumo dava ~±0,5 %. Isso bate com a fórmula η_th = P/(ṁ·LHV) no setup operacional (dinamômetro com setpoint de P, LHV idêntico entre BL/ADTV) — η_th só mexe via consumo, e o consumo mexe pouco. Todos os pontos com `significancia_95pct = diferenca_dentro_de_U`. Interpretação física: aditivo ataca química de formação de NOx sem penalizar eficiência energética.
3. **Uniformidade pós-fix**: após o Fix 3, U_delta média bate com subida e descida (todas em ~2,25% para η_th, ~1,0-1,3% para consumo) — resultado esperado fisicamente, já que os três usam exatamente o mesmo instrumento e a mesma propagação.

## Arquivos

- `C:\Temp\np28_git_main_20260422\nanum-pipeline-28-main\nanum_pipeline_29.py` (modificado — fora do repo newgen, galpão antigo)
- `src/pipeline_newgen_rev1/legacy_monoliths/nanum_pipeline_29.py` (modificado — cópia no newgen, mantida em sincronia)
- `config/pipeline29_text/compare.toml` (modificado — +30 linhas, 3 novas entradas `n_th`)
- `scripts/run_legacy_compare_n_th.py` (novo)
- `scripts/replot_n_th_individual.py` (novo)
- `scripts/replot_consumo_individual.py` (novo)
- `scripts/compare_cycle.py`, `scripts/plot_uncertainty_consumption.py`, `scripts/diagnose_nox_inversion.py`, `scripts/evaluate_media_comparison.py` (novos)
- `handoff/changes/2026-04-25-add-n-th-to-compare.md` (novo — este arquivo)
- `handoff/CHANGES_INDEX.md` (nova linha)
- `handoff/decisions/2026-04-25-uB-correlacionado-em-media-de-campanha.md` (novo)
- `handoff/decisions/2026-04-25-propagacao-delta-via-uc-direto.md` (novo)
- `handoff/decisions/2026-04-25-derivadas-expor-uA-uB-separados.md` (novo)

## Validação

- `python -m unittest discover -s tests -p "test_*.py"` → **61 testes OK**, 0 skip (rodado 2x — antes e depois do fix de propagação).
- `python scripts/run_legacy_compare_n_th.py` (2ª rodada, após o fix) → rc=0; 6 PNGs nativos + 3 PNGs de análise com escalas corretas (abs 10-35% step 2; delta -5 a +5% step 0,5).
- Recompute vs report: `max |delta_recomp - delta_report| = 0.0000 pct` em todos os 18 loads das rampas subida e descida.
- **U_delta_pct populado** após o fix: descida ~1,8-3,9%; media ~1,3-2,7% (menor por n=2 por lado); subida ~1,8-4,0%. Dos 54 pares, apenas 1 ponto (subida @ 10 kW, `|delta|/U_delta = 1,048`) ultrapassa U em 95% — abaixo dos ~2,7 falsos positivos esperados por acaso num conjunto de 54. Confirma que o aditivo não mexe em η_th.
- Tempdir preservado em `C:\Users\sc61730\AppData\Local\Temp\legacy_n_th_compare_2yw8sf9h\`.
- Nenhum diretório operacional tocado (`E:\out_Nanum` intacto).

## Pendências

- **OneDrive sync**: as edições no monolito e o compare.toml precisam ser copiados pra `C:\Users\sc61730\OneDrive - Stellantis\Pessoal\pipeline_newgen\config\pipeline29_text\compare.toml` e ao `legacy_monoliths\nanum_pipeline_29.py` dessa cópia operacional antes do próximo Save & Run.
- **A cópia no galpão antigo** (`C:\Temp\np28_git_main_20260422\nanum-pipeline-28-main\nanum_pipeline_29.py`) está fora do repo Pipeline_newgen_rev1, não entra no `git status` desta árvore. É só referência.
- **Bridge `run_compare_iteracoes`**: Passo 2d sugerido em mudanças anteriores. Quando for feito, a cópia em `legacy_monoliths/` já carrega as edições — é só passar o `final_table` inteiro pro legado.
- **Port nativo das derivadas** (Passo 3b): expor uA/uB separados para η_th, BSFC, Consumo_L_h, emissões específicas g/kWh. Ver decisão `2026-04-25-derivadas-expor-uA-uB-separados.md`. Isso permite eventualmente remover o branch de fallback "só uc" na agregação.
- **Port nativo da agregação** (Passo 3c): levar os Fix 2 e Fix 3 para o módulo nativo do compare_iteracoes, com testes unitários fixados contra as regras GUM das decisões.
