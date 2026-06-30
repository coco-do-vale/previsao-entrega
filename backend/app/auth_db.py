"""
Banco local (SQLite) para login — completamente separado do SQL Server da
empresa. Guarda só usuários, sessões, tentativas de login (auditoria) e
tokens de redefinição de senha. Nunca guarda senha em texto puro: só hash
bcrypt (via passlib).
"""
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

import bcrypt

DB_PATH = Path(__file__).resolve().parent.parent / "auth.db"
DOMINIO_PERMITIDO = "@cocodovale.com.br"
SESSAO_DIAS = 7
RESET_TOKEN_HORAS = 1


def _hash_senha(senha: str) -> str:
    return bcrypt.hashpw(senha.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _checar_senha(senha: str, hash_: str) -> bool:
    return bcrypt.checkpw(senha.encode("utf-8"), hash_.encode("utf-8"))


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS usuarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                senha_hash TEXT NOT NULL,
                criado_em TEXT NOT NULL,
                ativo INTEGER NOT NULL DEFAULT 1
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sessoes (
                token TEXT PRIMARY KEY,
                usuario_id INTEGER NOT NULL,
                criado_em TEXT NOT NULL,
                expira_em TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS login_audit (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL,
                sucesso INTEGER NOT NULL,
                criado_em TEXT NOT NULL,
                detalhe TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS reset_tokens (
                token TEXT PRIMARY KEY,
                usuario_id INTEGER NOT NULL,
                criado_em TEXT NOT NULL,
                expira_em TEXT NOT NULL,
                usado INTEGER NOT NULL DEFAULT 0
            )
        """)


def _agora() -> str:
    return datetime.now(timezone.utc).isoformat()


def email_valido_dominio(email: str) -> bool:
    return email.strip().lower().endswith(DOMINIO_PERMITIDO)


def criar_usuario(email: str, senha: str):
    email = email.strip().lower()
    senha_hash = _hash_senha(senha)
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO usuarios (email, senha_hash, criado_em) VALUES (?, ?, ?)",
            (email, senha_hash, _agora()),
        )


def buscar_usuario_por_email(email: str) -> sqlite3.Row | None:
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM usuarios WHERE email = ? AND ativo = 1", (email.strip().lower(),)
        ).fetchone()


def verificar_senha(usuario: sqlite3.Row, senha: str) -> bool:
    return _checar_senha(senha, usuario["senha_hash"])


def registrar_login_audit(email: str, sucesso: bool, detalhe: str = ""):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO login_audit (email, sucesso, criado_em, detalhe) VALUES (?, ?, ?, ?)",
            (email.strip().lower(), 1 if sucesso else 0, _agora(), detalhe),
        )


def criar_sessao(usuario_id: int) -> str:
    token = secrets.token_urlsafe(32)
    expira = (datetime.now(timezone.utc) + timedelta(days=SESSAO_DIAS)).isoformat()
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO sessoes (token, usuario_id, criado_em, expira_em) VALUES (?, ?, ?, ?)",
            (token, usuario_id, _agora(), expira),
        )
    return token


def usuario_da_sessao(token: str) -> sqlite3.Row | None:
    if not token:
        return None
    with get_conn() as conn:
        sessao = conn.execute("SELECT * FROM sessoes WHERE token = ?", (token,)).fetchone()
        if not sessao:
            return None
        if sessao["expira_em"] < _agora():
            conn.execute("DELETE FROM sessoes WHERE token = ?", (token,))
            return None
        return conn.execute(
            "SELECT * FROM usuarios WHERE id = ? AND ativo = 1", (sessao["usuario_id"],)
        ).fetchone()


def encerrar_sessao(token: str):
    with get_conn() as conn:
        conn.execute("DELETE FROM sessoes WHERE token = ?", (token,))


def criar_reset_token(usuario_id: int) -> str:
    token = secrets.token_urlsafe(32)
    expira = (datetime.now(timezone.utc) + timedelta(hours=RESET_TOKEN_HORAS)).isoformat()
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO reset_tokens (token, usuario_id, criado_em, expira_em) VALUES (?, ?, ?, ?)",
            (token, usuario_id, _agora(), expira),
        )
    return token


def consumir_reset_token(token: str) -> sqlite3.Row | None:
    """Retorna o usuário dono do token se ele for válido e não usado, e já
    marca como usado (token de uso único)."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM reset_tokens WHERE token = ? AND usado = 0", (token,)
        ).fetchone()
        if not row or row["expira_em"] < _agora():
            return None
        conn.execute("UPDATE reset_tokens SET usado = 1 WHERE token = ?", (token,))
        usuario = conn.execute("SELECT * FROM usuarios WHERE id = ?", (row["usuario_id"],)).fetchone()
        return usuario


def atualizar_senha(usuario_id: int, nova_senha: str):
    senha_hash = _hash_senha(nova_senha)
    with get_conn() as conn:
        conn.execute("UPDATE usuarios SET senha_hash = ? WHERE id = ?", (senha_hash, usuario_id))
        # Derruba todas as sessões ativas desse usuário ao trocar a senha.
        conn.execute("DELETE FROM sessoes WHERE usuario_id = ?", (usuario_id,))
