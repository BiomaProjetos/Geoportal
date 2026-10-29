"""Teste de ponta a ponta da API. Precisa de um PostGIS com os dados de exemplo importados.

  DATABASE_URL=... SEGREDO_JWT=... COOKIE_SEGURO=0 pytest tests/test_api.py
"""
import pathlib

from fastapi.testclient import TestClient

from geoportal import auth
from geoportal.main import app

EXEMPLO = pathlib.Path(__file__).parent.parent.parent.parent / "exemplo"


def cliente():
    auth.criar_usuario("teste@bioma.local", "Teste", "senha-de-teste-123", "admin")
    c = TestClient(app)
    r = c.post("/api/login", json={"email": "teste@bioma.local", "senha": "senha-de-teste-123"})
    assert r.status_code == 200, r.text
    return c


def test_sem_login_bloqueia():
    c = TestClient(app)
    assert c.get("/api/imoveis").status_code == 401
    assert c.post("/api/login", json={"email": "teste@bioma.local", "senha": "errada"}).status_code == 401


def test_fluxo_completo():
    c = cliente()
    cfg = c.get("/api/config").json()
    assert any(x["slug"] == "prodes" and x["carregada"] for x in cfg["camadas"])
    lista = c.get("/api/imoveis").json()
    assert len(lista) >= 4
    im = c.get("/api/imovel", params={"car": "MT100245/2023"}).json()
    tipos = {f["properties"]["tipo"] for f in im["geojson"]["features"]}
    assert {"ATP", "APP", "AVN", "AC"} <= tipos
    t = c.post("/api/triagem", params={"car": "MT100245/2023"}).json()
    assert t["resumo"]["criticos"] >= 3
    assert t["reserva_legal"]["pct"] == 0.8
    gj = c.get("/api/camadas/prodes/geojson", params={"bbox": "-59,-12,-58,-11", "z": 13}).json()
    assert len(gj["features"]) >= 1
    longe = c.get("/api/camadas/prodes/geojson", params={"bbox": "-59,-12,-58,-11", "z": 6}).json()
    assert longe["features"] == [] and "aviso" in longe
    assert c.patch("/api/imovel", params={"car": "MT100245/2023"}, json={"situacao": "Em análise"}).status_code == 200
    assert c.patch("/api/imovel", params={"car": "MT100245/2023"}, json={"origem": "X"}).status_code == 400
    zipcar = EXEMPLO / "cars" / "MT087731_2021.zip"
    with open(zipcar, "rb") as f:
        r = c.post("/api/imovel", files={"arquivo": ("MT087731_2021.zip", f, "application/zip")},
                   data={"origem": "Carteira Bioma"})
    assert r.status_code == 200, r.text
    assert r.json()["car"] == "MT087731/2021"
    assert c.post("/api/imovel/sema", json={"car": "MT1/2020"}).status_code == 409
