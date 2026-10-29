"""API e páginas do Geoportal Bioma."""
from __future__ import annotations

import json
import pathlib
import tempfile
import time
from collections import defaultdict
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, Request, Response, UploadFile
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import auth, config, db, importar, sema_wfs, triagem

@asynccontextmanager
async def vida(_app):
    yield
    db.fechar()


app = FastAPI(title="Geoportal Bioma", docs_url=None, redoc_url=None, openapi_url=None, lifespan=vida)
ESTATICO = config.AQUI / "static"
MAX_UPLOAD = 300 * 1024 * 1024
SITUACOES = ["Prospecção", "Aguardando análise", "Em análise", "Distribuído", "Aguardando complementação",
             "Enviado", "Aprovado", "Arquivado"]


@app.middleware("http")
async def cabecalhos(request: Request, call_next):
    resp = await call_next(request)
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["Referrer-Policy"] = "same-origin"
    resp.headers["X-Frame-Options"] = "DENY"
    if request.url.path.startswith("/api/"):
        resp.headers["Cache-Control"] = "no-store"
    return resp


def registrar(usuario: str, car: str | None, acao: str):
    with db.conexao() as con:
        con.execute("INSERT INTO consultas(usuario, car, acao) VALUES (%s,%s,%s)", (usuario, car, acao))


# ------------------------------------------------------------------ sessão
class Login(BaseModel):
    email: str
    senha: str


_tentativas: dict[str, list[float]] = defaultdict(list)


@app.post("/api/login")
def login(dados: Login, request: Request, response: Response):
    ip = request.headers.get("x-forwarded-for", request.client.host if request.client else "?").split(",")[0]
    agora = time.time()
    _tentativas[ip] = [t for t in _tentativas[ip] if agora - t < 300]
    if len(_tentativas[ip]) >= 8:
        raise HTTPException(429, "Muitas tentativas. Espere 5 minutos e tente de novo.")
    u = auth.autenticar(dados.email.strip(), dados.senha)
    if not u:
        _tentativas[ip].append(agora)
        raise HTTPException(401, "E-mail ou senha incorretos.")
    _tentativas.pop(ip, None)
    response.set_cookie(auth.COOKIE, auth.emitir_token(u), httponly=True, secure=config.COOKIE_SEGURO,
                        samesite="strict", max_age=config.SESSAO_HORAS * 3600, path="/")
    registrar(u["email"], None, "login")
    return {"nome": u["nome"], "perfil": u["perfil"]}


@app.post("/api/logout")
def logout(response: Response):
    response.delete_cookie(auth.COOKIE, path="/")
    return {"ok": True}


@app.get("/api/eu")
def eu(u: dict = Depends(auth.usuario_atual)):
    return u


# ------------------------------------------------------------------ catálogo e camadas
@app.get("/api/config")
def configuracao(u: dict = Depends(auth.usuario_atual)):
    cfg = config.catalogo()
    with db.conexao() as con:
        cat = {r["slug"]: r for r in con.execute("SELECT slug, feicoes, versao_em FROM bases.catalogo").fetchall()}
    camadas = []
    for c in cfg["camadas"]:
        info = cat.get(c["slug"])
        camadas.append({k: c.get(k) for k in ("slug", "nome", "grupo", "fonte", "papel", "cor", "tracejado",
                                              "preenchimento", "min_zoom", "visivel")}
                       | {"carregada": bool(info), "feicoes": info["feicoes"] if info else 0,
                          "versao_em": info["versao_em"].isoformat() if info else None})
    return {"camadas": camadas, "fundos": cfg.get("fundos", []), "imovel_tipos": cfg.get("imovel_tipos", []),
            "situacoes": SITUACOES, "busca_sema": sema_wfs.ligado(), "usuario": u}


