"""Gera dados FICTÍCIOS para testar o Geoportal Bioma sem as bases reais.

Cria em ./exemplo/:
  bases/<slug>.zip   shapefiles das bases de referência (nomes de arquivo = slug do camadas.yaml)
  cars/<CAR>.zip     zip no formato do Simcar: ATP, APP, AVN e AREA_CONSOLIDADA
  modulo_fiscal_exemplo.csv
"""
import math
import pathlib
import random
import sys
import tempfile
import zipfile

import numpy as np
import pyogrio.raw
from shapely import affinity
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import unary_union

SAIDA = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "exemplo")
CRS = "EPSG:4674"

PROPS = [
    dict(car="MT100245/2023", nome="FAZENDA SANTA CLARA DO JURUENA (EXEMPLO)", mun="Juína", lat=-11.29, lng=-58.60, r=1.9, seed=11,
         fito="Floresta Ombrófila Aberta", river=(18, -.25, .22, .03), avn=(110, .38, .86),
         prodes=[(2003, "open", .55), (2005, "open", .5), (2007, "open", .42), (2012, "avn", .2), (2019, "avn", .25), (2023, "avn", .16)],
         emb=[("embargo_sema", 4)], mb=[5], sigef=(.04, -.025, .988, "EX-7F3C-A91"), snci=None,
         custeio=[("2021/22", "BANCO DO BRASIL", "SOJA", 1380000, "open", .75), ("2023/24", "BANCO DA AMAZONIA", "SOJA", 910000, 4, .32)],
         viz=(300, .55, "MT009901/2019"), ti=(215, 6.2, 5.0), ucgap=True),
    dict(car="MT087731/2021", nome="SITIO BOA ESPERANCA (EXEMPLO)", mun="Juara", lat=-11.18, lng=-57.43, r=.92, seed=23,
         fito="Floresta Ombrófila Aberta", river=(-35, .12, .12, .03), avn=(20, .4, .55),
         prodes=[(2002, "open", .35), (2006, "open", .3)], emb=[], mb=[], sigef=None, snci=None,
         custeio=[("2023/24", "SICOOB", "PASTAGEM", 120000, "open", .3)], viz=None, ti=None, ucgap=False),
    dict(car="MT154902/2024", nome="FAZENDA CHAPADAO VERDE (EXEMPLO)", mun="Nova Mutum", lat=-13.70, lng=-56.21, r=2.75, seed=37,
         fito="Savana Arborizada", river=(70, .3, .3, .05), avn=(250, .42, .62),
         prodes=[(2001, "open", .9), (2004, "open", .8), (2008, "open", .6), (2011, "avn", .32), (2016, "avn", .28)],
         emb=[("embargo_ibama", 3)], mb=[], sigef=(-.03, .03, .994, "EX-2B80-C17"), snci=None,
         custeio=[("2022/23", "BANCO DO BRASIL", "ALGODAO", 3150000, "open", .95), ("2024/25", "BANCO DO BRASIL", "SOJA", 2900000, 3, .45)],
         viz=None, ti=None, ucgap=False),
    dict(car="MT063318/2020", nome="FAZENDA RIO DAS PEDRAS (EXEMPLO)", mun="Campo Verde", lat=-15.47, lng=-55.27, r=1.7, seed=41,
         fito="Savana Parque", river=(-10, -.3, .18, .03), avn=(200, .35, .78),
         prodes=[(2002, "open", .6), (2005, "open", .55)], emb=[], mb=[], sigef=(.008, .006, .999, "EX-91D4-0E2"), snci=None,
         custeio=[("2024/25", "SICREDI", "SOJA", 1040000, "open", .7)], viz=None, ti=None, ucgap=False),
]


def kdeg(lat, dx, dy):
    return dx / (111.32 * math.cos(math.radians(lat))), dy / 110.574


def blob(c, rkm, n, jit, R):
    pts = []
    for i in range(n):
        a = i / n * 2 * math.pi
        r = rkm * (1 - jit + R.random() * 2 * jit)
        dx, dy = kdeg(c[1], math.cos(a) * r, math.sin(a) * r)
        pts.append((c[0] + dx, c[1] + dy))
    return Polygon(pts).buffer(0)


def off(c, ang, km):
    a = math.radians(ang)
    dx, dy = kdeg(c[1], math.cos(a) * km, math.sin(a) * km)
    return (c[0] + dx, c[1] + dy)


def amostra(poly, R):
    x0, y0, x1, y1 = poly.bounds
    for _ in range(500):
        p = Point(x0 + R.random() * (x1 - x0), y0 + R.random() * (y1 - y0))
        if poly.contains(p):
            return (p.x, p.y)
    c = poly.representative_point()
    return (c.x, c.y)


def gerar(p):
    R = random.Random(p["seed"])
    c = (p["lng"], p["lat"])
    g = {}
    g["atp"] = blob(c, p["r"], 16, .16, R)
    ang, o, amp, w = p["river"]
    pts = []
    for i in range(41):
        t = -1.6 + 3.2 * i / 40
        along, perp = t * p["r"], o * p["r"] + math.sin(t * 3.1) * amp * p["r"] * .6
        a = math.radians(ang)
        dx, dy = kdeg(p["lat"], math.cos(a) * along - math.sin(a) * perp, math.sin(a) * along + math.cos(a) * perp)
        pts.append((c[0] + dx, c[1] + dy))
    rio = LineString(pts)
    g["app"] = rio.buffer(w / 111.0).intersection(g["atp"])
    d, of, rr = p["avn"]
    avn0 = blob(off(c, d, of * p["r"]), rr * p["r"], 14, .2, R).intersection(g["atp"])
    avn_raw = avn0.difference(g["app"])
    g["open"] = g["atp"].difference(avn0).difference(g["app"])
    g["prodes"] = []
    for ano, onde, r in p["prodes"]:
        host = avn_raw if onde == "avn" else g["open"]
        f = blob(amostra(host, R), r, 10, .3, R).intersection(host)
        g["prodes"].append((ano, f))
    pos = unary_union([f for a, f in g["prodes"] if a >= 2009]) if any(a >= 2009 for a, _ in g["prodes"]) else None
    g["avn"] = avn_raw.difference(pos) if pos else avn_raw
    pre = [f for a, f in g["prodes"] if a < 2009]
    g["uso_cons"] = g["open"].difference(pre[-1]) if p["ucgap"] and pre else g["open"]
    g["rio"] = rio
    return g, R


