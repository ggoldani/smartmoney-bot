# Sprint 1 - MVP Free Bot

## ✅ Implementação Completa

Sprint 1 foi **100% implementado** com todas as features planejadas:

### Features Implementadas

1. **✅ Config System (YAML)**
   - Arquivo `configs/free.yaml` com todas configurações
   - Loader de YAML com validação e env var substitution
   - Helper functions para acesso fácil (`get_rsi_config()`, etc.)

2. **✅ Binance REST API Backfill**
   - Cliente REST com retry automático (exponential backoff)
   - Busca 200 candles por timeframe na inicialização
   - Suporte a múltiplos símbolos e timeframes

3. **✅ RSI Indicator**
   - Cálculo manual usando método de Wilder (padrão RSI)
   - Análise de condições críticas (overbought/oversold)
   - Detecção multi-timeframe

4. **✅ Alert Rules Engine**
   - Loop assíncrono monitorando candles fechados
   - Dispara alertas RSI baseado em regras
   - Suporte a consolidação multi-TF
   - Integração com throttler

5. **✅ Message Templates (BR)**
   - Formatação brasileira (timezone, números, datas)
   - Templates para: RSI overbought/oversold, multi-TF, startup, shutdown, errors
   - Emojis configurados por tipo de alerta

6. **✅ Throttling & Circuit Breaker**
   - Max 20 alertas/hora (configurável)
   - Circuit breaker: consolida se >5 alertas/minuto
   - Tracking de histórico por condição

7. **✅ Admin Channel Support**
   - Erros críticos enviados para canal admin
   - Warnings para reconexões, rate limits, etc.
   - Templates específicos para admin

8. **✅ Graceful Shutdown**
   - Handler de SIGTERM/SIGINT
   - Mensagem de shutdown para grupo
   - Cancelamento limpo de tasks assíncronas

9. **✅ Docker Compose**
   - Volume para configs (read-only)
   - Volume para logs (rotação automática)
   - Volume para database
   - Resource limits (256MB RAM, 0.5 CPU)
   - Non-root user (UID 1000)

10. **✅ Main Orchestrator**
    - Startup sequence (DB init → backfill → startup message)
    - Parallel execution (WebSocket + Alert Engine)
    - Shutdown sequence
    - Error handling e reporting para admin

---

## 🧪 Como Testar

### 1. Setup Inicial

```bash
# Entre no diretório do bot
cd smartmoney-bot

# Copie o .env.example
cp .env.example .env

# Edite o .env com suas credenciais
nano .env
```

**Configuração mínima do `.env`:**
```bash
BOT_TOKEN=seu_token_aqui
CHANNEL_CHAT_ID=-1001234567890  # ID do grupo de teste
ADMIN_CHANNEL_ID=-10098765432  # ID do canal admin
LOG_LEVEL=INFO
CONFIG_FILE=./configs/free.yaml
```

### 2. Testes Locais (sem Docker)

```bash
# Criar virtualenv
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate   # Windows

# Instalar dependências
pip install -r requirements.txt

# Testar config loader
python -c "from src.config import get_config; print(get_config().raw)"

# Testar backfill
python src/main.py --backfill

# Testar ping (envia mensagem teste)
python src/main.py --ping

# Rodar bot completo (dry-run primeiro!)
python src/main.py --dry-run
```

### 3. Teste com Docker

```bash
# Build da imagem
docker compose build

# Subir bot
docker compose up -d

# Ver logs
docker compose logs -f bot-free

# Parar bot
docker compose down
```

### 4. Validação de Alertas RSI

Para testar se os alertas RSI funcionam:

1. **Aguarde candles fecharem** - Bot checa a cada 5 segundos
2. **Verifique logs** para ver cálculos RSI:
   ```bash
   docker compose logs -f | grep "RSI analysis"
   ```
3. **Simule condição crítica** (opcional):
   - Use mercado real em momento de RSI extremo
   - Ou injete dados manualmente no SQLite (avançado)

### 5. Teste de Graceful Shutdown

```bash
# Enviar SIGTERM
docker compose stop bot-free

# Verificar que mensagem de shutdown foi enviada no Telegram
```

---

## 📋 Checklist de Verificação

Antes de fazer deploy em produção, verifique:

- [ ] `.env` configurado com tokens corretos
- [ ] Grupos de Telegram criados (free + admin)
- [ ] Bot adicionado aos grupos com permissão de enviar mensagens
- [ ] `configs/free.yaml` revisado e ajustado se necessário
- [ ] Teste local com `--dry-run` passou sem erros
- [ ] Teste de backfill completou com sucesso
- [ ] Teste de ping enviou mensagem para grupo correto
- [ ] Bot rodando em Docker sem crashes
- [ ] Logs não mostram erros críticos
- [ ] Mensagem de startup apareceu no grupo
- [ ] Alertas RSI sendo enviados corretamente (aguardar condições reais)

---

## 🐛 Troubleshooting

### Bot não inicia
- Verifique logs: `docker compose logs bot-free`
- Confirme que `configs/free.yaml` existe
- Verifique que BOT_TOKEN está correto

### Mensagens não chegam no Telegram
- Confirme que bot foi adicionado ao grupo
- Verifique CHANNEL_CHAT_ID (deve começar com `-100`)
- Teste com `python src/main.py --ping`

### RSI não calcula
- Verifique que backfill completou (pelo menos 15 candles por TF)
- Veja logs: "Insufficient data for RSI"
- Aguarde mais candles fecharem naturalmente

### Backfill falha
- Pode ser rate limit da Binance (raro com 200 candles)
- Verifique conexão internet
- Retry automático deve funcionar após 1s, 2s, 4s

---

## 📈 Próximos Passos (Sprint 2)

Sprint 1 está **completo e pronto para testes**!

Próximas features (Sprint 2):
1. Breakout alerts (1d, 1w)
2. Database cleanup cronjob (90 dias)
3. Health monitoring (latência, uptime)

---

## 🚀 Deploy em Produção

Quando estiver pronto:

```bash
# Na VPS
git clone <repo>
cd smartmoney-bot
cp .env.example .env
nano .env  # Configurar produção

# Subir bot
docker compose up -d

# Monitorar
docker compose logs -f
```

**Lembre-se:** Primeira vez pode levar ~30s para backfill completar!
