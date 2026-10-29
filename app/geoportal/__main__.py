"""Comandos de administração do Geoportal Bioma.

  python -m geoportal migrar
  python -m geoportal criar-usuario EMAIL "NOME" [--admin]
  python -m geoportal importar-base SLUG ARQUIVO [--encoding latin1] [--srid 4674]
  python -m geoportal importar-pasta PASTA            (importa todo arquivo cujo nome começa pelo slug)
  python -m geoportal importar-car ARQUIVO [--car MT000000/2020] [--carteira]
  python -m geoportal importar-mf ARQUIVO.csv
  python -m geoportal bases
  python -m geoportal retriar                          (recalcula a triagem de todos os imóveis)
"""
import argparse
import getpass
import pathlib

from . import auth, config, db, importar, triagem


def main(argv=None):
    p = argparse.ArgumentParser(prog="geoportal", description="Administração do Geoportal Bioma")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("migrar")
    a = sub.add_parser("criar-usuario"); a.add_argument("email"); a.add_argument("nome"); a.add_argument("--admin", action="store_true")
    a.add_argument("--senha", help="(evite: prefira digitar quando pedido)")
    a = sub.add_parser("importar-base"); a.add_argument("slug"); a.add_argument("arquivo")
    a.add_argument("--encoding"); a.add_argument("--srid", type=int)
    a = sub.add_parser("importar-pasta"); a.add_argument("pasta"); a.add_argument("--encoding"); a.add_argument("--srid", type=int)
    a = sub.add_parser("importar-car"); a.add_argument("arquivo"); a.add_argument("--car")
    a.add_argument("--carteira", action="store_true", help="marca como Carteira Bioma (padrão: Prospecção)")
    a = sub.add_parser("importar-mf"); a.add_argument("arquivo")
    sub.add_parser("bases")
    sub.add_parser("retriar")
    args = p.parse_args(argv)

    if args.cmd == "migrar":
        db.migrar(); print("Banco pronto.")
    elif args.cmd == "criar-usuario":
        senha = args.senha or getpass.getpass("Senha (mín. 10 caracteres): ")
        auth.criar_usuario(args.email, args.nome, senha, "admin" if args.admin else "analista")
        print(f"Usuário {args.email} salvo.")
    elif args.cmd == "importar-base":
        importar.importar_base(args.slug, args.arquivo, args.encoding, args.srid)
    elif args.cmd == "importar-pasta":
        slugs = sorted((c["slug"] for c in config.catalogo()["camadas"]), key=len, reverse=True)
        pasta = pathlib.Path(args.pasta)
        grupos: dict[str, list] = {}
        for arq in sorted(pasta.iterdir()):
            if arq.suffix.lower() not in (".zip",) + importar.EXT_VETOR:
                continue
            slug = next((s for s in slugs if arq.stem.lower().startswith(s)), None)
            if not slug:
                print(f"  ignorado (nome não começa por um slug do camadas.yaml): {arq.name}")
                continue
            grupos.setdefault(slug, []).append(arq)
        for slug, arqs in grupos.items():
            try:
                importar.importar_base(slug, arqs, args.encoding, args.srid, log=lambda m: None)
                print(f"  {slug}: ok ({', '.join(a.name for a in arqs)})")
            except Exception as e:
                print(f"  {slug}: ERRO — {e}")
    elif args.cmd == "importar-car":
        r = importar.importar_car(args.arquivo, car=args.car,
                                  dados={"origem": "Carteira Bioma" if args.carteira else None})
        triagem.calcular(r["car"])
        print(f"{r['car']} importado ({float(r['area_ha']):.2f} ha) e triado.")
    elif args.cmd == "importar-mf":
        print(f"{importar.importar_modulo_fiscal(args.arquivo)} municípios importados.")
    elif args.cmd == "bases":
        with db.conexao() as con:
            cat = {r["slug"]: r for r in con.execute("SELECT * FROM bases.catalogo").fetchall()}
        for c in config.catalogo()["camadas"]:
            r = cat.get(c["slug"])
            st = f"{r['feicoes']:>8} feições  {r['versao_em']:%d/%m/%Y}  {r['arquivo']}" if r else "   — não importada"
            print(f"{c['slug']:<22} {st}")
    elif args.cmd == "retriar":
        with db.conexao() as con:
            cars = [r["car"] for r in con.execute("SELECT car FROM imoveis").fetchall()]
        for car in cars:
            triagem.calcular(car)
        print(f"{len(cars)} imóveis triados.")


if __name__ == "__main__":
    try:
        main()
    finally:
        db.fechar()
