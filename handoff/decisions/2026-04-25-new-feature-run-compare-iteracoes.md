# 2026-04-25 — new-feature-run-compare-iteracoes

Status: ativa e vinculante.

## Decisão

Adicionar a feature `run_compare_iteracoes` à `LOAD_SWEEP_FEATURE_SPECS`, na fase `plots`, habilitada por padrão em `load` e desabilitada em `sweep`.

## Motivação

A decisão arquitetural de 2026-04-23 estabeleceu que "uma estação por entrada em `LOAD_SWEEP_FEATURE_SPECS`" e que "qualquer tentativa de adicionar stage fora do registro requer uma nova entrada no registro e justificativa em um `handoff/decisions/` posterior".

O Passo 2d vai expor a geração dos plots comparativos BL × ADTV como estação do pipeline. Hoje essa geração acontece dentro do `main()` do legado via `_plot_compare_iteracoes_bl_vs_adtv` (`nanum_pipeline_29.py:~7056`), consumindo o `final_table` e a aba `compare` do config textual. A chamada deve virar uma estação independente com feature_key estável pra caber no fluxo check-box da GUI e permitir troca entre bridge e port nativo.

Características que justificam a entrada no spec:

- **É feature observável no plano** — o `show-plan` e a GUI de configuração precisam listá-la como toggle; hoje isso não existe mas é a pista de pouso.
- **Precisa de feature_key estável** — a bridge `RunCompareIteracoesBridgeStage` (Passo 2d) e a estação nativa (Passo 3c) usarão a mesma chave no `STAGE_REGISTRY`.
- **Default true em `load` mode** — o ensaio padrão do Nanum é BL vs ADTV em load, e esse compare é a principal saída visual.
- **Default false em `sweep` mode** — no sweep interessa comparar bins de parâmetro dentro de uma mesma campanha, não BL vs ADTV. A feature permanece desligada por padrão ali; se o usuário quiser cruzar os dois eixos, liga manualmente.
- **Depende de `build_final_table` estar habilitada** — sem `final_table` populado, o compare não pode rodar. Essa dependência deve ser validada na stage (skip graceful com log se `ctx.final_table is None`, padrão já usado nas bridges `export_excel` e `run_unitary_plots`).

## Forma da entrada

Em `workflows/load_sweep/feature_flags.py::LOAD_SWEEP_FEATURE_SPECS`:

```python
FeatureSpec(
    key="run_compare_iteracoes",
    label="Run compare BL vs ADTV (iteracoes)",
    description="Generate compare_iteracoes_bl_vs_adtv/ PNGs and metricas_incertezas.xlsx from the final table and the [compare] bundle config.",
    stage="plots",
    default_by_mode={"load": True, "sweep": False},
    legacy_anchor=legacy_anchor_for_feature("run_compare_iteracoes"),
),
```

Em `bridges/legacy_pipeline30.py::LEGACY_PIPELINE30_ANCHORS`:

```python
"run_compare_iteracoes": "nanum_pipeline_29.py::_plot_compare_iteracoes_bl_vs_adtv",
```

## Consequências

- `LOAD_SWEEP_FEATURE_SPECS` passa de 15 para 16 entradas (na verdade, se `build_final_table` já é 15ª, esta fica como 16ª; contar no momento do port).
- `handoff/stages_status.md`: a linha "Plots compare (subida × descida)" hoje tem feature_key `run_compare_plots` que NÃO é essa feature — `run_compare_plots` é o compare dentro de uma mesma campanha (subida vs descida, já listado como 🔴). A nova feature `run_compare_iteracoes` é uma linha nova, com seu próprio feature_key. Serão duas linhas distintas em Fase 3:
  - `run_compare_plots` (🔴) — compare dentro da campanha (_plot_compare_stable no legado)
  - `run_compare_iteracoes` (🔴 → 🟡 bridge no Passo 2d → 🟢 no Passo 3c) — compare BL × ADTV entre campanhas
- `show-plan` passa a listar `run_compare_iteracoes` na seção `plots`, default `on` em load.
- A ordem em `STAGE_PIPELINE_ORDER` é: `... build_final_table → export_excel → run_unitary_plots → run_compare_iteracoes → ...`. A estação consome `final_table` mas não depende de outputs das duas anteriores.
- Quando o port nativo ocorrer (Passo 3c), a entrada no spec permanece inalterada; só troca a classe registrada em `STAGE_REGISTRY["run_compare_iteracoes"]`.
- O port nativo (Passo 3c) deve encodar as regras das decisões:
  - `2026-04-25-uB-correlacionado-em-media-de-campanha.md` — agregação da média
  - `2026-04-25-propagacao-delta-via-uc-direto.md` — propagação do delta
  - `2026-04-25-derivadas-expor-uA-uB-separados.md` — satisfeita via Passo 3b, aqui consumida

## Decisões irmãs

- `2026-04-24-new-feature-build-final-table.md` — mesmo padrão: feature nova que entra como bridge primeiro e ganha port nativo depois.
