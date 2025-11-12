#!/bin/bash
set -euo pipefail

################################################################################
# SmartMoney Bot - Production Deployment Script
# Ubuntu 24.04 LTS
#
# Uso: sudo bash deploy.sh
################################################################################

readonly SCRIPT_VERSION="2.0.0"
readonly BOT_USER="smartmoney"
readonly BOT_DIR="/opt/smartmoney-bot"
readonly LOG_FILE="/var/log/smartmoney-deploy.log"

# Colors for output
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly NC='\033[0m' # No Color

################################################################################
# Logging Functions
################################################################################

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1" | tee -a "$LOG_FILE"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1" | tee -a "$LOG_FILE"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1" | tee -a "$LOG_FILE"
}

################################################################################
# Pre-flight Checks
################################################################################

check_root() {
    if [[ $EUID -ne 0 ]]; then
        log_error "Este script deve ser executado como root (sudo)"
        exit 1
    fi
}

check_ubuntu() {
    if [[ ! -f /etc/os-release ]]; then
        log_error "Sistema operacional não identificado"
        exit 1
    fi

    source /etc/os-release
    if [[ "$ID" != "ubuntu" ]] || [[ "$VERSION_ID" != "24.04" ]]; then
        log_warn "Este script foi testado apenas no Ubuntu 24.04 LTS"
        read -p "Continuar mesmo assim? (y/N) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
}

################################################################################
# System Update & Security
################################################################################

update_system() {
    log_info "Atualizando sistema..."

    export DEBIAN_FRONTEND=noninteractive

    apt-get update -qq
    apt-get upgrade -y -qq
    apt-get autoremove -y -qq
    apt-get autoclean -y -qq

    log_info "Sistema atualizado"
}

install_base_packages() {
    log_info "Instalando pacotes base..."

    apt-get install -y -qq \
        apt-transport-https \
        ca-certificates \
        curl \
        gnupg \
        lsb-release \
        git \
        ufw \
        fail2ban \
        htop \
        vim \
        net-tools \
        wget

    log_info "Pacotes base instalados"
}

################################################################################
# Firewall Configuration
################################################################################

configure_firewall() {
    log_info "Configurando firewall (UFW)..."

    # Reset UFW
    ufw --force reset

    # Default policies
    ufw default deny incoming
    ufw default allow outgoing

    # Allow SSH (CRÍTICO - não bloquear)
    ufw allow 22/tcp comment 'SSH'

    # Allow healthcheck endpoint (opcional, apenas se quiser expor)
    # ufw allow 8080/tcp comment 'Healthcheck'

    # Enable UFW
    ufw --force enable

    log_info "Firewall configurado"
}

configure_fail2ban() {
    log_info "Configurando Fail2Ban..."

    # Jail local config
    cat > /etc/fail2ban/jail.local <<EOF
[DEFAULT]
bantime = 3600
findtime = 600
maxretry = 5

[sshd]
enabled = true
port = 22
logpath = /var/log/auth.log
EOF

    systemctl enable fail2ban
    systemctl restart fail2ban

    log_info "Fail2Ban configurado"
}

################################################################################
# Docker Installation
################################################################################

install_docker() {
    log_info "Instalando Docker..."

    # Remove versões antigas
    apt-get remove -y -qq docker docker-engine docker.io containerd runc 2>/dev/null || true

    # Add Docker GPG key
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    chmod a+r /etc/apt/keyrings/docker.gpg

    # Add Docker repository
    echo \
      "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
      $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null

    # Install Docker
    apt-get update -qq
    apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

    # Start Docker
    systemctl enable docker
    systemctl start docker

    log_info "Docker instalado: $(docker --version)"
}

################################################################################
# Python Installation (alternativa ao Docker)
################################################################################

install_python() {
    log_info "Instalando Python 3.13..."

    # Adicionar PPA deadsnakes (para Python 3.13)
    add-apt-repository -y ppa:deadsnakes/ppa
    apt-get update -qq

    # Instalar Python 3.13 + deps
    apt-get install -y -qq \
        python3.13 \
        python3.13-venv \
        python3.13-dev \
        python3-pip \
        build-essential

    # Verificar versão
    python3.13 --version

    log_info "Python 3.13 instalado"
}

################################################################################
# User & Directory Setup
################################################################################

create_bot_user() {
    log_info "Criando usuário do bot..."

    # Criar usuário sem login shell (segurança)
    if ! id "$BOT_USER" &>/dev/null; then
        useradd -r -s /bin/false -d "$BOT_DIR" -c "SmartMoney Bot Service" "$BOT_USER"
        log_info "Usuário $BOT_USER criado"
    else
        log_warn "Usuário $BOT_USER já existe"
    fi

    # Add to docker group
    usermod -aG docker "$BOT_USER" || true
}

