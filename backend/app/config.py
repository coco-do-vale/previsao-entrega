"""
Configurações centralizadas via variáveis de ambiente (.env).
Nunca commitar credenciais reais no Git — sempre usar .env (já no .gitignore).
"""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # --- SQL Server ---
    db_server: str = "localhost"
    db_database: str = "ControladoriaNotas"
    db_use_windows_auth: bool = True
    db_user: str = ""
    db_password: str = ""
    db_driver: str = "ODBC Driver 18 for SQL Server"

    # --- Nome real da tabela principal (ajustar após discover_schema.py) ---
    tabela_fato: str = "TFato Geral2"
    tabela_leadtime: str = "Leadtime"

    # --- CORS: domínio do frontend no Vercel ---
    frontend_origin: str = "http://localhost:5173"

    # --- App ---
    api_title: str = "API Previsão de Entregas"
    debug: bool = False

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
