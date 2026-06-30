from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app import auth_db
from app.config import settings
from app.routers import previsao
from app.routers import auth as auth_router

app = FastAPI(title=settings.api_title, debug=settings.debug)


@app.on_event("startup")
def _criar_tabelas_auth():
    auth_db.init_db()


# CORS: só é necessário quando o frontend é servido de outra origem (ex:
# Vercel). Quando o próprio backend serve o frontend (mesma origem), o
# navegador nem aplica a checagem de CORS — mas deixamos liberado para não
# quebrar caso alguém acesse via outro domínio/túnel.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.debug else [settings.frontend_origin],
    allow_credentials=not settings.debug,  # só funciona com cookie quando a origem não é "*"
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(auth_router.router)
app.include_router(previsao.router)


@app.get("/api/health")
def health_check():
    """Não exige login — usado para monitoramento."""
    return {"status": "ok"}


# Serve o frontend estático (frontend/index.html) na mesma origem do
# backend — assim qualquer máquina da rede acessa tudo por um único
# endereço (http://servidor:8000/), sem CORS e sem depender de "localhost".
FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "frontend"
app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
