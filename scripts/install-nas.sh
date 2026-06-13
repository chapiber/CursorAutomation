#!/usr/bin/env bash
# Installation CursorAutomation sur NAS Synology.
# Usage : bash scripts/install-nas.sh
# Prérequis : git, docker compose, accès /volume1/docker/
set -euo pipefail

INSTALL_DIR="${INSTALL_DIR:-/volume1/docker/cursor-automation}"
REPO_URL="${REPO_URL:-https://github.com/chapiber/CursorAutomation.git}"

echo "=== CursorAutomation — installation NAS ==="
echo "Répertoire : $INSTALL_DIR"

if [[ ! -d "$INSTALL_DIR" ]]; then
  mkdir -p "$INSTALL_DIR"
fi

cd "$INSTALL_DIR"

if [[ ! -d ".git" ]]; then
  echo "[1/5] Clone $REPO_URL"
  git clone "$REPO_URL" .
else
  echo "[1/5] Déjà cloné — git pull"
  git pull --ff-only || true
fi

if [[ ! -f ".env" ]]; then
  echo "[2/5] Création .env depuis .env.example"
  cp .env.example .env
  echo ""
  echo "IMPORTANT : éditer $INSTALL_DIR/.env"
  echo "  - CURSOR_API_KEY"
  echo "  - RUNNER_API_KEY  (openssl rand -hex 32)"
  echo "  - N8N_ENCRYPTION_KEY (openssl rand -hex 32)"
  echo ""
else
  echo "[2/5] .env existant — conservé"
fi

mkdir -p workspaces logs n8n_data secrets
chmod 700 secrets 2>/dev/null || true
# n8n : propriétaire = utilisateur Synology (évite EACCES sur volume bind)
N8N_UID=$(id -u 2>/dev/null || echo 1000)
N8N_GID=$(id -g 2>/dev/null || echo 1000)
if grep -q '^N8N_UID=' .env 2>/dev/null; then
  sed -i "s/^N8N_UID=.*/N8N_UID=$N8N_UID/" .env
  sed -i "s/^N8N_GID=.*/N8N_GID=$N8N_GID/" .env
else
  echo "N8N_UID=$N8N_UID" >> .env
  echo "N8N_GID=$N8N_GID" >> .env
fi

if [[ ! -d "workspaces/MyDiveClub/.git" ]]; then
  echo "[3/5] Clone initial MyDiveClub (pour git pull / deploy)"
  git clone --branch main https://github.com/chapiber/MyDiveClub.git workspaces/MyDiveClub || \
    echo "[WARN] Clone MyDiveClub échoué — sera retenté au premier run"
else
  echo "[3/5] workspaces/MyDiveClub déjà présent"
fi

echo "[4/5] Build images Docker"
docker compose build

echo "[5/5] Démarrage stack"
docker compose up -d

echo ""
echo "=== Terminé ==="
echo "Santé runner : curl -s http://localhost:8765/health"
echo "n8n UI       : http://$(hostname -I 2>/dev/null | awk '{print $1}'):5678"
echo "Import workflow : n8n/workflows/cdm2026-daily.json"
echo "Doc test : docs/TEST-POC.md"
