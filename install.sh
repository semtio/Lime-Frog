#!/bin/bash
set -e

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "=== SEO Checker - Автоматическая установка на Linux ==="

# Функция для вывода ошибок
error_exit() {
    echo -e "${RED}[ОШИБКА]${NC} $1" >&2
    exit 1
}

info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

# Проверка root прав
if [ "$EUID" -ne 0 ]; then
    error_exit "Запустите с sudo: sudo ./install.sh"
fi

# Переменные
APP_DIR="/opt/seo-checker"
APP_USER="www-data"
VENV_DIR="$APP_DIR/venv"
SERVICE_NAME="seo-checker"
APP_PORT=""

info "Определяю окружение..."

# Проверка дистрибутива
if [ -f /etc/os-release ]; then
    . /etc/os-release
    info "ОС: $NAME $VERSION"
else
    error_exit "Не удалось определить дистрибутив Linux"
fi

# Проверка панели управления
PANEL_DETECTED="none"
if command -v v-list-users &> /dev/null || [ -d /usr/local/hestia ]; then
    PANEL_DETECTED="hestia"
    warn "Обнаружена панель HestiaCP/VestaCP"
elif [ -d /usr/local/vesta ]; then
    PANEL_DETECTED="vesta"
    warn "Обнаружена панель VestaCP"
fi

# Функция поиска свободного порта
find_free_port() {
    local start_port=$1
    local port=$start_port
    while ss -tlnp | grep -q ":$port "; do
        ((port++))
        if [ $port -gt 9000 ]; then
            error_exit "Не удалось найти свободный порт в диапазоне $start_port-9000"
        fi
    done
    echo $port
}

# Определение порта для приложения
if ss -tlnp | grep -q ":80 "; then
    warn "Порт 80 уже занят (вероятно, веб-сервером или панелью)"
    APP_PORT=$(find_free_port 8085)
    info "Будет использован порт: $APP_PORT"
else
    APP_PORT=80
    info "Порт 80 свободен, будет использован"
fi

info "[1/8] Установка системных пакетов..."
apt-get update -qq || error_exit "Не удалось обновить репозитории"
apt-get install -y python3 python3-pip python3-venv nginx ufw curl || error_exit "Не удалось установить пакеты"

# Проверка пользователя
if ! id "$APP_USER" &>/dev/null; then
    warn "Пользователь $APP_USER не существует, создаю..."
    useradd -r -s /bin/false $APP_USER || error_exit "Не удалось создать пользователя"
fi

info "[2/8] Создание директории приложения..."
mkdir -p "$APP_DIR"
cp -r . "$APP_DIR/" || error_exit "Не удалось скопировать файлы"
chown -R $APP_USER:$APP_USER "$APP_DIR"

info "[3/8] Создание виртуального окружения..."
sudo -u $APP_USER python3 -m venv "$VENV_DIR" || error_exit "Не удалось создать venv"
sudo -u $APP_USER "$VENV_DIR/bin/pip" install --upgrade pip -q
sudo -u $APP_USER "$VENV_DIR/bin/pip" install -r "$APP_DIR/requirements.txt" -q || error_exit "Не удалось установить зависимости"

info "[4/8] Настройка Nginx..."
# Создаём директории для sites-enabled
mkdir -p /etc/nginx/sites-available
mkdir -p /etc/nginx/sites-enabled

# Создаём конфиг из шаблона с нужным портом
cat > /etc/nginx/sites-available/seo-checker <<EOF
server {
    listen $APP_PORT;
    server_name _;

    client_max_body_size 10M;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 120s;
    }

    location /static {
        alias /opt/seo-checker/static;
        expires 30d;
    }
}
EOF

ln -sf /etc/nginx/sites-available/seo-checker /etc/nginx/sites-enabled/seo-checker

# Добавляем include в главный конфиг, если его нет
if ! grep -q "include /etc/nginx/sites-enabled/" /etc/nginx/nginx.conf; then
    sed -i '/http {/a \    include /etc/nginx/sites-enabled/*;' /etc/nginx/nginx.conf
fi

nginx -t || error_exit "Конфигурация Nginx содержит ошибки"
systemctl reload nginx || error_exit "Не удалось перезагрузить Nginx"

