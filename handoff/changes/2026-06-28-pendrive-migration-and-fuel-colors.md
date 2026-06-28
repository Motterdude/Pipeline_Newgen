# 2026-06-28 — Migração pen-drive + fix Series Colors all_fuels

## O que mudou

### 1. Migração para pen-drive (`E:\Mestrado\Pipeline_Newgen`)

- Inicializado `.git` no pen-drive com tracking de `origin/main` (GitHub).
- Criada pasta `config/workspaces/` — centraliza todos os workspace JSONs e presets.
- Movidos 13 workspaces de `config/pipeline29_text/` → `config/workspaces/`.
- Movido `pipeline29_legacy_bundle.json` de `config/presets/` → `config/workspaces/`.
- Removida pasta `config/presets/` (vazia).
- Atualizados paths internos (OneDrive → pen-drive) em:
  - Todos os workspace JSONs
  - `config/pipeline29_text/defaults.toml`, `metadata.toml`, `preview_presets.json`
  - `AppData\Local\pipeline_newgen_rev1\config_gui_state.json`
  - `AppData\Local\pipeline_newgen_rev1\pipeline30_runtime_paths.json`
- Corrigida corrupção (BOM UTF-8 + null bytes) causada por `Set-Content -Encoding utf8` do PowerShell 5.1.

### 2. `_workspace_file_path` → `config/workspaces/`

- **`preview_plot_tab.py`**: novo helper `_workspaces_dir()` retorna `config_dir.parent / "workspaces"` (criando se necessário). `_workspace_file_path()` e `_refresh_workspace_list()` usam essa pasta.
- **`pipeline29_config_backend.py`**: `default_preset_dir()` agora retorna `config/workspaces/`.

### 3. Fix Series Colors no modo `all_fuels_yx`

- **`preview_plot_tab.py` → `_open_series_colors_dialog`**: detecta `plot_type`; no modo fuel lista fuel labels via `fuel_plot_groups`, no modo iterations usa `_derive_series_column` (comportamento anterior).
- **`renderers.py`**: substituído `colors = fuel_colors or fuel_color_map(...)` por `colors = fuel_color_map(labels, fuel_colors)` em todas as 4 funções de plot. Garante que o dict de defaults é sempre processado (com ou sem overrides).
- **`fuel_colors.py` → `resolve_fuel_color`**: prioridade = direct key (`D85B15`) > prefixed key (`FUEL_COLOR_D85B15`) > hardcoded default. Permite que overrides do dialog sobrescrevam configuração da GUI.
- Overrides persistem via `series_styles` no workspace JSON.

## Por quê

- Migração: pen-drive será o local de execução principal (OneDrive deixa de ser working copy).
- Workspaces: nome intuitivo, lista populava de pasta incorreta quando `config_dir` divergia.
- Series Colors: nunca funcionou para `all_fuels_yx` (keys com prefixo `FUEL_COLOR_` não matchavam lookup direto por label).

## Arquivos

- `src/pipeline_newgen_rev1/ui/preview_plot_tab.py`
- `src/pipeline_newgen_rev1/ui/legacy/pipeline29_config_backend.py`
- `src/pipeline_newgen_rev1/runtime/unitary_plots/renderers.py`
- `src/pipeline_newgen_rev1/runtime/fuel_colors.py`
- `config/workspaces/` (nova pasta, 14 arquivos)
- `config/pipeline29_text/` (JSONs de workspace removidos)

## Validação

- `py_compile` OK em todos os 4 .py editados.
- 539/549 testes passam (10 erros pré-existentes em `test_bridge_*` por `_path` import no pen-drive).
- Teste manual: GUI abre, lista workspaces populada, Series Colors lista fuel labels, cores aplicadas no plot.

## Pendências

- Git clone em `C:\Temp\np28_git_main_20260422\Pipeline_newgen_rev1` está 7 commits atrás — sincronizar se for usar novamente.
- Considerar commit dos arquivos untracked (configs de preset do mestrado) para que fiquem versionados.