@app.get("/api/camadas/{slug}/geojson")
def camada_geojson(slug: str, bbox: str = Query(...), z: int = Query(12, ge=0, le=22),
                   u: dict = Depends(auth.usuario_atual)):
    c = config.camada(slug)
    if not c:
        raise HTTPException(404, "Camada desconhecida.")
    if z < int(c.get("min_zoom", 8)):
        return {"type": "FeatureCollection", "features": [], "aviso": "Aproxime o mapa para ver esta camada."}
    try:
        w, s, e, n = (float(v) for v in bbox.split(","))
    except ValueError:
        raise HTTPException(400, "bbox inválido.")
    tol = 360 / (256 * 2 ** z) / 2
    with db.conexao() as con:
        if not db.base_existe(con, slug):
            return {"type": "FeatureCollection", "features": [], "aviso": "Base ainda não importada."}
        rows = con.execute(f"""SELECT gid, attrs, ST_AsGeoJSON(ST_SimplifyPreserveTopology(geom, %s), 6) AS g
                               FROM {db.tabela_base(slug)}
                               WHERE geom && ST_MakeEnvelope(%s,%s,%s,%s,4674) LIMIT 4001""",
                           (tol, w, s, e, n)).fetchall()
    excedeu = len(rows) > 4000
    feats = [{"type": "Feature", "id": r["gid"], "properties": r["attrs"] or {}, "geometry": json.loads(r["g"])}
             for r in rows[:4000] if r["g"]]
    out = {"type": "FeatureCollection", "features": feats}
    if excedeu:
        out["aviso"] = "Muitas feições nesta área: aproxime para ver todas."
    return out


# ------------------------------------------------------------------ imóveis
def _imovel_resumo(r: dict) -> dict:
    t = r.get("triagem") or {}
    return {"car": r["car"], "nome": r["nome"], "municipio": r["municipio"], "proprietario": r["proprietario"],
            "situacao": r["situacao"], "origem": r["origem"], "analista": r["analista"],
            "area_ha": float(r["area_ha"]) if r["area_ha"] is not None else None,
            "triagem_em": r["triagem_em"].isoformat() if r["triagem_em"] else None,
            "resumo": t.get("resumo"), "atualizado_em": r["atualizado_em"].isoformat()}


@app.get("/api/imoveis")
def listar_imoveis(u: dict = Depends(auth.usuario_atual)):
    with db.conexao() as con:
        rows = con.execute("""SELECT car, nome, municipio, proprietario, situacao, origem, analista, area_ha,
                                     triagem, triagem_em, atualizado_em FROM imoveis
                              ORDER BY atualizado_em DESC""").fetchall()
    return [_imovel_resumo(r) for r in rows]


@app.get("/api/imovel")
def ver_imovel(car: str, u: dict = Depends(auth.usuario_atual)):
    car = importar.normalizar_car(car)
    with db.conexao() as con:
        r = con.execute("""SELECT car, nome, municipio, proprietario, situacao, origem, analista, observacoes,
                                  pct_rl, area_ha, triagem, triagem_em, atualizado_em,
                                  ST_AsGeoJSON(geom, 7) AS g FROM imoveis WHERE car=%s""", (car,)).fetchone()
        if not r:
            raise HTTPException(404, "CAR não cadastrado. Importe o zip do Simcar ou busque na SEMA.")
        cams = con.execute("""SELECT tipo, attrs, ST_AsGeoJSON(geom, 7) AS g FROM imovel_camadas
                              WHERE car=%s ORDER BY tipo""", (car,)).fetchall()
    feats = [{"type": "Feature", "properties": {"tipo": "ATP"}, "geometry": json.loads(r["g"])}] if r["g"] else []
    feats += [{"type": "Feature", "properties": {"tipo": c["tipo"], **(c["attrs"] or {})}, "geometry": json.loads(c["g"])}
              for c in cams if c["g"]]
    registrar(u["email"], car, "consultou")
    return {**_imovel_resumo(r), "observacoes": r["observacoes"], "pct_rl": float(r["pct_rl"]) if r["pct_rl"] else None,
            "triagem": r["triagem"], "geojson": {"type": "FeatureCollection", "features": feats}}


