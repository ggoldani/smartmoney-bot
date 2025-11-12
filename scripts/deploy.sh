#!/bin/bash
set -euo pipefail

################################################################################
# SmartMoney Bot - Production Deployment Script
# Debian-based Distros (Ubuntu, Debian, etc)
#
# Uso: sudo bash deploy.sh
#
# O script irá:
# 1. Detectar distro Debian-based (Ubuntu, Debian, etc)
# 2. Instalar bot no diretório do USUÁRIO ATUAL (~/<user>/smartmoney-bot)
# 3. Configurar permissões para o usuário (não precisa sudo para git/editar)
# 4. Instalar dependências do sistema (Docker/Python/firewall) como root
# 5. Escolher deploy: Docker OU Python nativo com systemd
################################################################################

readonly SCRIPT_VERSION="2.2.0"
# Pega o usuário real (quem chamou sudo)
readonly BOT_USER="${SUDO_USER:-$USER}"
readonly BOT_DIR="/home/$BOT_USER/smartmoney-bot"
readonly LOG_FILE="/tmp/smartmoney-deploy.log"

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

check_debian_based() {
    if [[ ! -f /etc/os-release ]]; then
        log_error "Sistema operacional não identificado"
        exit 1
    fi

    source /etc/os-release

    # Definir valores padrão para variáveis que podem não estar definidas
    ID="${ID:-unknown}"
    ID_LIKE="${ID_LIKE:-}"
    VERSION_ID="${VERSION_ID:-unknown}"

    # Verifica se é Debian-based (Ubuntu, Debian, etc)
    if [[ "$ID_LIKE" != *"debian"* ]] && [[ "$ID" != "debian" ]] && [[ "$ID" != "ubuntu" ]]; then
        log_error "Este script requer uma distro Debian-based (Ubuntu, Debian, etc)"
        log_error "Distro detectada: $ID"
        exit 1
    fi

    log_info "Distro detectada: $ID (baseado em Debian)"
    log_info "Versão: $VERSION_ID"
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

    # Detectar caminho correto do log (Debian-based usa /var/log/auth.log)
    if [[ ! -f /var/log/auth.log ]]; then
        log_warn "Log file /var/log/auth.log não encontrado, Fail2Ban pode não funcionar corretamente"
    fi

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
backend = systemd
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

    # Add Docker GPG key (genérico para Debian-based)
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/$(source /etc/os-release && echo "$ID")/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    chmod a+r /etc/apt/keyrings/docker.gpg

    # Detectar distro ID para repositório correto
    source /etc/os-release

    # Definir valores padrão para variáveis que podem não estar definidas
    ID="${ID:-unknown}"
    VERSION_CODENAME="${VERSION_CODENAME:-}"

    DOCKER_DISTRO="$ID"
    if [[ "$ID" == "ubuntu" ]]; then
        DOCKER_DISTRO="ubuntu"
        CODENAME=$(lsb_release -cs 2>/dev/null || echo "jammy")
    elif [[ "$ID" == "debian" ]]; then
        DOCKER_DISTRO="debian"
        CODENAME="${VERSION_CODENAME:-bookworm}"  # Fallback if empty
    else
        DOCKER_DISTRO="$ID"
        CODENAME="${VERSION_CODENAME:-jammy}"  # Fallback for other distros
    fi

    # Add Docker repository
    echo \
      "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/$DOCKER_DISTRO \
      $CODENAME stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null

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
    log_info "Instalando Python 3.11+..."

    # Tentar usar python3 padrão do apt (3.11+ em distros modernas)
    apt-get install -y -qq \
        python3 \
        python3-venv \
        python3-dev \
        python3-pip \
        build-essential

    # Verificar versão e compatibilidade
    PYTHON_VERSION=$(python3 --version | awk '{print $2}')
    PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
    PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)

    log_info "Python instalado: $PYTHON_VERSION"

    # Verificar se é 3.11+
    if [[ $PYTHON_MAJOR -lt 3 ]] || [[ $PYTHON_MAJOR -eq 3 && $PYTHON_MINOR -lt 11 ]]; then
        log_error "Python 3.11+ é requerido. Versão encontrada: $PYTHON_VERSION"
        log_warn "Tente: apt-get install -y deadsnakes-ppa (se Ubuntu) e depois apt-get install python3.11"
        exit 1
    fi

    log_info "Python 3.11+ verificado ✓"
}

