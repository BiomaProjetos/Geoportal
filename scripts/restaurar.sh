#!/usr/bin/env bash
# Restaura um backup: ./scripts/restaurar.sh backups/geoportal-AAAA-MM-DD.dump
set -euo pipefail
cd "$(dirname "$0")/.."
[ -f "${1:-}" ] || { echo "Uso: $0 backups/geoportal-AAAA-MM-DD.dump"; exit 1; }
read -rp "Isso substitui o banco atual pelo backup $1. Digite RESTAURAR para continuar: " OK
[ "$OK" = "RESTAURAR" ] || exit 1
docker compose exec -T db pg_restore -U geoportal -d geoportal --clean --if-exists < "$1"
echo "Backup restaurado."
