# OPERATIONS GUIDE

Guia operacional completo para gerenciar o SmartMoney Bot em desenvolvimento e produção.

---

## COMANDOS ESSENCIAIS

### Setup Inicial (Primeira Vez)

```bash
# Clone e entre no diretório
git clone <repo-url>
cd smartmoney-bot

# Crie ambiente virtual
python -m venv .venv
source .venv/bin/activate

# Instale dependências
pip install -r requirements.txt

# Configure variáveis de ambiente
cp .env.example .env
nano .env  # Edite: BOT_TOKEN, CHANNEL_CHAT_ID, ADMIN_CHANNEL_ID
```

**Variáveis obrigatórias no .env:**
```env
BOT_TOKEN=<seu_token_do_botfather>
CHANNEL_CHAT_ID=<id_do_canal_público>
ADMIN_CHANNEL_ID=<id_do_canal_admin>
CONFIG_FILE=./configs/free.yaml
DB_URL=sqlite:///./data.db
LOG_LEVEL=INFO
```

---

## MODOS DE EXECUÇÃO

### 1. Modo Dry-Run (Teste Sem Telegram)

```bash
source .venv/bin/activate
PYTHONPATH=. python src/main.py --dry-run
```

**Comportamento:**
- ✅ Conecta à Binance (WebSocket + REST)
- ✅ Calcula indicadores (RSI, breakouts)
- ✅ Executa regras de alerta
- ❌ NÃO envia mensagens ao Telegram
- ✅ Registra tudo em logs

**Uso:** Validação de lógica, debug de indicadores, testes de backfill.

---

### 2. Modo LIVE (Produção)

```bash
source .venv/bin/activate
PYTHONPATH=. python src/main.py
```

**Comportamento:**
- ✅ Conecta à Binance
- ✅ Calcula indicadores
- ✅ Executa regras
- ✅ ENVIA alertas ao Telegram

**Variações:**

```bash
# Com logs em arquivo
PYTHONPATH=. python src/main.py 2>&1 | tee logs/bot.log

# Em background (continua após fechar terminal)
nohup PYTHONPATH=. python src/main.py > logs/bot.log 2>&1 &

# Salvar PID para facilitar parar depois
nohup PYTHONPATH=. python src/main.py > logs/bot.log 2>&1 & echo $! > bot.pid
```

---

## MONITORAMENTO

### Logs em Tempo Real

```bash
# Ver últimas 50 linhas
tail -50 logs/bot.log

# Seguir logs (Ctrl+C para sair)
tail -f logs/bot.log

# Filtrar por nível
grep "ERROR" logs/bot.log
grep "WARNING" logs/bot.log
grep "INFO" logs/bot.log

# Ver alertas disparados
grep "Alert sent" logs/bot.log
```

### Verificar Status do Bot

```bash
# Verificar se está rodando
ps aux | grep "python src/main.py"

# Ver uso de recursos
top -p $(pgrep -f "python src/main.py")

# Verificar conexões de rede
netstat -anp | grep python
```

### Database

```bash
# Entrar no SQLite
sqlite3 data.db

# Queries úteis (dentro do sqlite3):
SELECT COUNT(*) FROM candles;
SELECT symbol, interval, COUNT(*) FROM candles GROUP BY symbol, interval;
SELECT * FROM candles ORDER BY close_time DESC LIMIT 10;
.exit
```

---

## PARAR O BOT

### Modo Foreground (Ctrl+C)

Se o bot está rodando no terminal visível:
```bash
Ctrl+C  # Ativa graceful shutdown (5 segundos)
```

### Modo Background

```bash
# Se salvou o PID:
kill -SIGTERM $(cat bot.pid)

# Se não salvou, encontre o PID:
ps aux | grep "python src/main.py"
kill -SIGTERM <PID>

# Forçar parada (último recurso):
kill -9 <PID>
```

**SEMPRE prefira `SIGTERM` (graceful shutdown) em vez de `kill -9`.**

---

## VERIFICAR CONECTIVIDADE

### Telegram API

```bash
# Testar bot token
curl https://api.telegram.org/bot<BOT_TOKEN>/getMe

# Testar envio de mensagem
curl -X POST "https://api.telegram.org/bot<BOT_TOKEN>/sendMessage" \
     -d "chat_id=<CHANNEL_CHAT_ID>&text=Teste"
```

### Binance API

```bash
# Ping (deve retornar {})
curl https://api.binance.com/api/v3/ping

# Server time
curl https://api.binance.com/api/v3/time

# Klines (BTCUSDT 1h, últimas 5 velas)
curl "https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1h&limit=5"
```

---

## DOCKER (PRODUÇÃO RECOMENDADA)

### Build e Start

```bash
# Build e start em background
docker-compose up -d

# Ver logs
docker-compose logs -f smartmoney-free

# Restart
docker-compose restart smartmoney-free

# Stop
docker-compose stop

# Stop e remove containers
docker-compose down
```

### Debugging Docker

```bash
# Entrar no container
docker-compose exec smartmoney-free /bin/sh

# Ver recursos
docker stats smartmoney-free

# Inspecionar
docker inspect smartmoney-free
```

---

## DEPLOYMENT VPS

### 1. Clone no VPS

