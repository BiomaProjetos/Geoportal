"""Importação de bases de referência e de imóveis (CAR) para o PostGIS.

Formatos aceitos: shapefile (.shp ou .zip com shapefile), GeoPackage (.gpkg), KML/KMZ, GeoJSON.
"""
from __future__ import annotations

import csv
import io
import json
import pathlib
import re
import unicodedata
import zipfile
from datetime import date, datetime

import pyogrio
import pyogrio.raw
from pyproj import CRS

from . import config, db

LOTE = 5000
EXT_VETOR = (".shp", ".gpkg", ".kml", ".kmz", ".geojson", ".json")


# ---------------------------------------------------------------- utilidades
def normalizar(txt: str) -> str:
    t = unicodedata.normalize("NFKD", str(txt or "")).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", t).strip().upper()


def _valor(v):
    if v is None:
        return None
    if hasattr(v, "item"):          # tipos numpy
        v = v.item()
    if isinstance(v, float) and v != v:  # NaN
        return None
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    if isinstance(v, bytes):
        return v.decode("utf-8", "replace")
    return v


def caminhos_vetoriais(caminho: pathlib.Path) -> list[str]:
    """Lista os conjuntos de dados que o GDAL deve ler (entra em .zip com /vsizip/)."""
    caminho = pathlib.Path(caminho)
    if caminho.suffix.lower() == ".zip":
        with zipfile.ZipFile(caminho) as z:
            nomes = [n for n in z.namelist() if n.lower().endswith(EXT_VETOR) and not n.startswith("__MACOSX")]
        if not nomes:
            raise ValueError(f"Nenhum arquivo vetorial dentro de {caminho.name}")
        return [f"/vsizip/{caminho}/{n}" for n in nomes]
    if caminho.suffix.lower() not in EXT_VETOR:
        raise ValueError(f"Formato não suportado: {caminho.suffix}")
    return [str(caminho)]


def _srid(meta: dict, srid_padrao: int | None) -> int:
    crs = meta.get("crs")
    if crs:
        epsg = CRS.from_user_input(crs).to_epsg(min_confidence=20)
        if epsg:
            return epsg
    if srid_padrao:
        return srid_padrao
    raise ValueError("Não consegui identificar o sistema de coordenadas do arquivo. "
                     "Informe com --srid (ex.: 4674 para SIRGAS 2000).")


def ler_em_lotes(caminho: str, encoding: str | None = None, srid_padrao: int | None = None):
    """Gera (srid, tipo_geom, nomes_campos, linhas) em lotes; linhas = [(attrs_json, wkb_hex)]."""
    info = pyogrio.read_info(caminho, encoding=encoding)
    total = info.get("features") or 0
    pulo = 0
    while True:
        meta, _fids, geoms, dados = pyogrio.raw.read(caminho, skip_features=pulo, max_features=LOTE,
                                                     encoding=encoding)
        n = len(geoms)
        if n == 0:
            break
        srid = _srid(meta, srid_padrao)
        campos = list(meta["fields"])
        cols = [arr.tolist() if hasattr(arr, "tolist") else list(arr) for arr in dados]
        linhas = []
        for i in range(n):
            if geoms[i] is None:
                continue
            attrs = {campos[j]: _valor(cols[j][i]) for j in range(len(campos))}
            linhas.append((json.dumps(attrs, ensure_ascii=False, default=str), bytes(geoms[i]).hex()))
        yield srid, meta.get("geometry_type") or "", campos, linhas
        pulo += n
        if total and pulo >= total:
            break


def _expr_geom(tipo_geom: str) -> str:
    """SQL que corrige e reprojeta a geometria lida (parâmetros: wkb hex, srid)."""
    base = "ST_Transform(ST_SetSRID(ST_GeomFromWKB(decode(%s,'hex')), %s), 4674)"
    if "Polygon" in tipo_geom or tipo_geom == "Unknown" or not tipo_geom:
        return f"ST_Multi(ST_CollectionExtract(ST_MakeValid(ST_Force2D({base})), 3))"
    return f"ST_Force2D({base})"


