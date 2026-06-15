#!/usr/bin/env bash
set -euo pipefail
INSTALL_DIR="${INSTALL_DIR:-/volume1/docker/cursor-automation}"
ENV_FILE="$INSTALL_DIR/.env"
if [[ ! -f "$ENV_FILE" ]]; then echo "ERREUR: $ENV_FILE introuvable"; exit 1; fi
set_kv() { local key="$1" val="$2"; if grep -q "^${key}=" "$ENV_FILE"; then sed -i "s|^${key}=.*|${key}=${val}|" "$ENV_FILE"; else echo "${key}=${val}" >> "$ENV_FILE"; fi }
set_kv "N8N_EDITOR_BASE_URL" "https://diveapps.serveblog.net/n8n"
set_kv "N8N_PATH" "/n8n"
set_kv "N8N_PROTOCOL" "https"
set_kv "N8N_SECURE_COOKIE" "true"
set_kv "WEBHOOK_URL" "https://diveapps.serveblog.net/n8n/"
set_kv "N8N_BASIC_AUTH_ACTIVE" "true"
if ! grep -q "^N8N_BASIC_AUTH_USER=" "$ENV_FILE" || grep -q "^N8N_BASIC_AUTH_USER=$" "$ENV_FILE"; then
  BASIC_USER="${N8N_BASIC_AUTH_USER:-n8nadmin}"
  BASIC_PASS="${N8N_BASIC_AUTH_PASSWORD:-$(openssl rand -base64 24 | tr -d '/+=' | head -c 24)}"
  set_kv "N8N_BASIC_AUTH_USER" "$BASIC_USER"
  set_kv "N8N_BASIC_AUTH_PASSWORD" "$BASIC_PASS"
  echo "Basic Auth user: $BASIC_USER"
fi
echo "OK: .env mis a jour."