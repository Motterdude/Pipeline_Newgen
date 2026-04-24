# Token Pacer Proxy — Ideia para implementar depois

## Problema
- Databricks AI Gateway não retorna headers de rate-limit
- Limite é por "output tokens per minute" no nível workspace/user (AWS Bedrock por baixo)
- Não há rate limits configurados no Databricks (confirmado na UI)
- Sem headers, não dá pra saber o headroom proativamente — só reativo via 429

## Descobertas empíricas (2026-04-24)
- Path direto (`adb-*.azuredatabricks.net/serving-endpoints/...`) throttleia rápido
- Path AI Gateway (`*.ai-gateway.azuredatabricks.net/anthropic/...`) tem pool separado, mais tolerante
- Claude Code usa o AI Gateway path + header `x-databricks-use-coding-agent-mode: true`
- 16K+ output tokens em 5 min sem throttle pelo AI Gateway
- Sem rate-limit headers em nenhum dos paths

## Solução proposta: proxy local
- Python puro, zero dependências externas, zero tokens de AI consumidos
- Roda num terminal próprio, escuta em `localhost:8741`
- Claude Code aponta `ANTHROPIC_BASE_URL=http://localhost:8741/anthropic`
- Proxy lê `usage` de cada response e rastreia tokens numa janela rolante de 60s
- Quando se aproxima do limite: adiciona delay antes de encaminhar o request
- Expõe dashboard ASCII em `/status` e JSON em `/status/json`

## Controles de throughput
| Alavanca | Como | Risco |
|---|---|---|
| Delay de requests | Segura o request N segundos antes de encaminhar | Seguro |
| Fila de concorrência | Serializa se múltiplos terminais disparam ao mesmo tempo | Seguro |
| Cap em `max_tokens` | Reescreve o body do request para limitar output | Médio |
| Injetar `reasoning_effort` | Adiciona `"reasoning_effort": "low"` no request | Médio |
| Bloqueio total | Retorna 429 local se orçamento esgotou | Claude Code faz retry |

## Configuração via env vars
- `PACER_PORT` (default: 8741)
- `PACER_SOFT_LIMIT` (default: 8000 output tokens)
- `PACER_HARD_LIMIT` (default: 12000 output tokens)
- `PACER_WINDOW` (default: 60s)
- `PACER_UPSTREAM_HOST`
- `PACER_DB_PROFILE` (default: SC61730)

## Auth
- Proxy obtém token via `databricks auth token --profile SC61730`
- Cache de 5 min, refresh automático