# ---------------------------------------------------------------- bases de referência
def importar_base(slug: str, arquivo, encoding: str | None = None,
                  srid: int | None = None, log=print) -> int:
    """Importa (ou substitui) a base bases.<slug> a partir de um ou mais arquivos (lista), que entram juntos.
    Retorna o nº de feições."""
    if not config.camada(slug):
        raise ValueError(f"Camada '{slug}' não existe no camadas.yaml")
    arquivos = [pathlib.Path(a) for a in (arquivo if isinstance(arquivo, (list, tuple)) else [arquivo])]
    tabela = db.tabela_base(slug)
    nova = db.tabela_base(f"{slug}__nova")
    total = 0
    with db.conexao() as con:
        with con.transaction():
            con.execute(f"DROP TABLE IF EXISTS {nova}")
            con.execute(f"CREATE TABLE {nova} (gid serial PRIMARY KEY, attrs jsonb, geom geometry(Geometry,4674))")
            for caminho in [c for a in arquivos for c in caminhos_vetoriais(a)]:
                for s, tipo, _c, linhas in ler_em_lotes(caminho, encoding, srid):
                    sql = f"INSERT INTO {nova}(attrs, geom) VALUES (%s::jsonb, {_expr_geom(tipo)})"
                    with con.cursor() as cur:
                        cur.executemany(sql, [(a, w, s) for a, w in linhas])
                    total += len(linhas)
                    log(f"  {slug}: {total} feições…")
            con.execute(f"DELETE FROM {nova} WHERE geom IS NULL OR ST_IsEmpty(geom)")
            con.execute(f"CREATE INDEX ON {nova} USING gist (geom)")
            con.execute(f"DROP TABLE IF EXISTS {tabela}")
            con.execute(f'ALTER TABLE {nova} RENAME TO "{slug}"')
            total = con.execute(f"SELECT count(*) AS n FROM {tabela}").fetchone()["n"]
            con.execute("""INSERT INTO bases.catalogo(slug, arquivo, feicoes, versao_em) VALUES (%s,%s,%s,now())
                           ON CONFLICT (slug) DO UPDATE SET arquivo=EXCLUDED.arquivo, feicoes=EXCLUDED.feicoes,
                           versao_em=now()""", (slug, ", ".join(a.name for a in arquivos), total))
        con.execute(f"ANALYZE {tabela}")
    log(f"{slug}: {total} feições importadas de {', '.join(a.name for a in arquivos)}")
    return total


# ---------------------------------------------------------------- imóvel (CAR)
CAMPOS_CAR = ["NUMEROESTADUAL", "NUMERO_ESTADUAL", "NUM_CAR", "NUMERO_CAR", "COD_IMOVEL", "CAR", "COD_CAR"]
CAMPOS_NOME = ["NOMEIMOVEL", "NOME_IMOVEL", "NOM_IMOVEL", "NOME_PROPRIEDADE", "IMOVEL", "NOME"]
CAMPOS_MUN = ["MUNICIPIO", "NOME_MUNICIPIO", "NOM_MUNICIPIO", "MUNIC"]
CAMPOS_PROP = ["PROPRIETARIO", "NOMEPROPRIETARIO", "NOME_PROPRIETARIO", "INTERESSADO", "REQUERENTE"]


def _campo(attrs: dict, opcoes: list[str]):
    chaves = {normalizar(k).replace(" ", "_"): k for k in attrs}
    for o in opcoes:
        for alvo in (o, o[:10]):
            if alvo in chaves and attrs[chaves[alvo]] not in (None, ""):
                return str(attrs[chaves[alvo]]).strip()
    return None


def classificar(nome_arquivo: str) -> str | None:
    n = normalizar(pathlib.PurePosixPath(nome_arquivo).stem)
    for regra in config.catalogo()["imovel_tipos"]:
        if any(chave in n for chave in regra["nomes_arquivo"]):
            return regra["tipo"]
    return None


def normalizar_car(car: str) -> str:
    return re.sub(r"\s+", "", str(car or "")).upper()