def escrever(path, geoms, campos: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    wkb = np.array([geom.wkb for geom in geoms], dtype=object)
    nomes = list(campos)
    dados = [np.array(campos[k], dtype=object if isinstance(campos[k][0], str) else None) for k in nomes]
    tipo = "MultiPolygon" if geoms[0].geom_type in ("Polygon", "MultiPolygon") else geoms[0].geom_type
    if tipo == "MultiPolygon":
        from shapely.geometry import MultiPolygon
        wkb = np.array([(MultiPolygon([gm]) if gm.geom_type == "Polygon" else gm).wkb for gm in geoms], dtype=object)
    pyogrio.raw.write(str(path), wkb, dados, nomes, geometry_type=tipo, crs=CRS, driver="ESRI Shapefile", encoding="UTF-8")


def zipar(destino, pasta):
    with zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(pathlib.Path(pasta).iterdir()):
            z.write(f, f.name)


def main():
    bases = {k: ([], {}) for k in ["embargo_sema", "embargo_ibama", "embargo_icmbio", "prodes", "uso_consolidado", "radam",
                                   "sigef", "sicor_glebas", "car_estadual", "ti_entorno", "mapbiomas_alerta"]}

    def add(slug, geom, **attrs):
        geoms, campos = bases[slug]
        geoms.append(geom)
        for k, v in attrs.items():
            campos.setdefault(k, []).append(v)

    for p in PROPS:
        g, R = gerar(p)
        with tempfile.TemporaryDirectory() as tmp:
            t = pathlib.Path(tmp)
            escrever(t / "ATP.shp", [g["atp"]], {"NUMEROESTADUAL": [p["car"]], "NOMEIMOVEL": [p["nome"]], "MUNICIPIO": [p["mun"]]})
            escrever(t / "APP.shp", [g["app"]], {"CLASSE": ["Rio ate 10 m"]})
            escrever(t / "AVN.shp", [g["avn"]], {"TIPO": ["AVN"]})
            escrever(t / "AREA_CONSOLIDADA.shp", [g["open"]], {"TIPO": ["AC"]})
            (SAIDA / "cars").mkdir(parents=True, exist_ok=True)
            zipar(SAIDA / "cars" / (p["car"].replace("/", "_") + ".zip"), t)
        for ano, f in g["prodes"]:
            add("prodes", f, year=float(ano), main_class="desmatamento")
        for slug, idx in p["emb"]:
            add(slug, g["prodes"][idx][1].buffer(0.0005), NUMERO=f"TAD-EX-{p['seed']}", DATA="2020-08-14")
        for idx in p["mb"]:
            add("mapbiomas_alerta", g["prodes"][idx][1], ALERTA=f"EX-{p['seed']}", ANO=2023)
        add("uso_consolidado", g["uso_cons"], FONTE="EXEMPLO")
        add("radam", g["atp"].buffer(0.05), FITOECOLOG=p["fito"])
        if p["sigef"]:
            dx, dy, s, cod = p["sigef"]
            f = affinity.scale(g["atp"], s, s)
            f = affinity.translate(f, *kdeg(p["lat"], dx, dy))
            add("sigef", f, parcela_co=cod)
        for ano, banco, cultura, valor, onde, r in p["custeio"]:
            ctr = g["prodes"][onde][1].representative_point().coords[0] if isinstance(onde, int) else amostra(g["open"], R)
            add("sicor_glebas", blob(ctr, r, 12, .2, R).intersection(g["atp"]), ANO_SAFRA=ano, INSTITUICAO=banco,
                FINALIDADE="CUSTEIO AGRICOLA", PRODUTO=cultura, VALOR=float(valor))
        if p["viz"]:
            d, r, cod = p["viz"]
            add("car_estadual", blob(off((p["lng"], p["lat"]), d, p["r"] * 1.3), r * p["r"], 12, .15, R), NUMEROESTADUAL=cod)
        add("car_estadual", g["atp"], NUMEROESTADUAL=p["car"])
        if p["ti"]:
            d, dist, r = p["ti"]
            add("ti_entorno", blob(off((p["lng"], p["lat"]), d, dist), r, 18, .08, R), NOME="ENTORNO TI EXEMPLO")

    for slug, (geoms, campos) in bases.items():
        if not geoms:
            continue
        with tempfile.TemporaryDirectory() as tmp:
            escrever(pathlib.Path(tmp) / f"{slug}.shp", geoms, campos)
            (SAIDA / "bases").mkdir(parents=True, exist_ok=True)
            zipar(SAIDA / "bases" / f"{slug}.zip", tmp)
    (SAIDA / "modulo_fiscal_exemplo.csv").write_text(
        "municipio;ha\nJuína;100\nJuara;100\nNova Mutum;100\nCampo Verde;80\n", encoding="utf-8")
    print(f"Dados de exemplo em {SAIDA.resolve()}")


if __name__ == "__main__":
    main()
