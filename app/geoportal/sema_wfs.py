"""Fase 2 — busca automática do perímetro do CAR no WFS do Geoportal SEMA-MT.

Fica desligada até SEMA_WFS_URL e SEMA_AUTHKEY estarem no .env. A requisição segue o mesmo padrão
do arquivo wfsrequest.txt que vem dentro das exportações SHP do Geoportal (typename, cql_filter,
outputformat=SHAPE-ZIP). A authkey fica só no servidor e nunca é enviada ao navegador.
"""
from __future__ import annotations

import pathlib
import tempfile
import urllib.parse
import urllib.request

from . import config, importar


def ligado() -> bool:
    return bool(config.SEMA_WFS_URL and config.SEMA_AUTHKEY)


def montar_url(car: str, typename: str | None = None) -> str:
    car = importar.normalizar_car(car)
    filtro = f"{config.SEMA_CAMPO_CAR} ilike '%{car}%'"
    params = {
        "service": "WFS", "version": "1.0.0", "request": "GetFeature",
        "typename": typename or config.SEMA_TYPENAME_ATP,
        "outputformat": "SHAPE-ZIP", "cql_filter": filtro,
        "authkey": config.SEMA_AUTHKEY,
    }
    return f"{config.SEMA_WFS_URL}?{urllib.parse.urlencode(params, quote_via=urllib.parse.quote)}"


def buscar_car(car: str, usuario: str | None = None, timeout: int = 120) -> dict:
    if not ligado():
        raise RuntimeError("Busca na SEMA desligada: preencha SEMA_WFS_URL e SEMA_AUTHKEY no .env.")
    with tempfile.TemporaryDirectory() as tmp:
        destino = pathlib.Path(tmp) / "car.zip"
        req = urllib.request.Request(montar_url(car), headers={"User-Agent": "GeoportalBioma/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp, open(destino, "wb") as f:
            f.write(resp.read())
        if destino.stat().st_size < 200:
            raise ValueError("A SEMA não devolveu feições para esse CAR.")
        return importar.importar_car(destino, car=car, usuario=usuario)
