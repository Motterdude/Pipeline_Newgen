# 2026-05-23 — exclusion-list-export-import-pipeline

## O que mudou

### Novo módulo: `exclusion_runner.py`
- `src/pipeline_newgen_rev1/runtime/exclusion_runner.py` (novo): funções para carregar JSON de exclusão (`load_exclusion_list`), construir set de `(basename, load_kw)` (`build_excluded_basename_set`), aplicar filtro ao DataFrame `ponto` (`apply_exclusions_to_ponto`), e varrer um diretório por JSONs válidos de exclusão (`scan_exclusion_lists`).

### Pipeline de processamento — aplicação no ponto
- `src/pipeline_newgen_rev1/runtime/context.py`: campo `exclusion_list_path: Optional[Path] = None` adicionado ao `RuntimeContext` e ao `from_kwargs`.
- `src/pipeline_newgen_rev1/runtime/stages/compute_trechos_ponto.py`: após `compute_ponto_stats`, se `ctx.exclusion_list_path` estiver preenchido, carrega a lista e remove as linhas matching `(BaseName, Load_kW)` antes de gravar `ctx.ponto`. Log `[INFO]` com nome do arquivo e linhas removidas.
- `src/pipeline_newgen_rev1/runtime/runner.py`: `run_load_sweep` aceita novo kwarg `exclusion_list_path: Optional[Path] = None` e repassa ao `RuntimeContext.from_kwargs`.

### GUI — seletor de exclusion list no helper de run
- `src/pipeline_newgen_rev1/ui/legacy/pipeline29_config_gui.py`:
  - Nova função `_show_exclusion_list_preview(path, parent)`: dialog read-only com tabela de 5 colunas (Serie, Load kW, Escopo, Razão, Data) para visualizar qualquer exclusion list JSON.
  - `Pipeline30SweepHelperDialog`: novos parâmetros `config_dir` e `initial_exclusion_list_path`; nova linha no form "Exclusion list" com combo de arquivos disponíveis (varredura via `scan_exclusion_lists`), botão "Ver lista..." e botão "Browse..."; `values()` retorna `"exclusion_list_path"`.
  - `Pipeline30ConfigEditor.__init__`: carrega `pipeline30_exclusion_list_path` dos runtime settings.
  - `_save_pipeline30_helper_settings`: persiste `exclusion_list_path` nos runtime settings JSON.
  - `_open_pipeline30_sweep_helper`: passa `config_dir` e `initial_exclusion_list_path` ao dialog; lê `exclusion_list_path` do retorno e salva em `self.pipeline30_exclusion_list_path`.
  - `main()`: lê `exclusion_list_path` dos runtime settings e passa como `exclusion_list_path=excl_path` ao `run_load_sweep`.

### Preview Plot — botão Export no dialog de exclusões
- `src/pipeline_newgen_rev1/ui/preview_plot_tab.py`: botão "Export..." adicionado ao `_open_exclusions_review`; salva o store como JSON com `type: exclusion_list` e `exported_at` timestamp; aponta por padrão para o config dir.

## Por quê

O usuário precisava de um ciclo completo: excluir pontos ruins no Preview Plot → exportar a lista → importar antes de re-rodar o pipeline → o pipeline descarta esses pontos antes do cálculo de médias (aditivados vs baselines). O ciclo anterior era manual (editar planilha) ou não existia.

A injeção no `ComputeTrechosPontoStage` foi escolhida como ponto de aplicação porque é o estágio mais cedo possível após a agregação por janelas mas antes de qualquer cálculo derivado (final_table, emissões, eficiência). Isso garante que nenhuma KPI seja afetada pelos dados excluídos.

O campo `basename` armazenado na exclusão durante o Preview Plot corresponde exatamente ao `BaseName` no DataFrame `ponto`, tornando o matching robusto sem necessidade de re-derivar labels de exibição.

## Arquivos

- `src/pipeline_newgen_rev1/runtime/exclusion_runner.py` (novo)
- `src/pipeline_newgen_rev1/runtime/context.py` (modificado — +exclusion_list_path)
- `src/pipeline_newgen_rev1/runtime/stages/compute_trechos_ponto.py` (modificado — aplica filtro)
- `src/pipeline_newgen_rev1/runtime/runner.py` (modificado — +exclusion_list_path kwarg)
- `src/pipeline_newgen_rev1/ui/legacy/pipeline29_config_gui.py` (modificado — seletor + persistência + pass ao run)
- `src/pipeline_newgen_rev1/ui/preview_plot_tab.py` (modificado — botão Export)

## Validação

- `python -m py_compile` → OK em todos os 6 arquivos
- `python -m unittest discover -s tests -p "test_*.py"` → 446 testes, 10 erros pré-existentes (bridges), sem regressão
- Sanidade de lógica: `apply_exclusions_to_ponto` retorna df inalterado se `BaseName`/`Load_kW` ausentes → seguro para DFs de sweep sem essas colunas

## Pendências

- Testes unitários para `exclusion_runner.py` (mock de DataFrame, verificar remoção correta de linhas).
- Testar ciclo completo: Export do Preview → abrir Sweep Helper → selecionar lista → Save & Run → verificar log `[INFO]` com linhas removidas → conferir `lv_kpis_clean.xlsx` sem os pontos excluídos.
- CLI `run-load-sweep` ainda não expõe `--exclusion-list` flag; pode ser adicionado se necessário para uso sem GUI.
