#!/usr/bin/env bash
# Importa todas as bases colocadas em dados/bases/ (nome do arquivo começando pelo slug do camadas.yaml).
# Ex.: dados/bases/uso_consolidado.zip, dados/bases/prodes_amazonia.shp, dados/bases/radam.zip
set -euo pipefail
cd "$(dirname "$0")/.."
docker compose exec -T app python -m geoportal importar-pasta /dados/bases "$@"
docker compose exec -T app python -m geoportal retriar
docker compose exec -T app python -m geoportal bases
