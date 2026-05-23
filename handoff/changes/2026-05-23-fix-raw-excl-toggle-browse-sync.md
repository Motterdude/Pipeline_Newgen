# 2026-05-23 — fix-raw-excl-toggle-browse-sync

## O que mudou

- `_browse_data_file` (botão "Browse..." da barra superior): após carregar o arquivo, agora também popula `_raw_df` e `_raw_path` — mas SOMENTE se `_raw_df` ainda for None (não sobrescreve Browse Raw intencional). Isso faz com que o workflow natural "Browse → toggle" funcione sem precisar usar Browse Raw explicitamente.

- `_load_raw_excl_file` (usado por Browse Raw e Browse Excl): ao carregar o arquivo, agora também tenta ler a sheet `"compare"` e chama `_load_compare_from_df` se detectada. Isso garante que carregar o arquivo excl via Browse Excl também atualiza o compare mode.

## Por quê

Bug: o usuário usou "Browse..." (barra superior) para carregar o arquivo, que é o comportamento natural e esperado. Esse botão chama `load_data_from_file` que popula apenas `_loaded_df` — nunca `_raw_df`. Como `_get_effective_df()` só usa `_raw_df`/`_excl_df` quando são não-None, o toggle raw/excl caía sempre para `_loaded_df`, exibindo o mesmo arquivo independente da seleção. O usuário reportou "mesmo trocando de raw/excl no seletor, não muda".

A causa foi não ter sincronizado o Browse antigo com o novo sistema de fontes. O fix garante que qualquer arquivo KPI carregado pelo Browse da barra superior popula automaticamente o campo "raw" do toggle.

## Arquivos

- `src/pipeline_newgen_rev1/ui/preview_plot_tab.py` (modificado)

## Validação

- `py_compile` → OK
- `unittest` → 446 testes, 10 erros pré-existentes
- Simulação headless dos 3 cenários:
  - Cenário 1 (Browse antigo → excl): `_raw_df` setado com excl (203r), toggle permanece em 203 — correto para quem carregou só um arquivo
  - Cenário 2 (Browse antigo → raw, Browse Excl → excl): toggle=raw → 222, toggle=excl → 203 ✓
  - Cenário 3 (Browse Raw → raw, Browse antigo → excl depois): `_raw_df` NÃO sobrescrito (guard `_raw_df is None`), comportamento correto ✓

## Pendências

- Workflow correto documentado: Browse (barra sup) no arquivo raw → Browse Excl na barra inferior no arquivo pós-exclusão → Combo Ativo: alterna entre os dois.
