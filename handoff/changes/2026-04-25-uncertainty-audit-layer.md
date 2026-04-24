# 2026-04-25 — uncertainty-audit-layer (Passo 3b.1)

## O que mudou

Novo audit layer nativo de incerteza: para 13 grandezas-chave do `lv_kpis_clean.xlsx`, o newgen agora reporta colunas passo-a-passo de incerteza + indicador de contribuição `%uA_contrib_var` / `%uB_contrib_var` (variance-weighted, GUM §F.1.2.4).

- **`src/pipeline_newgen_rev1/runtime/uncertainty_audit/`** (subpacote novo, ~500 linhas):
  - `specs.py` — `MeasurandSpec` dataclass + `AUDITED_MEASURANDS: tuple` com 13 entradas (6 medidas + 7 derivadas).
  - `decomposition.py` — `decompose_uB(value, instrument_key, instruments)` retorna `(uB_res, uB_acc)`. Port fiel de `uB_from_instruments_rev2` do legado (linhas 4880-4933), mas **separa** os dois termos em vez de RSSeá-los. `uB_res_i = resolution_i/√12` por componente, `uB_acc_i = (acc_abs + acc_pct·|x| + digits·lsd)/fator_dist` (√3 se rect, 1 se normal). RSS entre componentes dentro de cada termo.
  - `contribution.py` — `contribution_var(uA, uc) = 100·(uA/uc)²`. Tratamento de NaN/zero: retorna NaN se uc ausente ou zero.
  - `derived_propagation.py` — propagação nativa de `uA_<m>` e `uB_<m>` (separados) para as derivadas `Consumo_L_h`, `n_th`/`n_th_pct`, `BSFC_g_kWh`, e emissões `g/kWh` (CO, CO2, NOx, THC) via partials GUM §5. Para `n_th` isto é inédito — o legado só expõe `uc_n_th`.
  - `core.py` — orquestrador `enrich_final_table_with_audit(final_table, instruments) -> final_table`. Para cada spec: (a) decompõe uB em uB_res/uB_acc se tem instrumento direto; (b) propaga uA/uB nativo se for derivada sem split; (c) combina uc = √(uA²+uB²) e U = 2·uc se ausentes; (d) adiciona pct_uA_contrib_var e pct_uB_contrib_var. **Só adiciona colunas, nunca sobrescreve.**
  - `__init__.py` — exports públicos.
- **`src/pipeline_newgen_rev1/runtime/stages/enrich_final_table_audit.py`** (novo) — estação `EnrichFinalTableAuditStage` (dataclass frozen). Thin wrapper que lê `ctx.final_table` + `ctx.bundle.instruments`; chama `enrich_final_table_with_audit`; loga quantas colunas foram adicionadas.
- **`src/pipeline_newgen_rev1/runtime/stages/__init__.py`** — nova entrada em `STAGE_REGISTRY` + `PROCESSING_STAGE_ORDER` inserida entre `build_final_table` e `export_excel`.
- **`src/pipeline_newgen_rev1/workflows/load_sweep/feature_flags.py`** — 17ª `FeatureSpec`: `key="enrich_final_table_audit"`, `stage="processing"`, default on em load e sweep.
- **`tests/test_uncertainty_audit.py`** (novo — 12 casos):
  - Decomposição: resolution-only, accuracy-only, combined matches total, stacking RSS, no-matching-key.
  - Contribuição: basic (3/4/5 triangulo → 36%), sums to 100, handles zero/NaN.
  - Propagação derivada: n_th formula bate analítica.
  - Integração: enrich adiciona as colunas esperadas, preserva originais, %contrib soma 100 para measured.
- **`tests/test_orchestrator.py`** — ajuste: `total_steps` passou de 15 para 16 (nova feature).
- **`handoff/decisions/2026-04-25-uncertainty-audit-layer.md`** (novo).
- **`handoff/function_cards/stage_enrich_final_table_audit.fnctx.md`** (novo).
- **`handoff/stages_status.md`** — nova linha "Audit layer de incerteza" 🟢 em Fase 2.
- **`handoff/changes/2026-04-25-uncertainty-audit-layer.md`** (este arquivo).
- **`handoff/CHANGES_INDEX.md`** — entrada nova.

## Por quê

O usuário pediu auditoria passo-a-passo da incerteza expandida (σ, uc, U, componentes de uB, dependências de resolução) + um **novo indicador** que mostre o percentual de contribuição da estabilidade (uA) vs da resolução do instrumento (uB) ao uc combinado, seguindo padrões GUM.

Antes do 3b.1, o `lv_kpis_clean.xlsx` só exportava `uA`, `uB`, `uc`, `U` agregados por grandeza — o usuário não podia ver:

