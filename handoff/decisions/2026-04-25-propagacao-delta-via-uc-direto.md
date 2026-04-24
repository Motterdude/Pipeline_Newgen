# 2026-04-25 — propagacao-delta-via-uc-direto

Status: ativa e vinculante.

## Decisão

A propagação de incerteza combinada para o `delta_pct` entre duas medições (ex.: ADTV vs BL no mesmo ponto de carga) usa **diretamente** a combinada de cada lado via lei de propagação GUM §5:

```
δ%                     = 100 · (value_right / value_left − 1)
∂δ/∂value_right        = +100 / value_left
∂δ/∂value_left         = −100 · value_right / value_left²
uc(δ%)                 = √( (∂δ/∂value_right · uc_right)²  +  (∂δ/∂value_left · uc_left)² )
U(δ%)                  = k · uc(δ%)    (k = 2)
```

**Não** é permitido recalcular `uc(δ%)` a partir de `uA(δ%)` e `uB(δ%)` combinados via `√(uA(δ)² + uB(δ)²)` como passo primário. Essa forma, embora matematicamente idêntica quando uA/uB estão separados em ambos os lados, **falha (produz NaN)** quando um dos lados tem só uc (métricas derivadas, ver decisão irmã).

Fallback permitido: se `uc_right` ou `uc_left` estiverem ausentes mas `uA/uB` existirem, reconstituir por `√(uA(δ)² + uB(δ)²)` como secundário.

## Motivação

Matematicamente, `uc² = uA² + uB²` por definição. Então:

```
(∂δ/∂r · uc_r)² = (∂δ/∂r)² · (uA_r² + uB_r²)
                = (∂δ/∂r · uA_r)² + (∂δ/∂r · uB_r)²
```

Somando esse termo com o análogo do lado esquerdo:

```
uc(δ)²  =  (∂δ/∂r · uc_r)² + (∂δ/∂l · uc_l)²
       =  uA(δ)² + uB(δ)²
```

As duas expressões são **idênticas**. A única diferença é qual é primária: se a partir de uc (decisão atual) ou a partir de uA/uB (caminho legado). A decisão escolhe a primeira por **robustez** a métricas que não têm uA/uB separados.

Caso-gatilho (2026-04-25): `η_th` só tem `uc_n_th_pct` no `final_table` — não tem `uA_n_th_pct` nem `uB_n_th_pct`, porque η_th é calculada via propagação instrumental sem σ entre janelas discriminado. Com o caminho legado, o `U_delta_pct` de η_th saía NaN em todas as comparações. Com a fórmula via uc direto, sai corretamente propagado.

Validação empírica: em todas as 4 métricas que têm uA/uB separados (consumo, CO, CO2, NOx, O2, THC), as duas fórmulas concordam a **0,0000 pct absoluto** em todos os pontos testados — confirmando equivalência matemática. Para η_th, a nova fórmula é a única que produz um número; a antiga produz NaN.

## Forma da entrada

No legado isso vive em `_build_compare_metric_delta_table` (`nanum_pipeline_29.py:~6945-6950`). Versão corrigida:

```python
m["uc_delta_pct"] = (
    (m["d_delta_d_right"].abs() * m["uc_right"]) ** 2
    + (m["d_delta_d_left"].abs() * m["uc_left"]) ** 2
) ** 0.5
# Fallback para casos em que uc está ausente mas uA/uB estão:
uc_fallback = (m["uA_delta_pct"] ** 2 + m["uB_delta_pct"] ** 2) ** 0.5
m["uc_delta_pct"] = m["uc_delta_pct"].where(m["uc_delta_pct"].notna(), uc_fallback)
m["U_delta_pct"] = K_COVERAGE * m["uc_delta_pct"]
```

A breakdown `uA(δ)` e `uB(δ)` continua sendo computada para fins de diagnóstico/exportação no xlsx — ela não é descartada.

## Consequências para o newgen

1. Qualquer estação que compute `delta_pct` entre duas agregações deve usar a forma direta como caminho primário. Isso vale para `run_compare_iteracoes` (Passo 2d+) e para qualquer comparação futura (ex.: BL vs ADTV por iteração, sweep delta entre setpoints).
2. A coluna `U_delta_pct` fica **não-nula** em todas as métricas presentes no final_table — isso é um invariante de teste: `report["U_delta_pct"].notna().all()` deve valer.
3. O port nativo da função (Passo 3c) precisa encodar também o fallback para blindar contra métricas futuras que venham só com uA/uB (ex.: importação de incertezas externas do usuário).

## Decisões irmãs

- `2026-04-25-uB-correlacionado-em-media-de-campanha.md` — lei de média. Combinada com esta, garante que uc(δ) é estatisticamente correto tanto na entrada (uc por lado bem agregado) quanto na saída (combinação via partials). As duas precisam viajar juntas.
- `2026-04-25-derivadas-expor-uA-uB-separados.md` — minimiza o uso do fallback atual ao fazer métricas derivadas exporem uA/uB nativamente.