def importar_car(arquivo: str | pathlib.Path, car: str | None = None, dados: dict | None = None,
                 encoding: str | None = None, srid: int | None = None, usuario: str | None = None) -> dict:
    """Importa o perímetro e as camadas de um imóvel a partir do zip exportado do Simcar/Geoportal SEMA
    (ou de um KML/SHP só com o perímetro). Retorna os dados do imóvel."""
    dados = {k: v for k, v in (dados or {}).items() if v not in (None, "")}
    arquivo = pathlib.Path(arquivo)
    camadas = []   # (tipo, srid, tipo_geom, linhas)
    for caminho in caminhos_vetoriais(arquivo):
        tipo = classificar(caminho)
        for s, tg, _c, linhas in ler_em_lotes(caminho, encoding, srid):
            camadas.append((tipo, s, tg, linhas))
    if not camadas:
        raise ValueError("O arquivo não tem feições.")
    poligonais = [c for c in camadas if "Polygon" in c[2]]
    atp = [c for c in camadas if c[0] == "ATP"]
    if not atp:
        if len(poligonais) == 1 or len(camadas) == 1:
            atp = [poligonais[0] if poligonais else camadas[0]]
        else:
            raise ValueError("Não encontrei o perímetro do imóvel (arquivo com ATP, PERIMETRO ou AREA_IMOVEL no nome).")
    _t, s_atp, tg_atp, linhas_atp = atp[0]
    attrs0 = json.loads(linhas_atp[0][0]) if linhas_atp else {}
    car = normalizar_car(car or _campo(attrs0, CAMPOS_CAR) or "")
    if not car:
        raise ValueError("Informe o número do CAR (não veio nos atributos do arquivo).")
    dados.setdefault("nome", _campo(attrs0, CAMPOS_NOME))
    dados.setdefault("municipio", _campo(attrs0, CAMPOS_MUN))
    dados.setdefault("proprietario", _campo(attrs0, CAMPOS_PROP))

    with db.conexao() as con, con.transaction():
        con.execute("CREATE TEMP TABLE _atp(geom geometry) ON COMMIT DROP")
        with con.cursor() as cur:
            cur.executemany(f"INSERT INTO _atp VALUES ({_expr_geom(tg_atp)})", [(w, s_atp) for _a, w in linhas_atp])
        geom_sql = "(SELECT ST_Multi(ST_CollectionExtract(ST_MakeValid(ST_Union(geom)),3)) FROM _atp)"
        campos = ["nome", "municipio", "proprietario", "situacao", "origem", "analista", "observacoes", "pct_rl"]
        vals = {c: dados.get(c) for c in campos}
        existe = con.execute("SELECT 1 FROM imoveis WHERE car=%s", (car,)).fetchone()
        if existe:
            sets = ", ".join(f"{c}=COALESCE(%({c})s, {c})" for c in campos)
            con.execute(f"UPDATE imoveis SET {sets}, geom={geom_sql}, atualizado_em=now(), triagem=NULL WHERE car=%(car)s",
                        {**vals, "car": car})
        else:
            vals["situacao"] = vals["situacao"] or "Aguardando análise"
            vals["origem"] = vals["origem"] or "Prospecção"
            con.execute(f"""INSERT INTO imoveis(car, {', '.join(campos)}, geom)
                            VALUES (%(car)s, {', '.join('%(' + c + ')s' for c in campos)}, {geom_sql})""",
                        {**vals, "car": car})
        con.execute("UPDATE imoveis SET area_ha = ST_Area(geom::geography)/10000 WHERE car=%s", (car,))
        con.execute("DELETE FROM imovel_camadas WHERE car=%s", (car,))
        for c in camadas:
            tipo, s, tg, linhas = c
            if c is atp[0] or tipo == "ATP":
                continue
            with con.cursor() as cur:
                cur.executemany(f"INSERT INTO imovel_camadas(car, tipo, attrs, geom) VALUES (%s,%s,%s::jsonb,{_expr_geom(tg)})",
                                [(car, tipo or "OUTRO", a, w, s) for a, w in linhas])
        con.execute("DELETE FROM imovel_camadas WHERE car=%s AND (geom IS NULL OR ST_IsEmpty(geom))", (car,))
        con.execute("INSERT INTO consultas(usuario, car, acao) VALUES (%s,%s,'importou CAR')", (usuario, car))
        r = con.execute("SELECT car, nome, municipio, area_ha FROM imoveis WHERE car=%s", (car,)).fetchone()
    return r


# ---------------------------------------------------------------- módulos fiscais
def importar_modulo_fiscal(arquivo_csv: str | pathlib.Path) -> int:
    """CSV com colunas municipio;ha (separador ; ou ,)."""
    texto = pathlib.Path(arquivo_csv).read_text(encoding="utf-8-sig")
    sep = ";" if texto.count(";") >= texto.count(",") else ","
    linhas = list(csv.DictReader(io.StringIO(texto), delimiter=sep))
    with db.conexao() as con, con.transaction():
        for l in linhas:
            mun = normalizar(l.get("municipio") or l.get("MUNICIPIO") or "")
            ha = str(l.get("ha") or l.get("HA") or "").replace(",", ".")
            if mun and ha:
                con.execute("""INSERT INTO modulo_fiscal VALUES (%s,%s)
                               ON CONFLICT (municipio) DO UPDATE SET ha=EXCLUDED.ha""", (mun, float(ha)))
    return len(linhas)
