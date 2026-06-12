# 2026-06-02 — qmax-compare-and-gui-state-fix

## O que mudou

- Adicionada métrica **QMAX** (`KIBOX_QMAX_1`) ao `compare_iteracoes/specs.py` — gera média×média, overlay e delta nos mesmos modos dos outros parâmetros KiBox.
- Corrigido typo no `config_gui_state.json` (`pipeline29_texta` → `pipeline29_text`) que fazia a GUI abrir com `config_dir` inexistente.
- Atualizado teste `test_metric_specs_count` de 39 → 40.

## Por quê

Usuário pediu adição do QMAX (taxa máxima de liberação de calor) ao módulo de compare, seguindo o mesmo padrão já usado para PMAX, RMAX, AQMAX etc.

Ao tentar usar a GUI depois, percebeu que a lista de "Workspaces Salvos" estava completamente vazia e que o último processamento de dados não gravou nos diretórios corretos. A causa raiz foi um typo no arquivo de estado persistente da GUI (`%LOCALAPPDATA%\pipeline_newgen_rev1\config_gui_state.json`): o campo `config_dir` apontava para `config/pipeline29_texta` (com "a" extra). Isso fez:
1. A GUI buscar workspaces num diretório inexistente → lista vazia.
2. O pipeline criar uma pasta `config/pipeline29_texta/` com configs parciais em vez de usar a pasta correta.
3. O xlsx de saída não ser carregado ao reabrir (workspace default buscava no dir errado).

## Arquivos

- `src/pipeline_newgen_rev1/runtime/compare_iteracoes/specs.py` (modificado — +8 linhas QMAX)
- `tests/test_compare_iteracoes.py` (modificado — contagem 39→40)
- `%LOCALAPPDATA%\pipeline_newgen_rev1\config_gui_state.json` (modificado — fix typo)

## Validação

- `python -m unittest discover -s tests -p "test_compare*"` → 65 tests OK
- Simulação offline da `_refresh_workspace_list` → 8 workspaces detectados corretamente
- Verificação do path corrigido via `default_app_state_dir()` → config dir existe, workspace file existe

## Pendências

- Deletar a pasta fantasma `config/pipeline29_texta/` (criada pelo pipeline ao rodar com typo) — requer confirmação do usuário.
- Não se sabe como o typo entrou no state file — possivelmente digitação acidental no campo "Text config dir" da GUI. Não há proteção contra paths inexistentes no save do state.
