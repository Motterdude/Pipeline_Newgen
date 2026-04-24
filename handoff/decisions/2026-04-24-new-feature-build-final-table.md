# 2026-04-24 — new-feature-build-final-table

Status: ativa e vinculante.

## Decisão

Adicionar a feature `build_final_table` à `LOAD_SWEEP_FEATURE_SPECS`, na fase `processing`, habilitada por padrão em ambos os modos (`load` e `sweep`).

## Motivação

A decisão arquitetural de 2026-04-23 estabeleceu que "uma estação por entrada em `LOAD_SWEEP_FEATURE_SPECS`" e que "qualquer tentativa de adicionar stage fora do registro (`LOAD_SWEEP_FEATURE_SPECS`) requer uma nova entrada no registro e justificativa em um `handoff/decisions/` posterior".

O Passo 2b precisa expor a "montagem da tabela final" como estação do pipeline — é o ponto onde `ponto` + `fuel_properties` + `kibox_agg` + `motec_ponto` são unidos pelo `build_final_table` do legado e transformam-se no DataFrame que vira `lv_kpis_clean.xlsx`.

Características que justificam a entrada no spec:

- **É uma feature observável no plano** — o `show-plan` e a GUI de configuração (futura) devem listá-la.
- **Precisa de feature_key estável** — o `Stage.feature_key` é a chave do registry; a estação bridge `BuildFinalTableBridgeStage` e a futura estação nativa precisam compartilhar essa chave para trocarem de implementação sem churn no runner.
- **É sempre default habilitada** — é o core do processamento; desligá-la significa "não produzir a tabela final", equivalente a um dry-run.

## Forma da entrada

```python
FeatureSpec(
    key="build_final_table",
    label="Build final KPI table",
    description="Aggregate trechos/pontos, merge fuel properties and KiBox/MoTeC, produce the final lv_kpis table.",
    stage="processing",
    default_by_mode={"load": True, "sweep": True},
    legacy_anchor=legacy_anchor_for_feature("build_final_table"),
),
```

E em `bridges/legacy_pipeline30.py::LEGACY_PIPELINE30_ANCHORS`:

```python
"build_final_table": "nanum_pipeline_29.py::build_final_table",
```

## Consequências

- `LOAD_SWEEP_FEATURE_SPECS` passa de 15 para 16 entradas.
- `stages_status.md` ganha a linha "Montagem da tabela final" agora com feature_key (hoje é `—`).
- `show-plan` passa a listar `build_final_table` na seção `processing`.
- Essa feature precede `export_excel` no `STAGE_PIPELINE_ORDER` — a ordem é `... → build_final_table → export_excel`.
- Quando o port nativo ocorrer (Passo 3+), a entrada no spec permanece inalterada; só troca a classe registrada em `STAGE_REGISTRY["build_final_table"]`.