create_directories() {
    log_info "Criando diretórios..."

    mkdir -p "$BOT_DIR"
    mkdir -p "$BOT_DIR/data"
    mkdir -p "$BOT_DIR/logs"
    mkdir -p "$BOT_DIR/configs"

    # Set permissions
    chown -R "$BOT_USER:$BOT_USER" "$BOT_DIR"
    chmod 750 "$BOT_DIR"

    log_info "Diretórios criados em $BOT_DIR"
}

################################################################################
# Bot Installation
################################################################################

clone_repository() {
    log_info "Clonando repositório..."

    # Se já existe, fazer pull
    if [[ -d "$BOT_DIR/.git" ]]; then
        log_warn "Repositório já existe, fazendo pull..."
        cd "$BOT_DIR"
        sudo -u "$BOT_USER" git pull
    else
        # Clone como bot user
        sudo -u "$BOT_USER" git clone https://github.com/seu-usuario/smartmoney-bot.git "$BOT_DIR"
    fi

    cd "$BOT_DIR"
    log_info "Repositório clonado/atualizado"
}

setup_environment() {
    log_info "Configurando ambiente..."

    # Criar .env se não existir
    if [[ ! -f "$BOT_DIR/.env" ]]; then
        log_warn "Arquivo .env não encontrado!"
        log_info "Criando .env a partir do template..."

        cp "$BOT_DIR/.env.example" "$BOT_DIR/.env"

        log_warn "IMPORTANTE: Edite $BOT_DIR/.env com suas credenciais:"
        log_warn "  - BOT_TOKEN (obtenha via @BotFather)"
        log_warn "  - CHANNEL_CHAT_ID (ID do canal Telegram)"
        log_warn "  - ADMIN_CHANNEL_ID (ID do canal admin)"

        # Proteger .env
        chmod 600 "$BOT_DIR/.env"
        chown "$BOT_USER:$BOT_USER" "$BOT_DIR/.env"

        # Pause para configuração
        read -p "Pressione ENTER após configurar o .env..."
    else
        log_info "Arquivo .env já existe"
    fi
}

################################################################################
# Deployment Method Selection
################################################################################

deploy_with_docker() {
    log_info "Fazendo deploy com Docker..."

    cd "$BOT_DIR"

    # Build da imagem
    docker compose build

    # Start do container
    docker compose up -d

    log_info "Bot iniciado via Docker"
    log_info "Logs: docker compose logs -f"
}

deploy_with_python() {
    log_info "Fazendo deploy com Python nativo..."

    cd "$BOT_DIR"

    # Criar venv como bot user
    sudo -u "$BOT_USER" python3.13 -m venv .venv

    # Instalar dependências
    sudo -u "$BOT_USER" .venv/bin/pip install --upgrade pip
    sudo -u "$BOT_USER" .venv/bin/pip install -r requirements.txt

    log_info "Dependências instaladas"
}

################################################################################
# Systemd Service (para Python nativo)
################################################################################

create_systemd_service() {
    log_info "Criando serviço systemd..."

    cat > /etc/systemd/system/smartmoney-bot.service <<EOF
[Unit]
Description=SmartMoney Brasil - Crypto Trading Alerts Bot
After=network.target

[Service]
Type=simple
User=$BOT_USER
Group=$BOT_USER
WorkingDirectory=$BOT_DIR
Environment="PYTHONPATH=$BOT_DIR"
ExecStart=$BOT_DIR/.venv/bin/python $BOT_DIR/src/main.py
Restart=on-failure
RestartSec=10
StandardOutput=append:$BOT_DIR/logs/bot.log
StandardError=append:$BOT_DIR/logs/bot-error.log

# Security hardening
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=$BOT_DIR/data $BOT_DIR/logs

[Install]
WantedBy=multi-user.target
EOF

    # Reload systemd
    systemctl daemon-reload
    systemctl enable smartmoney-bot.service
    systemctl start smartmoney-bot.service

    log_info "Serviço systemd criado e iniciado"
}

################################################################################
# Log Rotation
################################################################################

configure_logrotate() {
    log_info "Configurando rotação de logs..."

    cat > /etc/logrotate.d/smartmoney-bot <<EOF
$BOT_DIR/logs/*.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
    create 0640 $BOT_USER $BOT_USER
}
EOF

    log_info "Log rotation configurado"
}

################################################################################
# Health Monitoring
################################################################################

create_healthcheck_script() {
    log_info "Criando script de healthcheck..."

    cat > /usr/local/bin/smartmoney-health <<'EOF'
#!/bin/bash
HEALTHCHECK_URL="http://localhost:8080/health"
TIMEOUT=5

if curl -sf --max-time "$TIMEOUT" "$HEALTHCHECK_URL" > /dev/null 2>&1; then
    echo "✅ Bot is healthy"
    exit 0
else
    echo "❌ Bot is unhealthy"
    exit 1
fi
EOF

    chmod +x /usr/local/bin/smartmoney-health

    log_info "Healthcheck script criado: /usr/local/bin/smartmoney-health"
}

setup_cron_monitoring() {
    log_info "Configurando monitoring via cron..."

    # Adicionar cron para verificar health a cada 5 minutos
    (crontab -u "$BOT_USER" -l 2>/dev/null; echo "*/5 * * * * /usr/local/bin/smartmoney-health || systemctl restart smartmoney-bot") | crontab -u "$BOT_USER" -

    log_info "Cron monitoring configurado"
}

