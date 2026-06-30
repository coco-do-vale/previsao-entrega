from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.routers import previsao

app = FastAPI(title=settings.api_title, debug=settings.debug)

# CORS: só é necessário quando o frontend é servido de outra origem (ex:
# Vercel). Quando o próprio backend serve o frontend (mesma origem), o
# navegador nem aplica a checagem de CORS — mas deixamos liberado para não
# quebrar caso alguém acesse via outro domínio/túnel.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.debug else [settings.frontend_origin],
    allow_credentials=False,  # precisa ser False quando allow_origins=["*"]
    allow_methods=["GET"],
    allow_headers=["*"],
)

app.include_router(previsao.router)

# Serve o frontend estático (frontend/index.html) na mesma origem do
# backend — assim qualquer máquina da rede acessa tudo por um único
# endereço (http://servidor:8000/), sem CORS e sem depender de "localhost".
FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "frontend"
app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
