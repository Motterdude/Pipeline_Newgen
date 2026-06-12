# 2026-06-12 — co-uncertainty-full-scale

## O que mudou

### 1. instruments.toml — parametrização correta da incerteza (% of Full Scale)

`config/pipeline29_text/instruments.toml` — CO_pct, CO2_pct, O2_pct trocam `acc_pct` (% da leitura) por `acc_abs` (% of Full Scale):

| Key | Antes | Depois | Justificativa |
|---|---|---|---|
| CO_pct | `acc_pct=0.01, acc_abs=0` | `acc_pct=0, acc_abs=0.2` | 1% × 20% FS = 0.2 %vol |
| CO2_pct | `acc_pct=0.01, acc_abs=0` | `acc_pct=0, acc_abs=0.2` | 1% × 20% FS = 0.2 %vol |
| O2_pct | `acc_pct=0.01, acc_abs=0` | `acc_pct=0, acc_abs=0.25` | 1% × 25% FS = 0.25 %vol |

`resolution = 0.1` mantido — confirmado como resolução efetiva noise-limited do instrumento, não do display.

### 2. prepare.py — bug fix: `guess_uncertainty_col` não resolvia métricas "medido"

`src/pipeline_newgen_rev1/runtime/compare_iteracoes/prepare.py` — `guess_uncertainty_col()` falhava para qualquer coluna `*_mean_of_windows` (CO, CO2, O2, NOx, THC medidos):

**Causa raiz:** a função tentava `U_CO_mean_of_windows` (não existe) e o fallback via `mappings` dict retornava vazio. Resultado: `U_delta_pct = NaN` para todas métricas medidas → sem barras de erro no plot.

**Fix:** heurística adicional que:
1. Detecta sufixo `_mean_of_windows` no metric_col
2. Extrai o stem (`CO`, `NOX`, etc.)
3. Mapeia para o prefix correto (`CO_pct`, `NOx_ppm`, etc.)
4. Tenta `U_<prefix>` como candidato

Métricas corrigidas: CO medido, CO2 medido, O2 medido, NOx medido, THC medido.

### 3. compare.toml — co_g_kwh adicionado

`config/pipeline29_text/compare.toml` — 3 novas entradas para `co_g_kwh` (CO específico g/kWh) nos pares primários (media×media, subida×subida, descida×descida) com `show_uncertainty = "on"`.

### 4. Decisão formalizada

`handoff/decisions/2026-06-12-co-uncertainty-full-scale.md` — documenta evidência do manual CAI 600 Series (pg.22: Noise/Repeatability < 1% of Full Scale), cadeia de sinal, e confirmação de que resolution=0.1 é correta.

## Por quê

Investigação do manual do fabricante (CAI 600 Series NDIR Operators Manual Rev 116, pg.22) revelou que **todas as specs de performance** (Noise, Repeatability, Drift, Linearity) são em **% of Full Scale**, não % da leitura:

- NOISE: < 1% of Full Scale
- REPEATABILITY: < 1% of Full Scale
- ZERO & SPAN DRIFT: < 1% of Full Scale per 24h

O antigo `acc_pct = 0.01` no instruments.toml interpretava a repetibilidade como 1% da leitura. Para CO com leituras de 50 ppm e FS = 20% (200.000 ppm), isso subestimava a incerteza de acurácia em ~4000× (calculava 0.5 ppm em vez de 2000 ppm).

A `resolution = 0.1` (%vol) está **correta** — é a resolução efetiva do instrumento limitada pelo noise floor, não do display (que tem 5 dígitos significativos). Os steps de 0.000001% nos xlsx são ruído eletrotérmico digitalizado pelo NI DAQ, sem informação real.

## Arquivos

- `config/pipeline29_text/instruments.toml` (modificado)
- `config/pipeline29_text/compare.toml` (modificado)
- `src/pipeline_newgen_rev1/runtime/compare_iteracoes/prepare.py` (bug fix: `guess_uncertainty_col`)
- `handoff/decisions/2026-06-12-co-uncertainty-full-scale.md` (novo)

## Validação

- `python -m unittest discover -s tests -p "test_*.py"` → 549 testes, 10 erros pré-existentes em `test_bridge_*`. Nenhuma falha nova.
- Cálculo de impacto:
  - CO (50 ppm): uB passa de 289 ppm → 1190 ppm (agora correto — o instrumento não garante essa resolução)
  - CO2 (12%): uB passa de 751 ppm → 1190 ppm (agora constante, independente da leitura)
  - O2: similar (acc_abs = 0.25 para FS = 25%)
- No compare (delta_mode=diff): U_delta_CO ≈ 2×√(uc_BL² + uc_ADT²) — agora com uc correto do fabricante

## Bug fix adicional: guess_uncertainty_col

O compare não plotava barras de incerteza para **nenhuma** métrica "medido" (CO, CO2, O2, NOx, THC) porque `guess_uncertainty_col` não conseguia mapear `CO_mean_of_windows` → `U_CO_pct`. A heurística falhava porque:
1. `U_CO_mean_of_windows` não existe no DataFrame
2. O fallback via `mappings` dict não encontrava match (o dict vinha vazio do bundle)

Fix: adicionada heurística que strip `_mean_of_windows` do nome da coluna e tenta prefixos conhecidos (`CO → CO_pct`, `NOX → NOx_ppm`, etc.). Agora todas as 5 métricas medidas resolvem corretamente.

## Pendências

- **Re-rodar o pipeline** para regenerar `lv_kpis_clean.xlsx` com a nova incerteza E o fix do guess.
- Confirmar o range real usado no experimento do Vinícius (0-20% ou auto-range menor). Se era 0-2%, o acc_abs deveria ser 0.02 (10× menor). Sem essa informação, 0.2 (FS=20%) é conservador.
- NOx/NO/THC (400-HCLD e 300M-HFID): Moreira lista 0.5% de repetibilidade mas não especifica se é "of reading" ou "of FS". Mantidos como `acc_pct` por ora — a diferença é menor para esses instrumentos com leituras mais altas.
