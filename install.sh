#!/usr/bin/env bash
# Instala o Geoportal Bioma numa VPS Ubuntu 22.04/24.04. Rode como root (ou com sudo) dentro da pasta do projeto.
set -euo pipefail
cd "$(dirname "$0")"
PASTA="$(pwd)"

echo "== Geoportal Bioma — instalação =="

if ! command -v docker >/dev/null 2>&1; then
  echo "-> Instalando o Docker…"
  curl -fsSL https://get.docker.com | sh
fi

if [ ! -f .env ]; then
  cp .env.example .env
  read -rp "Endereço do geoportal (ex.: geo.solucoesagroambientais.com): " DOMINIO
  sed -i "s|^DOMINIO=.*|DOMINIO=${DOMINIO}|" .env
  sed -i "s|^DB_SENHA=.*|DB_SENHA=$(openssl rand -hex 24)|" .env
  sed -i "s|^SEGREDO_JWT=.*|SEGREDO_JWT=$(openssl rand -hex 32)|" .env
  chmod 600 .env
  echo "-> .env criado com senhas novas."
fi

mkdir -p dados/bases dados/cars backups
chown -R 1000:1000 dados

if command -v ufw >/dev/null 2>&1; then
  ufw allow OpenSSH >/dev/null; ufw allow 80/tcp >/dev/null; ufw allow 443/tcp >/dev/null
  ufw --force enable >/dev/null || true
fi

echo "-> Subindo banco, aplicação e HTTPS…"
docker compose up -d --build
docker compose exec -T app python -m geoportal migrar

# Rotinas: backup diário às 2h30 e retriagem da carteira toda segunda às 5h
( crontab -l 2>/dev/null | grep -v "geoportal-bioma" ;
  echo "30 2 * * * cd ${PASTA} && bash scripts/backup.sh >> backups/backup.log 2>&1 # geoportal-bioma"
  echo "0 5 * * 1 cd ${PASTA} && docker compose exec -T app python -m geoportal retriar >> backups/retriagem.log 2>&1 # geoportal-bioma"
) | crontab -

echo
echo "Pronto. Agora crie o seu usuário de administrador:"
echo "  docker compose exec app python -m geoportal criar-usuario SEU@EMAIL \"Seu Nome\" --admin"
echo
echo "Depois abra https://$(grep ^DOMINIO= .env | cut -d= -f2)"
