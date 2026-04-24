# Índice de mudanças

Ordem cronológica inversa. Uma linha por sessão. Detalhe completo em `handoff/changes/YYYY-MM-DD-slug.md`.

## 2026-04

- **2026-04-24** — [bridge-unitary-plots](changes/2026-04-24-bridge-unitary-plots.md) — Passo 2c: `RunUnitaryPlotsBridgeStage` gera plots via legado; paridade byte-a-byte do `lv_kpis_clean.xlsx` (19×511) e paridade de 37/37 PNGs confirmadas contra baseline standalone; 61 testes OK.
- **2026-04-24** — [bridge-build-final-table](changes/2026-04-24-bridge-build-final-table.md) — Passo 2b: cadeia de alimentação legado reproduzida; `BuildFinalTableBridgeStage` popula `ctx.final_table` e `export_excel` passa a gerar `lv_kpis_clean.xlsx` real; 58 testes OK (1 skip).
- **2026-04-24** — [bridge-scaffolding](changes/2026-04-24-bridge-scaffolding.md) — Passo 2a: 4 monolitos copiados para `legacy_monoliths/`, `bridges/legacy_runtime.py`, 1 bridge stage `export_excel` (no-op enquanto `final_table` None); 55 testes OK (1 skip).
- **2026-04-24** — [esteira-runtime-context](changes/2026-04-24-esteira-runtime-context.md) — `RuntimeContext` + registry de estações + 3 estações nativas extraídas do runner; 52/52 testes verdes.
- **2026-04-23** — [definicao-estrutura-registro](changes/2026-04-23-definicao-estrutura-registro.md) — Painel de estações, ritual de registro, skill `/log-change` e `CLAUDE.md` estabelecidos.
- **2026-04-23** — checkpoint operacional (pré-registro) — Save & Run ligado ao executor migrado; fix LabVIEW calamine; validação real em `raw_NANUM` com 133/76/19/0 erros. Detalhe em `HANDOFF_MASTER.md`.
