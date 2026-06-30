"""
Rotas de autenticação. Cadastro livre restrito ao domínio
@cocodovale.com.br, login com sessão via cookie httponly, auditoria de
tentativas de login e redefinição de senha por token (sem SMTP configurado
ainda — o link de redefinição é gravado em backend/reset_pendentes.log
para o admin repassar manualmente até a TI liberar o envio de e-mail).
"""
import sqlite3
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Cookie, HTTPException, Request, Response
from pydantic import BaseModel, EmailStr

from app import auth_db

router = APIRouter(prefix="/api/auth", tags=["auth"])


def exigir_login(sessao: str | None = Cookie(default=None)) -> sqlite3.Row:
    """Dependency usada nas rotas de dados — exige sessão válida."""
    usuario = auth_db.usuario_da_sessao(sessao)
    if not usuario:
        raise HTTPException(status_code=401, detail="Não autenticado.")
    return usuario

COOKIE_NOME = "sessao"
RESET_LOG_PATH = Path(__file__).resolve().parent.parent.parent / "reset_pendentes.log"


class CadastroBody(BaseModel):
    email: EmailStr
    senha: str


class LoginBody(BaseModel):
    email: EmailStr
    senha: str


class EsqueciSenhaBody(BaseModel):
    email: EmailStr


class RedefinirSenhaBody(BaseModel):
    token: str
    nova_senha: str


@router.post("/registrar")
def registrar(body: CadastroBody):
    if not auth_db.email_valido_dominio(body.email):
        raise HTTPException(status_code=400, detail=f"Só e-mails {auth_db.DOMINIO_PERMITIDO} podem se cadastrar.")
    if not (8 <= len(body.senha) <= 72):
        raise HTTPException(status_code=400, detail="A senha precisa ter entre 8 e 72 caracteres.")
    if auth_db.buscar_usuario_por_email(body.email):
        raise HTTPException(status_code=409, detail="Já existe uma conta com esse e-mail.")
    auth_db.criar_usuario(body.email, body.senha)
    return {"status": "ok"}


@router.post("/login")
def login(body: LoginBody, response: Response):
    usuario = auth_db.buscar_usuario_por_email(body.email)
    if not usuario or not auth_db.verificar_senha(usuario, body.senha):
        auth_db.registrar_login_audit(body.email, sucesso=False)
        raise HTTPException(status_code=401, detail="E-mail ou senha incorretos.")

    auth_db.registrar_login_audit(body.email, sucesso=True)
    token = auth_db.criar_sessao(usuario["id"])
    response.set_cookie(
        key=COOKIE_NOME,
        value=token,
        httponly=True,
        samesite="lax",
        secure=False,  # backend roda em HTTP na rede interna, não HTTPS
        max_age=auth_db.SESSAO_DIAS * 24 * 3600,
        path="/",
    )
    return {"email": usuario["email"]}


@router.post("/logout")
def logout(response: Response, sessao: str | None = Cookie(default=None)):
    if sessao:
        auth_db.encerrar_sessao(sessao)
    response.delete_cookie(COOKIE_NOME, path="/")
    return {"status": "ok"}


@router.get("/me")
def me(sessao: str | None = Cookie(default=None)):
    usuario = auth_db.usuario_da_sessao(sessao)
    if not usuario:
        raise HTTPException(status_code=401, detail="Não autenticado.")
    return {"email": usuario["email"]}


@router.post("/esqueci-senha")
def esqueci_senha(body: EsqueciSenhaBody, request: Request):
    usuario = auth_db.buscar_usuario_por_email(body.email)
    # Resposta genérica sempre — não revela se o e-mail existe ou não.
    if usuario:
        token = auth_db.criar_reset_token(usuario["id"])
        base_url = str(request.base_url).rstrip("/")
        link = f"{base_url}/redefinir-senha.html?token={token}"
        linha = f"{datetime.now().isoformat(timespec='seconds')} | {usuario['email']} | {link}\n"
        with open(RESET_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(linha)
        print(f"[RESET DE SENHA] {linha.strip()}")
    return {"status": "ok", "mensagem": "Se o e-mail existir, um link de redefinição foi gerado. Peça para o administrador te repassar."}


@router.post("/redefinir-senha")
def redefinir_senha(body: RedefinirSenhaBody):
    if not (8 <= len(body.nova_senha) <= 72):
        raise HTTPException(status_code=400, detail="A senha precisa ter entre 8 e 72 caracteres.")
    usuario = auth_db.consumir_reset_token(body.token)
    if not usuario:
        raise HTTPException(status_code=400, detail="Link inválido ou expirado. Peça um novo.")
    auth_db.atualizar_senha(usuario["id"], body.nova_senha)
    return {"status": "ok"}
