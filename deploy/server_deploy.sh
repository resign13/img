#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/ai-batchpic}"
SERVICE_NAME="${SERVICE_NAME:-ai-batchpic-web}"
REPO_URL="${REPO_URL:-https://github.com/resign13/img.git}"
BRANCH="${BRANCH:-main}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
NODE_MAJOR="${NODE_MAJOR:-20}"
DOMAIN_NAME="${DOMAIN_NAME:-design.smawell.shop}"
APP_PORT="${APP_PORT:-10000}"

if ! command -v git >/dev/null 2>&1; then
  apt-get update
  apt-get install -y git
fi

if ! command -v curl >/dev/null 2>&1; then
  apt-get update
  apt-get install -y curl
fi

if ! command -v node >/dev/null 2>&1; then
  curl -fsSL "https://deb.nodesource.com/setup_${NODE_MAJOR}.x" | bash -
  apt-get install -y nodejs
fi

apt-get update
apt-get install -y python3 python3-venv python3-pip nginx

mkdir -p "$(dirname "$APP_DIR")"
if [ ! -d "$APP_DIR/.git" ]; then
  rm -rf "$APP_DIR"
  git clone --branch "$BRANCH" "$REPO_URL" "$APP_DIR"
else
  git -C "$APP_DIR" fetch origin "$BRANCH"
  git -C "$APP_DIR" checkout "$BRANCH"
  git -C "$APP_DIR" reset --hard "origin/$BRANCH"
fi

cd "$APP_DIR/web_app/frontend"
npm ci || npm install
npm run build

cd "$APP_DIR/web_app/backend"
$PYTHON_BIN -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

cat > /etc/systemd/system/${SERVICE_NAME}.service <<SERVICE
[Unit]
Description=AI BatchPic Web
After=network.target

[Service]
Type=simple
WorkingDirectory=${APP_DIR}/web_app/backend
EnvironmentFile=-${APP_DIR}/.env
Environment=APP_PORT=${APP_PORT}
ExecStart=${APP_DIR}/web_app/backend/.venv/bin/gunicorn --config gunicorn.conf.py run:app
Restart=always
RestartSec=5
User=root

[Install]
WantedBy=multi-user.target
SERVICE

systemctl daemon-reload
systemctl enable "$SERVICE_NAME"
systemctl restart "$SERVICE_NAME"

for attempt in $(seq 1 30); do
  if curl -fsS "http://127.0.0.1:${APP_PORT}/api/health" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

if [ -n "$DOMAIN_NAME" ]; then
  enabled_site="/etc/nginx/sites-enabled/${SERVICE_NAME}"
  conflicting_sites=""
  if [ -d /etc/nginx/sites-enabled ]; then
    conflicting_sites="$(grep -RslE "server_name[[:space:]].*\\b${DOMAIN_NAME//./\\.}\\b" /etc/nginx/sites-enabled 2>/dev/null || true)"
    conflicting_sites="$(printf "%s\n" "$conflicting_sites" | grep -vx "$enabled_site" || true)"
  fi
  if [ -n "$conflicting_sites" ]; then
    echo "Existing nginx site already owns ${DOMAIN_NAME}; preserving its configuration:"
    printf "%s\n" "$conflicting_sites"
    echo "Skipping nginx changes and continuing with the application service restart."
  else

  CERT_DIR="/etc/letsencrypt/live/${DOMAIN_NAME}"
  if [ ! -f "${CERT_DIR}/fullchain.pem" ] || [ ! -f "${CERT_DIR}/privkey.pem" ]; then
    PARENT_DOMAIN="${DOMAIN_NAME#*.}"
    if [ "$PARENT_DOMAIN" != "$DOMAIN_NAME" ] && [ -f "/etc/letsencrypt/live/${PARENT_DOMAIN}/fullchain.pem" ] && [ -f "/etc/letsencrypt/live/${PARENT_DOMAIN}/privkey.pem" ]; then
      CERT_DIR="/etc/letsencrypt/live/${PARENT_DOMAIN}"
    fi
  fi
  SSL_BLOCK=""
  if [ -f "${CERT_DIR}/fullchain.pem" ] && [ -f "${CERT_DIR}/privkey.pem" ]; then
    SSL_BLOCK=$(cat <<SSL

server {
    listen 443 ssl;
    server_name ${DOMAIN_NAME};

    client_max_body_size 80m;
    ssl_certificate ${CERT_DIR}/fullchain.pem;
    ssl_certificate_key ${CERT_DIR}/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;

    location / {
        proxy_pass http://127.0.0.1:${APP_PORT};
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 360s;
        proxy_send_timeout 360s;
    }
}
SSL
)
  fi

  cat > /etc/nginx/sites-available/${SERVICE_NAME} <<NGINX
server {
    listen 80;
    server_name ${DOMAIN_NAME};

    client_max_body_size 80m;

    location / {
        proxy_pass http://127.0.0.1:${APP_PORT};
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 360s;
        proxy_send_timeout 360s;
    }
}
${SSL_BLOCK}
NGINX
  ln -sf /etc/nginx/sites-available/${SERVICE_NAME} /etc/nginx/sites-enabled/${SERVICE_NAME}
  nginx -t
  systemctl reload nginx
  fi
fi

systemctl status "$SERVICE_NAME" --no-pager -l