################################################################################
# User & Directory Setup
################################################################################

setup_user_permissions() {
    log_info "Configurando permissões para usuário $BOT_USER..."

    # Verificar se usuário existe
    if ! id "$BOT_USER" &>/dev/null; then
        log_error "Usuário $BOT_USER não existe!"
        log_error "Execute como: sudo bash deploy.sh (sem trocar de usuário)"
        exit 1
    fi

    # Add to docker group (se Docker estiver instalado)
    if command -v docker &>/dev/null; then
        if ! groups "$BOT_USER" | grep -q docker; then
            usermod -aG docker "$BOT_USER" || true
            log_info "Usuário $BOT_USER adicionado ao grupo docker"
            log_warn "⚠️  IMPORTANTE: O grupo docker apenas ativa após logout/login"
            log_warn "   Se escolher Docker no próximo passo, script executará como root"
            log_warn "   e ajustará permissões automaticamente"
        else
            log_info "Usuário $BOT_USER já está no grupo docker"
        fi
    fi

    log_info "Bot será instalado em: $BOT_DIR"
    log_info "Usuário: $BOT_USER"
}

create_directories() {
    log_info "Criando diretórios..."

    # Criar diretórios como usuário (não como root)
    if [[ ! -d "$BOT_DIR" ]]; then
        sudo -u "$BOT_USER" mkdir -p "$BOT_DIR"
        log_info "Diretório $BOT_DIR criado"
    else
        log_warn "Diretório $BOT_DIR já existe"
    fi

    # Subdiretórios
    sudo -u "$BOT_USER" mkdir -p "$BOT_DIR/data"
    sudo -u "$BOT_USER" mkdir -p "$BOT_DIR/logs"
    sudo -u "$BOT_USER" mkdir -p "$BOT_DIR/configs"

    log_info "Usuário $BOT_USER tem controle total do diretório"
}

################################################################################
# Bot Installation
################################################################################

clone_repository() {
    log_info "Clonando repositório..."

    # Se já existe, fazer pull
    if [[ -d "$BOT_DIR/.git" ]]; then
        log_warn "Repositório já existe, fazendo pull..."
        # Git pull em subshell com cd para manter contexto correto
        sudo -u "$BOT_USER" bash -c "cd '$BOT_DIR' && git pull"
        log_info "Repositório atualizado"
    else
        log_warn "⚠️  Clone o repositório manualmente como usuário $BOT_USER:"
        log_warn "   su - $BOT_USER"
        log_warn "   git clone <seu-repo-url> ~/smartmoney-bot"
        log_warn "   exit"
        read -p "Pressione ENTER após clonar o repositório..." || true

        if [[ ! -d "$BOT_DIR/.git" ]]; then
            log_error "Repositório não encontrado em $BOT_DIR"
            exit 1
        fi
        log_info "Repositório encontrado"
    fi

    # Validar arquivos críticos
    local required_files=("$BOT_DIR/.env.example" "$BOT_DIR/requirements.txt" "$BOT_DIR/docker-compose.yml")
    for file in "${required_files[@]}"; do
        if [[ ! -f "$file" ]]; then
            log_error "Arquivo crítico não encontrado: $file"
            log_error "Verifique se o repositório foi clonado corretamente"
            exit 1
        fi
    done
    log_info "Todos os arquivos críticos validados ✓"
}