1. **De onde vem o uB** — calibração ou resolução? `uB_res_<m>` e `uB_acc_<m>` respondem.
2. **Se o ponto é ruidoso ou preciso** — o `pct_uA_contrib_var` mostra imediatamente. Se >70%, a medição é o gargalo; se <30%, o instrumento é o gargalo.
3. **Como as derivadas decompõem** — `n_th_pct` só tinha `uc_n_th`, sem split uA/uB. Agora tem ambos computados nativamente pela lei de propagação.

Escolha da fórmula variance-weighted (`100·uA²/uc²`) em detrimento da linear: `uc² = uA² + uB²`, então a contribuição natural é em **variância** (soma 100%). A linear `uA/uc·100` nunca soma 100% porque uc não é soma linear — seria enganoso para leigos e incorreta para engenharia metrológica.

Arquitetura: audit layer **nativo depois da bridge** (Opção A do plano). A bridge `BuildFinalTableBridgeStage` continua construindo `ctx.final_table` como antes; o audit layer roda **depois** apenas adicionando colunas. Quando o port nativo completo de `build_final_table` vier (Passo 3b.3), o audit layer pode migrar pra dentro ou continuar como enrichment — decisão isolada.

Sobre a interface de mapping variável→instrumento discutida (Passo 3b.2): ficou para sessão separada. Requer modificações na GUI legada preservada (`ui/legacy/pipeline29_config_gui.py`) e é significativa o suficiente para merecer planejamento próprio.

## Arquivos

- `src/pipeline_newgen_rev1/runtime/uncertainty_audit/__init__.py` (novo)
- `src/pipeline_newgen_rev1/runtime/uncertainty_audit/specs.py` (novo)
- `src/pipeline_newgen_rev1/runtime/uncertainty_audit/decomposition.py` (novo)
- `src/pipeline_newgen_rev1/runtime/uncertainty_audit/contribution.py` (novo)
- `src/pipeline_newgen_rev1/runtime/uncertainty_audit/derived_propagation.py` (novo)
- `src/pipeline_newgen_rev1/runtime/uncertainty_audit/core.py` (novo)
- `src/pipeline_newgen_rev1/runtime/stages/enrich_final_table_audit.py` (novo)
- `src/pipeline_newgen_rev1/runtime/stages/__init__.py` (modificado — registry + order)
- `src/pipeline_newgen_rev1/workflows/load_sweep/feature_flags.py` (modificado — 17ª spec)
- `tests/test_uncertainty_audit.py` (novo)
- `tests/test_orchestrator.py` (modificado — 15→16)
- `handoff/decisions/2026-04-25-uncertainty-audit-layer.md` (novo)
- `handoff/function_cards/stage_enrich_final_table_audit.fnctx.md` (novo)
- `handoff/stages_status.md` (atualizado)
- `handoff/changes/2026-04-25-uncertainty-audit-layer.md` (novo — este arquivo)
- `handoff/CHANGES_INDEX.md` (nova entrada)

## Validação

- `python -m unittest discover -s tests -p "test_*.py"` → **80 testes OK**, 0 skip (era 68; +12 novos do audit + 1 ajuste de orchestrator).
- `py_compile` → OK em todos os novos.
- `python scripts/compare_cycle.py` → `rc_legacy=0`, `rc_newgen=0`, plots 56/56 byte-idênticos (sem regressão), xlsx ganha ~32 colunas de auditoria.
- **Validação numérica manual** num ponto real do `raw/subindo_aditivado_1/`:
  - Consumo_kg_h = 1,893: uA=0,01233, uB=0,01133, uc=0,01675, U=0,03350 (1,77%), **pct_uA_contrib = 54,2%**, pct_uB_contrib = 45,8%. Soma = 100%. ✓
  - P_kw em idle (x=0): uA=0, uB_res=0, uB_acc=0,01155 (vem de digits·lsd/√3), uc=0,01155, **pct_uA_contrib = 0%**, pct_uB_contrib = 100%. Soma = 100%. ✓
  - Math verificado: `uA²/uc² = 0,01233²/0,01675² = 0,542 → 54,2%` ✓
- Nenhuma bridge modificada. Nenhuma coluna pré-existente sobrescrita.

## Pendências

- **Passo 3b.2** — UI de mapping variável→instrumento (discussão aberta). Depende: aba nova na `pipeline29_config_gui.py` migrada com dropdown de LV cols descobertas + dropdown de instruments + preview de incerteza calculada. Reduz atrito para criar novas entradas em Mappings + Instruments em sincronia.
- **Passo 3b.3** — port nativo completo de `build_final_table`. Quando vier, decidir se audit layer migra para dentro ou fica como enrichment.
- **Drift das 53 colunas em `legacy_monoliths/`** continua — não é objetivo deste passo. O port nativo completo (3b.3) resolve.
- **`scripts/compare_cycle.py`** agora reporta as ~32 novas audit cols como `extra_in_newgen`. Aceito até 3b.3 sincronizar as cópias.
- **Componentes adicionais de uB** (ambiente, drift, auto-zero): fora de escopo. Adicionar quando houver demanda específica.
