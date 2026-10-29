"""Configuração lida das variáveis de ambiente (arquivo .env na VPS)."""
import os
import pathlib
from functools import lru_cache

import yaml

AQUI = pathlib.Path(__file__).resolve().parent

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://geoportal:geoportal@localhost:5432/geoportal")
SEGREDO_JWT = os.environ.get("SEGREDO_JWT", "")
SESSAO_HORAS = int(os.environ.get("SESSAO_HORAS", "12"))
COOKIE_SEGURO = os.environ.get("COOKIE_SEGURO", "1") == "1"   # 0 só em teste local sem HTTPS
PASTA_DADOS = pathlib.Path(os.environ.get("PASTA_DADOS", "/dados"))
CAMADAS_YAML = pathlib.Path(os.environ.get("CAMADAS_YAML", str(AQUI / "camadas.yaml")))

# Fase 2 — busca automática no WFS da SEMA-MT. Fica desligada enquanto estas duas não forem preenchidas.
SEMA_WFS_URL = os.environ.get("SEMA_WFS_URL", "")
SEMA_AUTHKEY = os.environ.get("SEMA_AUTHKEY", "")
SEMA_TYPENAME_ATP = os.environ.get("SEMA_TYPENAME_ATP", "Geoportal:MVW_REQUERIMENTO_ATP")
SEMA_CAMPO_CAR = os.environ.get("SEMA_CAMPO_CAR", "NUMEROESTADUAL")


def segredo_jwt() -> str:
    if not SEGREDO_JWT or len(SEGREDO_JWT) < 32:
        raise RuntimeError("Defina SEGREDO_JWT no .env com pelo menos 32 caracteres (o install.sh gera um).")
    return SEGREDO_JWT


@lru_cache
def catalogo() -> dict:
    with open(CAMADAS_YAML, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    for c in cfg["camadas"]:
        c.setdefault("visivel", True)
        c.setdefault("min_zoom", 8)
        c.setdefault("preenchimento", True)
        c.setdefault("tracejado", None)
    return cfg


def camada(slug: str) -> dict | None:
    return next((c for c in catalogo()["camadas"] if c["slug"] == slug), None)


def camadas_por_papel(papel: str) -> list[dict]:
    return [c for c in catalogo()["camadas"] if c.get("papel") == papel]