@app.post("/api/imovel")
async def novo_imovel(arquivo: UploadFile = File(...), car: str = Form(""), nome: str = Form(""),
                      municipio: str = Form(""), proprietario: str = Form(""), situacao: str = Form(""),
                      origem: str = Form(""), analista: str = Form(""), u: dict = Depends(auth.usuario_atual)):
    nome_arq = pathlib.Path(arquivo.filename or "arquivo.zip").name
    if not nome_arq.lower().endswith((".zip",) + importar.EXT_VETOR):
        raise HTTPException(400, "Envie o .zip exportado do Simcar/Geoportal SEMA, ou um KML/KMZ/GeoJSON do perímetro.")
    with tempfile.TemporaryDirectory() as tmp:
        destino = pathlib.Path(tmp) / nome_arq
        tamanho = 0
        with open(destino, "wb") as f:
            while bloco := await arquivo.read(1024 * 1024):
                tamanho += len(bloco)
                if tamanho > MAX_UPLOAD:
                    raise HTTPException(413, "Arquivo maior que 300 MB.")
                f.write(bloco)
        try:
            r = importar.importar_car(destino, car=car or None, usuario=u["email"],
                                      dados={"nome": nome, "municipio": municipio, "proprietario": proprietario,
                                             "situacao": situacao, "origem": origem, "analista": analista})
        except ValueError as e:
            raise HTTPException(400, str(e))
    triagem.calcular(r["car"])
    return {"car": r["car"], "nome": r["nome"], "area_ha": float(r["area_ha"] or 0)}


class BuscaSema(BaseModel):
    car: str


@app.post("/api/imovel/sema")
def buscar_sema(dados: BuscaSema, u: dict = Depends(auth.usuario_atual)):
    if not sema_wfs.ligado():
        raise HTTPException(409, "A busca automática na SEMA ainda não está ligada. Importe o zip exportado do Geoportal.")
    try:
        r = sema_wfs.buscar_car(dados.car, usuario=u["email"])
    except Exception as e:  # erro de rede ou resposta da SEMA
        raise HTTPException(502, f"Não consegui buscar na SEMA: {e}")
    triagem.calcular(r["car"])
    return {"car": r["car"], "nome": r["nome"]}


class Edicao(BaseModel):
    nome: str | None = None
    municipio: str | None = None
    proprietario: str | None = None
    situacao: str | None = None
    origem: str | None = None
    analista: str | None = None
    observacoes: str | None = None
    pct_rl: float | None = None


@app.patch("/api/imovel")
def editar_imovel(car: str, dados: Edicao, u: dict = Depends(auth.usuario_atual)):
    car = importar.normalizar_car(car)
    campos = dados.model_dump(exclude_unset=True)
    if "origem" in campos and campos["origem"] not in ("Carteira Bioma", "Prospecção"):
        raise HTTPException(400, "Origem deve ser 'Carteira Bioma' ou 'Prospecção'.")
    if not campos:
        return {"ok": True}
    sets = ", ".join(f"{k}=%({k})s" for k in campos)
    with db.conexao() as con:
        n = con.execute(f"UPDATE imoveis SET {sets}, atualizado_em=now() WHERE car=%(car)s", {**campos, "car": car}).rowcount
    if not n:
        raise HTTPException(404, "CAR não cadastrado.")
    registrar(u["email"], car, "editou " + ", ".join(campos))
    if "pct_rl" in campos or "municipio" in campos:
        triagem.calcular(car)
    return {"ok": True}


@app.delete("/api/imovel")
def apagar_imovel(car: str, u: dict = Depends(auth.so_admin)):
    car = importar.normalizar_car(car)
    with db.conexao() as con:
        con.execute("DELETE FROM imoveis WHERE car=%s", (car,))
    registrar(u["email"], car, "apagou")
    return {"ok": True}


@app.post("/api/triagem")
def recalcular(car: str, u: dict = Depends(auth.usuario_atual)):
    try:
        return triagem.calcular(car)
    except KeyError:
        raise HTTPException(404, "CAR não cadastrado.")


# ------------------------------------------------------------------ usuários (admin)
class NovoUsuario(BaseModel):
    email: str
    nome: str
    senha: str
    perfil: str = "analista"


@app.get("/api/usuarios")
def usuarios(u: dict = Depends(auth.so_admin)):
    with db.conexao() as con:
        return con.execute("SELECT email, nome, perfil, ativo, criado_em FROM usuarios ORDER BY nome").fetchall()


@app.post("/api/usuarios")
def criar(dados: NovoUsuario, u: dict = Depends(auth.so_admin)):
    if dados.perfil not in ("admin", "analista"):
        raise HTTPException(400, "Perfil inválido.")
    try:
        auth.criar_usuario(dados.email, dados.nome, dados.senha, dados.perfil)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"ok": True}


@app.exception_handler(HTTPException)
async def erro_http(request: Request, exc: HTTPException):
    return JSONResponse({"erro": exc.detail}, status_code=exc.status_code)


app.mount("/", StaticFiles(directory=ESTATICO, html=True), name="estatico")
