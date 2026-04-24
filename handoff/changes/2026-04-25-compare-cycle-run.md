# 2026-04-25 — compare-cycle-run

## O que mudou

- **`scripts/compare_cycle.py`** (novo) — driver unattended que roda o **legado `nanum_pipeline_29.main()`** end-to-end e o **newgen `run-load-sweep`** sobre o mesmo raw, cada um em tempdir próprio, e compara os outputs (`lv_kpis_clean.xlsx` via `DataFrame.equals`; PNGs de `plots/` via sha256 + tamanho). O driver:
  - monkey-patcha `prompt_plot_point_filter_from_metas` e `prompt_plot_point_filter` para retornar `None` (= sem filtro, todos os pontos);
  - isola `LOCALAPPDATA` num tempdir para não tocar o JSON operacional (`%LOCALAPPDATA%\nanum_pipeline_29\pipeline29_runtime_paths.json` aponta para `E:\out_Nanum` real);
  - copia `config/pipeline29_text/` para tempdir e reescreve `RAW_INPUT_DIR`/`OUT_DIR` em `defaults.toml`;
  - seta `PIPELINE29_USE_DEFAULT_RUNTIME_DIRS=1` e `PIPELINE29_SKIP_CONFIG_GUI_PROMPT=1` no subprocess legado;
  - chama newgen via CLI com `--config-dir / --process-dir / --out-dir` dedicados ao tempdir;
  - emite `compare_report.json` e preserva o tempdir ao final para inspeção manual.

## Por quê

O usuário pediu um **ciclo de compare entre newgen e pipeline_29** retomando o contexto de ontem (Passo 2c encerrou a trilogia de bridges 2a/2b/2c). Até ontem a validação de paridade era ad-hoc (smoke manual contra baseline standalone). Faltava uma rotina reprodutível que:
1. Não tocasse diretórios operacionais (`E:\raw_pyton\raw_NANUM`, `E:\out_Nanum_rev2`, `%LOCALAPPDATA%`);
2. Executasse o legado de forma não-interativa (main() tem 2 popups: dirs + filtro de pontos);
3. Quantificasse o gap entre as saídas — tanto paridade dos artefatos bridged quanto visibilidade do que ainda não foi portado.

Com `scripts/compare_cycle.py` o ciclo vira one-liner e o report fica máquina-legível. Importante para a transição da fase "bridge" para a fase "port nativo": cada port poderá reutilizar esse driver como smoke de não-regressão antes de commitar.

Resultado desta execução sobre `raw/subindo_aditivado_1/` (18 xlsx LabVIEW do legacy repo):

- **`lv_kpis_clean.xlsx`**: `DataFrame.equals == True` sobre 19×511; sha256 dos bytes difere (metadata do xlsx — timestamps, order de styles) mas o mesmo tamanho 79876 B.
- **Plots unitários**: 37/37 PNGs byte-idênticos no newgen.
- **Gap quantificado**: legado produz 56 PNGs, newgen 37. Os 19 ausentes são todos os plots do diagnóstico de tempo (`time_delta_by_file/*.png` + `time_delta_to_next_all_samples.png`), gerados pelo `build_time_diagnostics`/`summarize_time_diagnostics` no `main()` do legado. A estação `run_time_diagnostics` segue 🔴 em `stages_status.md` — gap esperado, não é regressão.

## Arquivos

- `scripts/compare_cycle.py` (novo)
- `handoff/changes/2026-04-25-compare-cycle-run.md` (novo — este arquivo)
- `handoff/CHANGES_INDEX.md` (entrada nova)

## Validação

- `python -m unittest discover -s tests -p "test_*.py"` → **61 testes OK**, 0 skip (pré-rodada do ciclo).
- `python scripts/compare_cycle.py` → `rc_legacy=0`, `rc_newgen=0`; report:
  - `kpis.dataframe_equals = true` (shape 19×511)
  - `plots.byte_identical_count = 37`, `plots.byte_different_count = 0`
  - `plots.missing_in_newgen = 19` (todos `time_delta_*`)
  - `plots.extra_in_newgen = 0`
- Tempdir preservado em `C:\Users\sc61730\AppData\Local\Temp\compare_cycle_txblbz14\` com `legacy_out/`, `newgen_out/`, `compare_report.json`, `legacy.log`, `newgen.log`.

## Pendências

- **Bridge ou port de `run_time_diagnostics`** fecharia o gap dos 19 PNGs ausentes — hoje é a única diferença observada entre o `main()` legado e o `run_load_sweep` do newgen para este raw.
- **Integrar o driver ao CI** (ou pelo menos a um alvo tipo `make compare` / `python -m pipeline_newgen_rev1.cli compare-cycle`) para cada port nativo rodar automaticamente antes de commit.
- **Raw alternativo com MoTeC + KiBox**: o dataset `subindo_aditivado_1/` é LV-only. Validar paridade em um raw com as três fontes (ex: `E:\raw_pyton\raw_NANUM`) continua sendo smoke manual — idealmente o driver aceitaria `--raw <dir>` como arg.
- **Normalizar o xlsx para byte-identical**: hoje `byte_identical=False` porque `safe_to_excel` aplica formatação que embute metadata não-determinística. Não é blocker (dataframe é igual) mas dificultaria um futuro hash-based regression test.