setup_environment() {
    log_info "Configurando ambiente..."

    # Criar .env se não existir
    if [[ ! -f "$BOT_DIR/.env" ]]; then
        log_warn "Arquivo .env não encontrado!"
        log_info "Criando .env a partir do template..."

        # Copiar e setar ownership ANTES de chmod
        sudo -u "$BOT_USER" cp "$BOT_DIR/.env.example" "$BOT_DIR/.env"

        log_warn "IMPORTANTE: Edite $BOT_DIR/.env com suas credenciais:"
        log_warn "  - BOT_TOKEN (obtenha via @BotFather)"
        log_warn "  - CHANNEL_CHAT_ID (ID do canal Telegram)"
        log_warn "  - ADMIN_CHANNEL_ID (ID do canal admin)"

        # Proteger .env com ownership correto (user ja é owner via sudo -u)
        sudo -u "$BOT_USER" chmod 600 "$BOT_DIR/.env"

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

    # Verificar se usuário está no grupo docker
    if ! groups "$BOT_USER" | grep -q docker; then
        log_warn "⚠️  Usuário $BOT_USER ainda não tem permissão docker"
        log_warn "   Faça logout/login OU execute como root para Docker"
        log_warn "   Continuando com build como root (permissões serão ajustadas)..."
    fi

    # Build da imagem como usuário (se tiver permissão docker)
    if groups "$BOT_USER" | grep -q docker; then
        sudo -u "$BOT_USER" bash -c "cd '$BOT_DIR' && docker compose build"
    else
        # Executar como root em subshell para manter working directory correto
        (cd "$BOT_DIR" && docker compose build)
        # Ajustar permissões dos arquivos criados
        chown -R "$BOT_USER:$BOT_USER" "$BOT_DIR"
    fi

    # Start do container como usuário (se tiver permissão docker)
    if groups "$BOT_USER" | grep -q docker; then
        sudo -u "$BOT_USER" bash -c "cd '$BOT_DIR' && docker compose up -d"
    else
        # Executar como root em subshell para manter working directory correto
        (cd "$BOT_DIR" && docker compose up -d)
    fi

    log_info "Bot iniciado via Docker"
    log_info "Logs: docker compose -f $BOT_DIR/docker-compose.yml logs -f"
}

deploy_with_python() {
    log_info "Fazendo deploy com Python nativo..."

    # Criar venv como bot user em contexto correto
    sudo -u "$BOT_USER" bash -c "cd '$BOT_DIR' && python3 -m venv .venv"

    # Instalar dependências em contexto correto
    sudo -u "$BOT_USER" bash -c "cd '$BOT_DIR' && .venv/bin/pip install --upgrade pip"
    sudo -u "$BOT_USER" bash -c "cd '$BOT_DIR' && .venv/bin/pip install -r requirements.txt"

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

    # Configurar sudoers para permitir restart sem senha
    echo "$BOT_USER ALL=(ALL) NOPASSWD: /bin/systemctl restart smartmoney-bot" | tee /etc/sudoers.d/smartmoney-bot > /dev/null
    chmod 0440 /etc/sudoers.d/smartmoney-bot

    # Cron entry para healthcheck
    local CRON_ENTRY="*/5 * * * * /usr/local/bin/smartmoney-health || sudo /bin/systemctl restart smartmoney-bot"

    # Verificar se cron entry já existe para evitar duplicatas
    if crontab -u "$BOT_USER" -l 2>/dev/null | grep -q "smartmoney-health"; then
        log_warn "Cron entry para smartmoney-health já existe, atualizando..."
        # Remove entry antiga e adiciona nova
        (crontab -u "$BOT_USER" -l 2>/dev/null | grep -v "smartmoney-health"; echo "$CRON_ENTRY") | crontab -u "$BOT_USER" -
    else
        # Adicionar nova entrada
        (crontab -u "$BOT_USER" -l 2>/dev/null; echo "$CRON_ENTRY") | crontab -u "$BOT_USER" -
    fi

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
    echo "1. Verifique o .env (como usuário $BOT_USER, sem sudo):"
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
    log_info "Debian-based Distros (Ubuntu, Debian, etc)"
    echo ""

    # Pre-flight checks
    check_root
    check_debian_based

    # Ask deployment method with validation
    DEPLOY_METHOD=""
    while [[ -z "$DEPLOY_METHOD" ]]; do
        echo "Escolha o método de deployment:"
        echo "1) Docker (recomendado - isolado, fácil de gerenciar)"
        echo "2) Python nativo (systemd - melhor performance)"
        read -p "Escolha (1/2): " -n 1 -r
        echo ""

        case "$REPLY" in
            1)
                DEPLOY_METHOD="docker"
                ;;
            2)
                DEPLOY_METHOD="python"
                ;;
            *)
                log_error "Opção inválida: '$REPLY'. Use 1 ou 2."
                ;;
        esac
    done

    log_info "Método selecionado: $DEPLOY_METHOD"

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
    setup_user_permissions
    create_directories
    clone_repository
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
    log_info "Script execução bem-sucedida em distro Debian-based"
}

# Run main
main "$@"
