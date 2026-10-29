"""Triagem automática de um imóvel: cruza o perímetro do CAR com as bases de referência no PostGIS.

Resultado preliminar. Não substitui a análise do analista nem a validação da SEMA-MT.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from . import config, db
from .importar import normalizar, normalizar_car

ORDEM = {"critico": 0, "atencao": 1, "ok": 2}
HA = "ST_Area(({g})::geography)/10000"


def _ha(expr: str) -> str:
    return f"COALESCE({HA.format(g=expr)}, 0)"


def _pegar(attrs: dict, campo: str):
    if not campo:
        return None
    for o in (campo, campo[:10]):
        for k, v in attrs.items():
            if k.upper() == o.upper():
                return v
    return None


def _flag(nivel, icone, titulo, detalhe, valor):
    return {"nivel": nivel, "icone": icone, "titulo": titulo, "detalhe": detalhe, "valor": valor}


def _fmt(v, casas=2):
    s = f"{v:,.{casas}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def _attr(campo: str, alias: str = "b") -> str:
    """Lê um atributo tolerando nomes cortados em 10 caracteres (shapefile) e maiúsculas/minúsculas."""
    opcoes = dict.fromkeys([campo, campo[:10], campo.upper(), campo.lower(), campo.upper()[:10], campo.lower()[:10]])
    return "COALESCE(" + ", ".join(f"{alias}.attrs->>'{o}'" for o in opcoes) + ")"


def _ano_sql(campo: str) -> str:
    return f"NULLIF(substring({_attr(campo)} from '(\\d{{4}})'), '')::int"


def _area_tipo(con, car: str, tipo: str) -> float:
    r = con.execute(f"""SELECT {_ha('ST_Union(ST_Intersection(c.geom, i.geom))')} AS ha
                        FROM imovel_camadas c JOIN imoveis i USING (car)
                        WHERE car=%s AND tipo=%s AND ST_Dimension(c.geom)=2""", (car, tipo)).fetchone()
    return float(r["ha"] or 0)


def _tem_tipo(con, car: str, tipo: str) -> bool:
    return con.execute("SELECT 1 FROM imovel_camadas WHERE car=%s AND tipo=%s LIMIT 1", (car, tipo)).fetchone() is not None


def _sobreposicao(con, car: str, slug: str) -> dict:
    t = db.tabela_base(slug)
    r = con.execute(f"""SELECT count(*) AS n, {_ha('ST_Union(ST_Intersection(b.geom, i.geom))')} AS ha,
                               (array_agg(b.attrs))[1:5] AS exemplos
                        FROM {t} b JOIN imoveis i ON ST_Intersects(b.geom, i.geom)
                        WHERE i.car=%s""", (car,)).fetchone()
    return {"n": int(r["n"]), "ha": float(r["ha"] or 0), "exemplos": r["exemplos"] or []}


def calcular(car: str) -> dict:
    car = normalizar_car(car)
    cfg = config.catalogo()
    ano_pos = int(cfg.get("ano_prodes_pos_marco", 2009))
    with db.conexao() as con:
        im = con.execute("""SELECT car, nome, municipio, proprietario, situacao, origem, pct_rl,
                                   area_ha::float AS area_ha FROM imoveis WHERE car=%s""", (car,)).fetchone()
        if not im:
            raise KeyError(car)
        A = float(im["area_ha"] or 0)
        flags, servicos, sobreps, nao_carregadas, versoes = [], [], [], [], []
        carregadas = {r["slug"]: r for r in con.execute("SELECT slug, versao_em, arquivo FROM bases.catalogo").fetchall()}

        def existe(c):
            ok = c["slug"] in carregadas and db.base_existe(con, c["slug"])
            if ok:
                versoes.append({"camada": c["nome"], "versao_em": carregadas[c["slug"]]["versao_em"].isoformat(),
                                "arquivo": carregadas[c["slug"]]["arquivo"]})
            else:
                nao_carregadas.append(c["nome"])
            return ok

        # ---- camadas do próprio imóvel
        avn = _area_tipo(con, car, "AVN") if _tem_tipo(con, car, "AVN") else None
        app = _area_tipo(con, car, "APP") if _tem_tipo(con, car, "APP") else None
        ac_decl = _area_tipo(con, car, "AC") if _tem_tipo(con, car, "AC") else None

        # ---- desmatamento (PRODES)
        prodes_anos, pre, pos = [], 0.0, 0.0
        geom_pos_sql = []     # subconsultas que devolvem a geometria do desmate pós-marco
        for c in config.camadas_por_papel("desmate"):
            if not existe(c):
                continue
            t, campo = db.tabela_base(c["slug"]), c.get("campo_ano", "year")
            rows = con.execute(f"""SELECT {_ano_sql(campo)} AS ano,
                                          {_ha('ST_Union(ST_Intersection(b.geom, i.geom))')} AS ha
                                   FROM {t} b JOIN imoveis i ON ST_Intersects(b.geom, i.geom)
                                   WHERE i.car=%s GROUP BY 1 ORDER BY 1""", (car,)).fetchall()
            for r in rows:
                if r["ha"] and r["ha"] > 0.0001:
                    prodes_anos.append({"ano": r["ano"], "ha": round(float(r["ha"]), 4), "camada": c["nome"]})
                    if r["ano"] is not None and r["ano"] >= ano_pos:
                        pos += float(r["ha"])
                    else:
                        pre += float(r["ha"])
            geom_pos_sql.append(f"SELECT b.geom FROM {t} b WHERE {_ano_sql(campo)} >= {ano_pos}")
        if pos > 0.01:
            flags.append(_flag("critico", "flame", "Desmatamento após 22/07/2008",
                               f"PRODES {ano_pos} em diante. Exige recomposição, não admite compensação",
                               f"{_fmt(pos)} ha"))
            servicos.append("PRADA / recomposição")

        # ---- embargos
        embargos, geom_emb_sql = [], []
        for c in config.camadas_por_papel("embargo"):
            if not existe(c):
                continue
            o = _sobreposicao(con, car, c["slug"])
            geom_emb_sql.append(f"SELECT b.geom FROM {db.tabela_base(c['slug'])} b")
            sobreps.append({"camada": c["nome"], "slug": c["slug"], "nivel": "critico" if o["n"] else "ok", **o})
            if o["n"]:
                embargos.append({"orgao": c.get("orgao", c["nome"]), **o})
                flags.append(_flag("critico", "ban", f"Embargo {c.get('orgao', c['nome'])}",
                                   f"{o['n']} polígono(s) sobre o imóvel", f"{_fmt(o['ha'])} ha"))
        if embargos:
            servicos.append("Desembargo")

        # ---- alertas
        for c in config.camadas_por_papel("alerta"):
            if not existe(c):
                continue
            o = _sobreposicao(con, car, c["slug"])
            sobreps.append({"camada": c["nome"], "slug": c["slug"], "nivel": "atencao" if o["n"] else "ok", **o})
            if o["n"]:
                flags.append(_flag("atencao", "alert", c["nome"], f"{o['n']} alerta(s) sobre o imóvel", f"{_fmt(o['ha'])} ha"))

        # ---- uso consolidado
        uc_info = None
        for c in config.camadas_por_papel("uso_consolidado"):
            if not existe(c):
                continue
            t = db.tabela_base(c["slug"])
            base_ha = con.execute(f"""SELECT {_ha('ST_Union(ST_Intersection(b.geom, i.geom))')} AS ha
                                      FROM {t} b JOIN imoveis i ON ST_Intersects(b.geom, i.geom)
                                      WHERE i.car=%s""", (car,)).fetchone()["ha"]
            fora = None
            if ac_decl is not None:
                fora = con.execute(f"""
                    WITH ac AS (SELECT ST_Union(ST_Intersection(c.geom, i.geom)) g FROM imovel_camadas c
                                JOIN imoveis i USING (car) WHERE car=%(car)s AND tipo='AC' AND ST_Dimension(c.geom)=2),
                         base AS (SELECT ST_Union(ST_Intersection(b.geom, i.geom)) g FROM {t} b
                                  JOIN imoveis i ON ST_Intersects(b.geom, i.geom) WHERE i.car=%(car)s)
                    SELECT {_ha("ST_Difference(ac.g, COALESCE(base.g, ST_GeomFromText('POLYGON EMPTY',4674)))")} AS ha
                    FROM ac, base""", {"car": car}).fetchone()["ha"]
            uc_info = {"base_ha": float(base_ha or 0), "ac_declarada_ha": ac_decl,
                       "fora_da_base_ha": None if fora is None else float(fora)}
            sobreps.append({"camada": c["nome"], "slug": c["slug"], "n": 1 if base_ha else 0, "ha": float(base_ha or 0),
                            "nivel": "atencao" if (fora or 0) > 0.5 else "ok", "exemplos": []})
            if fora is not None and fora > 0.5:
                flags.append(_flag("atencao", "layers", "Área aberta fora da base de uso consolidado",
                                   "Comprovar abertura até 22/07/2008 com imagem da época (Landsat 5)", f"{_fmt(fora)} ha"))
                servicos.append("Comprovação de uso consolidado")
            elif fora is not None:
                flags.append(_flag("ok", "layers", "Área consolidada dentro da base da SEMA",
                                   "A base de uso consolidado cobre a área declarada", f"{_fmt(base_ha or 0)} ha"))

        # ---- fitofisionomia e percentual de RL
        fito, pct, pct_texto = None, None, None
        for c in config.camadas_por_papel("fitofisionomia"):
            if not existe(c):
                continue
            campo = c.get("campo_fito", "FITOECOLOG")
            r = con.execute(f"""SELECT {_attr(campo)} AS fito, {_ha('ST_Union(ST_Intersection(b.geom, i.geom))')} AS ha
                                FROM {db.tabela_base(c['slug'])} b JOIN imoveis i ON ST_Intersects(b.geom, i.geom)
                                WHERE i.car=%s GROUP BY 1 ORDER BY 2 DESC LIMIT 1""", (car,)).fetchone()
            if r and r["fito"]:
                fito = r["fito"]
                for regra in cfg.get("percentual_rl", []):
                    if any(p in normalizar(fito) for p in regra["contem"]):
                        pct, pct_texto = regra["pct"] / 100, regra["texto"]
                        break
        if im["pct_rl"] is not None:
            pct = float(im["pct_rl"]) / 100
            pct_texto = f"{float(im['pct_rl']):g}% — definido pelo analista"

        # ---- Reserva Legal
        mf_ha = con.execute("SELECT ha::float FROM modulo_fiscal WHERE municipio=%s",
                            (normalizar(im["municipio"] or ""),)).fetchone()
        mf = A / mf_ha["ha"] if mf_ha and mf_ha["ha"] else None
        rl = {"area_ha": A, "fitofisionomia": fito, "pct": pct, "pct_texto": pct_texto, "avn_ha": avn, "app_ha": app,
              "modulos_fiscais": mf, "mf_ha": mf_ha["ha"] if mf_ha else None, "desmate_pos_ha": pos}
        if pct is not None and avn is not None:
            rl["exigida_ha"] = pct * A
            rl["saldo_ha"] = avn - pct * A
            rl["saldo_com_app_ha"] = avn + (app or 0) - pct * A
            if rl["saldo_ha"] < 0 and mf is not None and mf <= 4:
                flags.append(_flag("atencao", "tree", "Passivo de RL sem o benefício do art. 67",
                                   f"Exigido {round(pct * 100)}% · até 4 MF, a RL pode se limitar à vegetação de 22/07/2008",
                                   f"{_fmt(-rl['saldo_ha'])} ha"))
            elif rl["saldo_ha"] < 0:
                flags.append(_flag("critico", "tree", "Passivo de Reserva Legal",
                                   f"Exigido {round(pct * 100)}% · vegetação nativa cobre {_fmt(avn / A * 100, 1)}% do imóvel",
                                   f"{_fmt(-rl['saldo_ha'])} ha"))
                servicos.append("Retificação com art. 67" if (mf is not None and mf <= 4)
                                else "Adesão ao PRA (recomposição ou compensação)")
            else:
                flags.append(_flag("ok", "tree", "Reserva Legal suficiente", "Excedente de vegetação nativa",
                                   f"+{_fmt(rl['saldo_ha'])} ha"))
        if mf is not None and mf <= 4:
            flags.append(_flag("ok", "leaf", "Até 4 módulos fiscais",
                               "Pode usar o art. 67: RL limitada à vegetação existente em 22/07/2008", f"{_fmt(mf, 1)} MF"))
            servicos.append("Cálculo de benefício (art. 67)")

        # ---- georreferenciamento
        georef = None
        georef_carregado = False
        for c in config.camadas_por_papel("georref"):
            if not existe(c):
                continue
            georef_carregado = True
            campo = c.get("campo_codigo")
            r = con.execute(f"""SELECT {_attr(campo)} AS codigo, {_ha('b.geom')} AS area,
                                       {_ha('ST_Intersection(b.geom, i.geom)')} AS comum
                                FROM {db.tabela_base(c['slug'])} b JOIN imoveis i ON ST_Intersects(b.geom, i.geom)
                                WHERE i.car=%s ORDER BY 3 DESC LIMIT 1""", (car,)).fetchone()
            if r and r["comum"] > 0.01 * A and (georef is None or c.get("rotulo") == "SIGEF" and georef["fonte"] != "SIGEF"):
                georef = {"fonte": c.get("rotulo", c["nome"]), "codigo": r["codigo"], "area_ha": float(r["area"]),
                          "comum_ha": float(r["comum"]), "dif_pct": (float(r["area"]) - A) / A * 100 if A else None}
            sobreps.append({"camada": c["nome"], "slug": c["slug"], "n": 1 if r else 0, "ha": float(r["comum"]) if r else 0,
                            "nivel": "info", "exemplos": []})
        if georef and georef["fonte"] == "SIGEF":
            d = georef["dif_pct"] or 0
            flags.append(_flag("atencao" if abs(d) > 1 else "ok", "map", "Parcela SIGEF",
                               "Diferença de área entre SIGEF e CAR", f"{'+' if d > 0 else ''}{_fmt(d, 1)}%"))
            if abs(d) > 1:
                servicos.append("Ajuste do perímetro CAR × SIGEF")
        elif georef:
            flags.append(_flag("atencao", "map", f"Só certificação {georef['fonte']}",
                               "Certificação anterior ao SIGEF. Avaliar migração", f"{_fmt(georef['area_ha'], 0)} ha"))
            servicos.append("Georreferenciamento (SIGEF)")
        elif georef_carregado:
            flags.append(_flag("atencao", "map", "Sem georreferenciamento certificado",
                               "Nenhuma parcela SIGEF ou SNCI sobre o imóvel", "—"))
            servicos.append("Georreferenciamento (SIGEF)")

        # ---- outros CARs
        for c in config.camadas_por_papel("outro_car"):
            if not existe(c):
                continue
            campo = c.get("campo_codigo", "")
            rows = con.execute(f"""SELECT {_attr(campo)} AS codigo, {_ha('ST_Intersection(b.geom, i.geom)')} AS ha
                                   FROM {db.tabela_base(c['slug'])} b JOIN imoveis i ON ST_Intersects(b.geom, i.geom)
                                   WHERE i.car=%s""", (car,)).fetchall()
            outros = [r for r in rows if normalizar_car(r["codigo"] or "") != car and r["ha"] > 0.5]
            total = sum(r["ha"] for r in outros)
            sobreps.append({"camada": c["nome"], "slug": c["slug"], "n": len(outros), "ha": total,
                            "nivel": "atencao" if outros else "ok", "exemplos": [{"codigo": r["codigo"]} for r in outros[:5]]})
            if outros:
                flags.append(_flag("atencao", "users", f"Sobreposição com outro CAR ({c['nome']})",
                                   ", ".join(str(r["codigo"]) for r in outros[:3]), f"{_fmt(total)} ha"))
                servicos.append("Retificação do CAR")

        # ---- custeio (Sicor)
        custeio = []
        for c in config.camadas_por_papel("custeio"):
            if not existe(c):
                continue
            m = c.get("campos_custeio", {})
            pos_union = " UNION ALL ".join(geom_pos_sql) or "SELECT NULL::geometry AS geom WHERE false"
            emb_union = " UNION ALL ".join(geom_emb_sql) or "SELECT NULL::geometry AS geom WHERE false"
            rows = con.execute(f"""
                SELECT b.attrs, {_ha('ST_Intersection(b.geom, i.geom)')} AS ha,
                       EXISTS (SELECT 1 FROM ({pos_union}) p WHERE ST_Intersects(p.geom, b.geom)
                               AND ST_Intersects(p.geom, i.geom)) AS desmate,
                       EXISTS (SELECT 1 FROM ({emb_union}) e WHERE ST_Intersects(e.geom, b.geom)) AS embargo
                FROM {db.tabela_base(c['slug'])} b JOIN imoveis i ON ST_Intersects(b.geom, i.geom)
                WHERE i.car=%s""", (car,)).fetchall()
            for r in rows:
                a = r["attrs"] or {}
                pega = lambda k: _pegar(a, m.get(k, k.upper()))
                valor = pega("valor")
                try:
                    valor = float(str(valor).replace(",", ".")) if valor not in (None, "") else None
                except ValueError:
                    valor = None
                custeio.append({"ano": pega("ano"), "instituicao": pega("instituicao"),
                                "finalidade": pega("finalidade"), "cultura": pega("cultura"),
                                "valor": valor, "ha": float(r["ha"]), "desmate": r["desmate"], "embargo": r["embargo"]})
        ruins = [g for g in custeio if g["desmate"] or g["embargo"]]
        def _total(gs):
            v = sum(g["valor"] or 0 for g in gs)
            return f"R$ {_fmt(v, 0)}" if v else f"{len(gs)} gleba(s)"
        if ruins:
            flags.append(_flag("critico", "bank", "Custeio sobre área irregular",
                               f"{len(ruins)} gleba(s) do Sicor tocam desmate pós-2008 ou embargo", _total(ruins)))
            servicos.append("Regularização para manter o crédito")
        elif custeio:
            flags.append(_flag("ok", "bank", "Custeio registrado no Sicor",
                               f"{len(custeio)} gleba(s) sem conflito com desmate ou embargo", _total(custeio)))

        # ---- áreas protegidas e camadas informativas
        for c in config.camadas_por_papel("protegida") + config.camadas_por_papel("info"):
            if not existe(c):
                continue
            o = _sobreposicao(con, car, c["slug"])
            nivel = c.get("nivel", "info") if o["n"] else "ok"
            sobreps.append({"camada": c["nome"], "slug": c["slug"], "nivel": nivel, **o})
            if o["n"] and c.get("papel") == "protegida":
                flags.append(_flag(nivel, "shield", c["nome"], f"{o['n']} feição(ões) sobre o imóvel", f"{_fmt(o['ha'])} ha"))

        flags.sort(key=lambda f: ORDEM.get(f["nivel"], 3))
        uso = {"avn_ha": avn, "app_ha": app, "ac_declarada_ha": ac_decl, "desmate_pos_ha": pos}
        resultado = {
            "car": car, "calculado_em": datetime.now(timezone.utc).isoformat(),
            "imovel": {k: im[k] for k in ("nome", "municipio", "proprietario", "situacao", "origem")} | {"area_ha": A},
            "flags": flags, "servicos": list(dict.fromkeys(servicos)), "uso_solo": uso,
            "desmatamento": {"anos": prodes_anos, "pre_marco_ha": pre, "pos_marco_ha": pos, "ano_pos_marco": ano_pos},
            "embargos": embargos, "uso_consolidado": uc_info, "reserva_legal": rl, "georref": georef,
            "custeio": custeio, "sobreposicoes": sobreps,
            "bases_usadas": versoes, "bases_nao_carregadas": sorted(set(nao_carregadas)),
            "resumo": {"criticos": sum(f["nivel"] == "critico" for f in flags),
                       "atencao": sum(f["nivel"] == "atencao" for f in flags),
                       "icones": sorted({f["icone"] for f in flags if f["nivel"] != "ok"})},
        }
        for s in resultado["sobreposicoes"]:
            s["exemplos"] = s.get("exemplos", [])[:5]
        con.execute("UPDATE imoveis SET triagem=%s::jsonb, triagem_em=now() WHERE car=%s",
                    (json.dumps(resultado, default=str), car))
    return resultado
