#!/usr/bin/env bash
set -euo pipefail
INSTALL_DIR="${INSTALL_DIR:-/volume1/docker/cursor-automation}"
ENV_FILE="$INSTALL_DIR/.env"
SECRETS_DIR="$INSTALL_DIR/secrets"
HTPASSWD_FILE="$SECRETS_DIR/n8n.htpasswd"
GATEWAY_ENV="$SECRETS_DIR/n8n-gateway.env"

if [[ ! -f "$ENV_FILE" ]]; then echo "ERREUR: $ENV_FILE introuvable"; exit 1; fi
mkdir -p "$SECRETS_DIR"

set_kv() {
  local key="$1" val="$2"
  if grep -q "^${key}=" "$ENV_FILE"; then
    sed -i "s|^${key}=.*|${key}=${val}|" "$ENV_FILE"
  else
    echo "${key}=${val}" >> "$ENV_FILE"
  fi
}

set_kv "N8N_EDITOR_BASE_URL" "https://diveapps.serveblog.net/n8n"
set_kv "N8N_PROTOCOL" "https"
set_kv "N8N_SECURE_COOKIE" "true"
set_kv "WEBHOOK_URL" "https://diveapps.serveblog.net/n8n/"
sed -i '/^N8N_PATH=/d' "$ENV_FILE"
sed -i '/^N8N_BASIC_AUTH_/d' "$ENV_FILE"

if [[ ! -f "$HTPASSWD_FILE" ]]; then
  GATEWAY_USER="${N8N_GATEWAY_USER:-n8nadmin}"
  GATEWAY_PASS="${N8N_GATEWAY_PASSWORD:-$(openssl rand -base64 18 | tr -d '/+=' | head -c 20)}"
  HASH=$(openssl passwd -apr1 "$GATEWAY_PASS")
  echo "${GATEWAY_USER}:${HASH}" > "$HTPASSWD_FILE"
  chmod 600 "$HTPASSWD_FILE"
  cat > "$GATEWAY_ENV" <<EOF
# Auth nginx (popup navigateur) — pas dans le conteneur n8n
N8N_GATEWAY_USER=${GATEWAY_USER}
N8N_GATEWAY_PASSWORD=${GATEWAY_PASS}
EOF
  chmod 600 "$GATEWAY_ENV"
  echo "Gateway nginx cree: user=${GATEWAY_USER} (voir secrets/n8n-gateway.env)"
else
  echo "OK: $HTPASSWD_FILE existe deja"
fi

echo "OK: .env mis a jour (sans N8N_PATH / N8N_BASIC_AUTH — n8n 2.23)."
