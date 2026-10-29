#!/usr/bin/env bash
# Cópia do banco em backups/ (guarda 14 dias). Copie a pasta backups/ para fora da VPS com frequência.
set -euo pipefail
cd "$(dirname "$0")/.."
ARQ="backups/geoportal-$(date +%F).dump"
docker compose exec -T db pg_dump -U geoportal -Fc geoportal > "$ARQ"
find backups -name 'geoportal-*.dump' -mtime +14 -delete
echo "$(date '+%F %T') backup ok: $ARQ ($(du -h "$ARQ" | cut -f1))"
