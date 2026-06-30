from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import previsao

app = FastAPI(title=settings.api_title, debug=settings.debug)

# CORS: necessário porque o frontend (Vercel) e o backend (servidor da
# empresa) ficam em domínios diferentes.
#
# Em DESENVOLVIMENTO local, liberamos qualquer origem (allow_origins=["*"])
# para eliminar problemas de configuração enquanto você testa.
# Em PRODUÇÃO, troque para allow_origins=[settings.frontend_origin] com o
# domínio real do Vercel, por segurança.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.debug else [settings.frontend_origin],
    allow_credentials=False,  # precisa ser False quando allow_origins=["*"]
    allow_methods=["GET"],
    allow_headers=["*"],
)

app.include_router(previsao.router)


@app.get("/")
def root():
    return {"app": settings.api_title, "status": "online"}
