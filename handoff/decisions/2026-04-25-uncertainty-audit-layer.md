# 2026-04-25 — uncertainty-audit-layer

Status: ativa e vinculante.

## Decisão

Adicionar, em todo `lv_kpis_clean.xlsx` produzido pelo newgen, **colunas de auditoria de incerteza passo-a-passo** para um conjunto controlado de grandezas medidas e derivadas. Implementação em uma nova estação nativa `enrich_final_table_audit` rodando **depois** do `build_final_table` e **antes** do `export_excel` no `STAGE_PIPELINE_ORDER`.

Por grandeza `<m>` em `AUDITED_MEASURANDS`:

- `uB_res_<m>` — componente de resolução do uB, `√(Σ (resolution_i/√12)²)` sobre todos os componentes `i` do instrumento (**apenas para grandezas com instrumento direto**).
- `uB_acc_<m>` — componente de acurácia do uB, `√(Σ (limit_i/fator_dist_i)²)` onde `limit_i = |x|·acc_pct + acc_abs + |digits·lsd|` e `fator_dist = √3` se `dist="rect"`, 1 se `dist="normal"` (**apenas para grandezas com instrumento direto**).
- `pct_uA_contrib_<m>` — `100·uA²/uc²`, **variance-weighted**.
- `pct_uB_contrib_<m>` — `100 − pct_uA_contrib_<m>`.

As colunas preexistentes (`uA_<m>`, `uB_<m>`, `uc_<m>`, `U_<m>`) **continuam sendo populadas** pela cadeia legada + port nativo. O audit layer **só adiciona**, nunca sobrescreve.

## Grandezas auditadas (13)

**Medidas (6)**: `Consumo_kg_h`, `P_kw`, `NOx_ppm`, `CO_pct`, `CO2_pct`, `THC_ppm`.  
**Derivadas (7)**: `Consumo_L_h`, `n_th_pct`, `BSFC_g_kWh`, `NOx_g_kWh`, `CO_g_kWh`, `CO2_g_kWh`, `THC_g_kWh`.

`Consumo_kg_h` é listado como medida apesar de não ter instrumento direto (é derivada de balance_kg × Δt); o uB não se decompõe em unidade coerente, então `instrument_key=None` e as colunas `uB_res`/`uB_acc` NÃO são emitidas pra essa grandeza. As %contribuições continuam válidas porque dependem de uA/uB agregados (existentes no `final_table`).

## Motivação

Três perguntas frequentes de auditoria que o xlsx atual NÃO responde:

1. **Quanto da incerteza vem da resolução vs acurácia do instrumento?** Só o uB total estava exportado. A decomposição `uB_res`/`uB_acc` separa os dois mecanismos — útil para decidir se o gargalo é resolução (trocar instrumento) ou acurácia (recalibrar).
2. **Quanto da incerteza combinada vem da estabilidade (uA) vs do instrumento (uB)?** `pct_uA_contrib_var` responde diretamente. Em pontos onde uA domina (>70%), o gargalo é repetibilidade do ensaio; onde uB domina, é metrologia.
3. **As derivadas seguem propagação estatisticamente correta?** Para `n_th`, `BSFC`, `Consumo_L_h`, `emissões g/kWh`, o audit layer **computa nativamente** o split uA/uB via partials GUM §5 quando o legado só expõe uc. Isso garante coerência com as decisões `uB-correlacionado-em-media-de-campanha` e `propagacao-delta-via-uc-direto` de 2026-04-25.

## Fórmula variance-weighted para contribuição (GUM §F.1.2.4)

```
uc² = uA² + uB²
%uA_contrib_var = 100 · uA² / uc²     (range 0-100)
%uB_contrib_var = 100 − %uA_contrib_var
```

Sempre soma 100%. Escolhida em detrimento da forma linear (`uA/uc·100`) porque `uc` é a raiz da **soma de variâncias** — a contribuição natural em metrologia é em variância, não em desvio padrão. GUM §F.1.2.4 explicita essa decomposição.

## Forma da entrada (stage registry)

```python
# runtime/stages/__init__.py
PROCESSING_STAGE_ORDER = (
    "run_time_diagnostics",
    "build_final_table",
    "enrich_final_table_audit",   # <-- aqui
    "export_excel",
    "run_unitary_plots",
)
```

E em `workflows/load_sweep/feature_flags.py`:

```python
FeatureSpec(
    key="enrich_final_table_audit",
    label="Enrich final table with uncertainty audit",
    description="Add per-measurand uB_res, uB_acc, and variance-weighted %uA/%uB contribution columns.",
    stage="processing",
    default_by_mode={"load": True, "sweep": True},
    legacy_anchor="",   # nativa, sem contraparte no galpão
),
```

## Consequências

- `LOAD_SWEEP_FEATURE_SPECS` passa de 15 para 16 entradas (17 se contar `build_final_table` anterior). `show-plan` agora lista `enrich_final_table_audit` na seção `processing`.
- `lv_kpis_clean.xlsx` do newgen ganha ~30 colunas de auditoria (6 medidas × 2 cols uB_decomp + 13 × 2 cols pct_contrib − duplicações). Largura aumenta mas informação é acionável.
- Paridade de plots não é afetada (audit layer só toca o xlsx, não plots).
- `scripts/compare_cycle.py` vai reportar as novas colunas como "extra_in_newgen" — esperado e aceito.
- Quando o Passo 3b.3 (port nativo completo de `build_final_table`) vier, o audit layer pode migrar pra dentro da estação nativa OR continuar como enrichment separado; a decisão fica pra lá.
- **Não** mexe em `legacy_monoliths/`. O drift de 53 colunas de emissões g/kWh continua — o audit layer consome o que estiver presente.

## Decisões irmãs

- `2026-04-25-uB-correlacionado-em-media-de-campanha.md` — regra de agregação de média. O audit layer reporta `pct_uA_contrib` em cada ponto, o que permite auditar se a regra está sendo aplicada corretamente (uA encolhe com √N na média, uB não).
- `2026-04-25-propagacao-delta-via-uc-direto.md` — propagação do delta. O audit layer não opera sobre o delta (isso é função do compare_iteracoes), mas fornece o `uc_<m>` por lado que a fórmula do delta consome.
- `2026-04-25-derivadas-expor-uA-uB-separados.md` — requisito de separação uA/uB em derivadas. O audit layer satisfaz esse contrato ao calcular nativamente o split para `n_th_pct`, `BSFC_g_kWh`, `Consumo_L_h` e emissões específicas.

## Não cobre (escopo futuro)

- **Passo 3b.2** — UI para mapeamento variável→instrumento com preview de incerteza. Depende do audit layer estar estável.
- **Passo 3b.3** — port nativo completo de `build_final_table`. O audit layer ficará embutido na estação nativa nesse momento.
- Componentes adicionais de uB (ambiente, drift temporal, auto-zero): fora de escopo enquanto não houver demanda concreta.