info "[5/8] Создание systemd сервиса..."
cat > /etc/systemd/system/$SERVICE_NAME.service <<EOF
[Unit]
Description=SEO Checker (Gunicorn)
After=network.target

[Service]
Type=notify
User=$APP_USER
Group=$APP_USER
WorkingDirectory=$APP_DIR
Environment="PATH=$VENV_DIR/bin"
ExecStart=$VENV_DIR/bin/gunicorn -c $APP_DIR/gunicorn.conf.py app:app
ExecReload=/bin/kill -s HUP \$MAINPID
KillMode=mixed
TimeoutStopSec=5
PrivateTmp=true
Restart=always

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable $SERVICE_NAME || error_exit "Не удалось включить автозапуск сервиса"
systemctl restart $SERVICE_NAME || error_exit "Не удалось запустить сервис"

info "[6/8] Настройка Firewall..."
if command -v ufw &> /dev/null; then
    ufw --force enable
    ufw allow 22/tcp
    ufw allow $APP_PORT/tcp
    ufw reload
    info "UFW настроен (открыты порты: 22, $APP_PORT)"
else
    warn "UFW не установлен, пропускаю настройку firewall"
fi

info "[7/8] Ожидание запуска сервиса..."
sleep 3

# Проверка статуса сервиса
if ! systemctl is-active --quiet $SERVICE_NAME; then
    error_exit "Сервис не запустился. Проверьте логи: journalctl -u $SERVICE_NAME -n 50"
fi

# Проверка что Gunicorn слушает порт 8000
if ! ss -tlnp | grep -q "127.0.0.1:8000"; then
    error_exit "Gunicorn не слушает порт 8000. Проверьте логи: journalctl -u $SERVICE_NAME -n 50"
fi

# Проверка что Nginx слушает APP_PORT
if ! ss -tlnp | grep -q ":$APP_PORT "; then
    error_exit "Nginx не слушает порт $APP_PORT"
fi

info "[8/8] Валидация доступности приложения..."

# Получаем IP сервера
SERVER_IP=$(hostname -I | awk '{print $1}')
APP_URL="http://127.0.0.1:$APP_PORT"

# Проверяем доступность через curl
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" $APP_URL || echo "000")

if [ "$HTTP_CODE" != "200" ]; then
    error_exit "Приложение не отвечает (HTTP $HTTP_CODE). URL: $APP_URL"
fi

echo ""
echo -e "${GREEN}✅ Установка завершена успешно!${NC}"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Приложение запущено и доступно по адресу:"
echo ""
if [ "$APP_PORT" = "80" ]; then
    echo "  http://$SERVER_IP"
else
    echo "  http://$SERVER_IP:$APP_PORT"
fi
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Управление сервисом:"
echo "  sudo systemctl status $SERVICE_NAME"
echo "  sudo systemctl restart $SERVICE_NAME"
echo "  sudo systemctl stop $SERVICE_NAME"
echo "  sudo journalctl -u $SERVICE_NAME -f"
echo ""
echo "Nginx логи:"
echo "  tail -f /var/log/nginx/access.log"
echo "  tail -f /var/log/nginx/error.log"
echo ""

WorkingDirectory=$APP_DIR
Environment="PATH=$VENV_DIR/bin"
ExecStart=$VENV_DIR/bin/gunicorn -c $APP_DIR/gunicorn.conf.py app:app
ExecReload=/bin/kill -s HUP \$MAINPID
KillMode=mixed
TimeoutStopSec=5
PrivateTmp=true
Restart=always

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable $SERVICE_NAME
systemctl restart $SERVICE_NAME

echo "[6/7] Настройка Firewall (UFW)..."
ufw --force enable
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw reload

echo "[7/7] Проверка статуса..."
systemctl status $SERVICE_NAME --no-pager || true
nginx -t

echo ""
echo "✅ Установка завершена!"
echo ""
echo "Сервис запущен на http://$(hostname -I | awk '{print $1}')"
echo ""
echo "Управление сервисом:"
echo "  sudo systemctl status $SERVICE_NAME"
echo "  sudo systemctl restart $SERVICE_NAME"
echo "  sudo systemctl logs -f $SERVICE_NAME  # просмотр логов"
echo ""
echo "Nginx логи:"
echo "  /var/log/nginx/access.log"
echo "  /var/log/nginx/error.log"
