"""Login da equipe: senha com bcrypt e sessão em cookie assinado (JWT, httpOnly)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, HTTPException, Request

from . import config, db

COOKIE = "gp_sessao"


def hash_senha(senha: str) -> str:
    if len(senha) < 10:
        raise ValueError("A senha precisa ter pelo menos 10 caracteres.")
    return bcrypt.hashpw(senha.encode(), bcrypt.gensalt(12)).decode()


def confere(senha: str, h: str) -> bool:
    try:
        return bcrypt.checkpw(senha.encode(), h.encode())
    except ValueError:
        return False


def criar_usuario(email: str, nome: str, senha: str, perfil: str = "analista"):
    with db.conexao() as con:
        con.execute("""INSERT INTO usuarios(email, nome, senha_hash, perfil) VALUES (lower(%s),%s,%s,%s)
                       ON CONFLICT (email) DO UPDATE SET nome=EXCLUDED.nome, senha_hash=EXCLUDED.senha_hash,
                       perfil=EXCLUDED.perfil, ativo=true""", (email, nome, hash_senha(senha), perfil))


def autenticar(email: str, senha: str) -> dict | None:
    with db.conexao() as con:
        u = con.execute("SELECT id, email, nome, perfil, senha_hash FROM usuarios WHERE email=lower(%s) AND ativo",
                        (email,)).fetchone()
    if not u or not confere(senha, u["senha_hash"]):
        return None
    return {k: u[k] for k in ("id", "email", "nome", "perfil")}


def emitir_token(u: dict) -> str:
    agora = datetime.now(timezone.utc)
    return jwt.encode({"sub": u["email"], "nome": u["nome"], "perfil": u["perfil"],
                       "iat": agora, "exp": agora + timedelta(hours=config.SESSAO_HORAS)},
                      config.segredo_jwt(), algorithm="HS256")


def usuario_atual(request: Request) -> dict:
    tok = request.cookies.get(COOKIE)
    if not tok:
        raise HTTPException(401, "Faça login para continuar.")
    try:
        d = jwt.decode(tok, config.segredo_jwt(), algorithms=["HS256"])
    except jwt.PyJWTError:
        raise HTTPException(401, "Sessão expirada. Faça login de novo.")
    return {"email": d["sub"], "nome": d["nome"], "perfil": d["perfil"]}


def so_admin(u: dict = Depends(usuario_atual)) -> dict:
    if u["perfil"] != "admin":
        raise HTTPException(403, "Só o administrador pode fazer isso.")
    return u