################################################################################
# Post-Install Summary
################################################################################

print_summary() {
    echo ""
    echo "════════════════════════════════════════════════════════════════"
    echo "🚀 SmartMoney Bot - Deploy Completo!"
    echo "════════════════════════════════════════════════════════════════"
    echo ""
    echo "📂 Diretório: $BOT_DIR"
    echo "👤 Usuário: $BOT_USER"
    echo ""
    echo "🔧 Comandos úteis:"
    echo ""

    if [[ "$DEPLOY_METHOD" == "docker" ]]; then
        echo "  # Ver logs:"
        echo "  docker compose -f $BOT_DIR/docker-compose.yml logs -f"
        echo ""
        echo "  # Restart:"
        echo "  docker compose -f $BOT_DIR/docker-compose.yml restart"
        echo ""
        echo "  # Status:"
        echo "  docker compose -f $BOT_DIR/docker-compose.yml ps"
    else
        echo "  # Ver logs:"
        echo "  journalctl -u smartmoney-bot -f"
        echo ""
        echo "  # Restart:"
        echo "  systemctl restart smartmoney-bot"
        echo ""
        echo "  # Status:"
        echo "  systemctl status smartmoney-bot"
    fi

    echo ""
    echo "  # Healthcheck:"
    echo "  /usr/local/bin/smartmoney-health"
    echo ""
    echo "  # Firewall status:"
    echo "  ufw status"
    echo ""
    echo "════════════════════════════════════════════════════════════════"
    echo ""
    echo "⚠️  PRÓXIMOS PASSOS:"
    echo ""
    echo "1. Verifique se o .env está configurado:"
    echo "   vim $BOT_DIR/.env"
    echo ""
    echo "2. Verifique se o bot está rodando:"
    if [[ "$DEPLOY_METHOD" == "docker" ]]; then
        echo "   docker compose -f $BOT_DIR/docker-compose.yml ps"
    else
        echo "   systemctl status smartmoney-bot"
    fi
    echo ""
    echo "3. Monitore os logs:"
    if [[ "$DEPLOY_METHOD" == "docker" ]]; then
        echo "   docker compose -f $BOT_DIR/docker-compose.yml logs -f"
    else
        echo "   tail -f $BOT_DIR/logs/bot.log"
    fi
    echo ""
    echo "════════════════════════════════════════════════════════════════"
}

################################################################################
# Main Execution
################################################################################

main() {
    log_info "SmartMoney Bot Deployment v$SCRIPT_VERSION"
    log_info "Ubuntu 24.04 LTS"
    echo ""

    # Pre-flight checks
    check_root
    check_ubuntu

    # Ask deployment method
    echo "Escolha o método de deployment:"
    echo "1) Docker (recomendado - isolado, fácil de gerenciar)"
    echo "2) Python nativo (systemd - melhor performance)"
    read -p "Escolha (1/2): " -n 1 -r
    echo ""

    if [[ $REPLY == "1" ]]; then
        DEPLOY_METHOD="docker"
    else
        DEPLOY_METHOD="python"
    fi

    # System setup
    update_system
    install_base_packages
    configure_firewall
    configure_fail2ban

    # Install deployment method dependencies
    if [[ "$DEPLOY_METHOD" == "docker" ]]; then
        install_docker
    else
        install_python
    fi

    # Bot setup
    create_bot_user
    create_directories

    # IMPORTANTE: Clone manual (ou ajustar URL)
    log_warn "⚠️  ATENÇÃO: Clone o repositório manualmente:"
    log_warn "   git clone <seu-repo-url> $BOT_DIR"
    read -p "Pressione ENTER após clonar o repositório..."

    setup_environment

    # Deploy
    if [[ "$DEPLOY_METHOD" == "docker" ]]; then
        deploy_with_docker
    else
        deploy_with_python
        create_systemd_service
    fi

    # Monitoring
    configure_logrotate
    create_healthcheck_script

    if [[ "$DEPLOY_METHOD" == "python" ]]; then
        setup_cron_monitoring
    fi

    # Summary
    print_summary

    log_info "Deploy completo! ✅"
}

# Run main
main "$@"
