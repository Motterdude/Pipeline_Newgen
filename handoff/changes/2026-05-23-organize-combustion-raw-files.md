# 2026-05-23 — organize-combustion-raw-files

## O que mudou

- Criada a pasta `raw_nanum_post_injector_fix_renamed_combustion/` com 12 subpastas organizadas (Subindo/Descendo × Baseline/Aditivado × 1/2/3).
- 222 xlsx (LabVIEW, fonte: `Downloads/Nanum_rev2_labview/`) + 223 .open (KiBox combustão, fonte: `raw_nanum_post_injector_fix/Rev2_combustao/`) copiados e renomeados para convenção `D85B15_{load}kW.xlsx` + `D85B15_{load}kW_i.open`.
- Pareamento feito por valor de carga (kW) extraído dos nomes, com validação por timestamp embutido no nome do .open.

## Por quê

O usuário instalou o KiBox ToGo e quer processar os dados de combustão Rev2. As duas fontes (LabVIEW xlsx e KiBox .open) estavam em pastas separadas com nomes heterogêneos. A organização segue a mesma convenção de `raw_nanum_post_injector_fix_renamed/` para compatibilidade com o pipeline.

## Arquivos

- `raw_nanum_post_injector_fix_renamed_combustion/` (12 subpastas, 445 arquivos — novo)

## Validação

- Sanity check: 11/12 pastas 100% sincronizadas (cada xlsx tem .open e vice-versa)
- 1 anomalia de fonte: `Subindo_Baseline_2/35kW` tem .open mas não tem xlsx (ponto não salvo no LabVIEW)
- Grid completo (0–45 kW, step 2.5) em 9/12 pastas; 3 pastas com grid incompleto (dados de fonte, não bug)
- Duplicata tratada: `Descendo_Aditivado_3/45kW` tinha 2 .open (reteste) — mantido o primeiro da sessão

## Pendências

- `Subindo_Baseline_2/D85B15_35kW_i.open` sem par xlsx — se o xlsx existir em outra fonte, adicionar manualmente.
- Converter os .open para CSV quando o pipeline for rodado nesta pasta (botão "Converter .open faltantes" na GUI).
- Pastas `Descendo_Baseline_2` e `Descendo_Baseline_3` têm grid incompleto na fonte — confirmar com dados do banco se pontos baixos foram medidos.