```bash
ssh user@vps-ip
git clone <repo-url>
cd smartmoney-bot
```

### 2. Configure .env (CRÍTICO!)

```bash
cp .env.example .env
nano .env

# NUNCA commitar .env com secrets reais!
```

### 3. Opção A: Docker (Recomendado)

```bash
docker-compose up -d
docker-compose logs -f smartmoney-free
```

### 4. Opção B: Python Direto

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
nohup PYTHONPATH=. python src/main.py > logs/bot.log 2>&1 & echo $! > bot.pid
```

### 5. Manter Bot Rodando (systemd)

Crie `/etc/systemd/system/smartmoney-bot.service`:

```ini
[Unit]
Description=SmartMoney Free Bot
After=network.target

[Service]
Type=simple
User=<seu-usuario>
WorkingDirectory=/home/<seu-usuario>/smartmoney-bot
Environment="PYTHONPATH=."
ExecStart=/home/<seu-usuario>/smartmoney-bot/.venv/bin/python src/main.py
Restart=on-failure
RestartSec=10s

[Install]
WantedBy=multi-user.target
```

**Ativar:**
```bash
sudo systemctl daemon-reload
sudo systemctl enable smartmoney-bot
sudo systemctl start smartmoney-bot
sudo systemctl status smartmoney-bot

# Ver logs
sudo journalctl -u smartmoney-bot -f
```

---

## TROUBLESHOOTING

### Bot não conecta ao Telegram

```bash
# Verifique token
echo $BOT_TOKEN

# Teste API
curl https://api.telegram.org/bot$BOT_TOKEN/getMe

# Verifique firewall
ping api.telegram.org
```

### Bot não recebe dados da Binance

```bash
# Teste conectividade
curl https://api.binance.com/api/v3/ping

# Verifique WebSocket (netcat)
nc -zv stream.binance.com 9443

# Ver logs de WebSocket
grep "WebSocket" logs/bot.log
```

### Database está vazio

```bash
# Verificar se backfill rodou
grep "Backfill" logs/bot.log

# Forçar backfill (apague o DB):
rm data.db
PYTHONPATH=. python src/main.py  # Recria e faz backfill
```

### Alertas não aparecem

```bash
# Verificar throttling
grep "Throttled" logs/bot.log
grep "Circuit breaker" logs/bot.log

# Verificar RSI atual (script rápido):
python -c "
from src.storage.db import get_db
from src.indicators.rsi import get_latest_rsi
print('RSI 1h:', get_latest_rsi('BTCUSDT', '1h'))
print('RSI 4h:', get_latest_rsi('BTCUSDT', '4h'))
print('RSI 1d:', get_latest_rsi('BTCUSDT', '1d'))
"
```

### Erro de UTF-8 / Encoding

```bash
# Verificar locale
locale

# Configurar UTF-8 (Ubuntu/Debian)
export LC_ALL=en_US.UTF-8
export LANG=en_US.UTF-8
```

---

## BACKUP E RESTORE

### Backup do Database

```bash
# Copiar database
cp data.db backup_$(date +%Y%m%d_%H%M%S).db

# Ou dump SQL
sqlite3 data.db .dump > backup.sql
```

### Restore

```bash
# De cópia
cp backup_20251111_160000.db data.db

# De dump SQL
sqlite3 data.db < backup.sql
```

---

## ATUALIZAÇÕES

### Atualizar código no VPS

```bash
cd smartmoney-bot

# Parar bot
docker-compose down
# ou: kill -SIGTERM $(cat bot.pid)

# Pull updates
git pull origin main

# Rebuild (se usar Docker)
docker-compose up -d --build

# Ou reinstalar deps (se Python direto)
source .venv/bin/activate
pip install -r requirements.txt --upgrade
nohup PYTHONPATH=. python src/main.py > logs/bot.log 2>&1 &
```

---

## CHECKLIST PRÉ-PRODUÇÃO

- [ ] `.env` configurado com secrets reais
- [ ] `.env` NÃO commitado no git
- [ ] Database criado e backfill completado
- [ ] Startup message apareceu no Telegram
- [ ] WebSocket conectado (verificar logs)
- [ ] Dry-run testado localmente
- [ ] LIVE testado localmente
- [ ] Recursos VPS verificados (CPU, RAM, disco)
- [ ] Firewall permite conexões Binance + Telegram
- [ ] Backup strategy definida

---

## COMANDOS RÁPIDOS (CHEAT SHEET)

```bash
# Ativar venv
source .venv/bin/activate

# Rodar em dry-run
PYTHONPATH=. python src/main.py --dry-run

# Rodar LIVE
PYTHONPATH=. python src/main.py

# Rodar LIVE em background
nohup PYTHONPATH=. python src/main.py > logs/bot.log 2>&1 & echo $! > bot.pid

# Ver logs
tail -f logs/bot.log

# Parar bot
kill -SIGTERM $(cat bot.pid)

# Docker start
docker-compose up -d

# Docker logs
docker-compose logs -f smartmoney-free

# Docker stop
docker-compose down

# Ver database
sqlite3 data.db "SELECT COUNT(*) FROM candles;"
```

---

**Última atualização:** 2025-11-11
**Versão do bot:** 1.0.0 (Sprint 1 completo)
