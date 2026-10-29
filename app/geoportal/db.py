"""Acesso ao PostGIS."""
import re
from contextlib import contextmanager

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from . import config

_pool: ConnectionPool | None = None
SLUG_OK = re.compile(r"^[a-z][a-z0-9_]{1,40}$")


def pool() -> ConnectionPool:
    global _pool
    if _pool is None:
        _pool = ConnectionPool(config.DATABASE_URL, min_size=1, max_size=8,
                               kwargs={"row_factory": dict_row}, open=True)
    return _pool


@contextmanager
def conexao():
    with pool().connection() as con:
        yield con


def fechar():
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None


def tabela_base(slug: str) -> str:
    """Nome qualificado e seguro da tabela de uma base de referência."""
    if not SLUG_OK.match(slug):
        raise ValueError(f"Nome de camada inválido: {slug!r}")
    return f'bases."{slug}"'


def base_existe(con, slug: str) -> bool:
    r = con.execute("SELECT to_regclass(%s) AS t", (f"bases.{slug}",)).fetchone()
    return r["t"] is not None


def migrar():
    sql = (config.AQUI / "schema.sql").read_text(encoding="utf-8")
    with psycopg.connect(config.DATABASE_URL, autocommit=True) as con:
        con.execute(sql)
