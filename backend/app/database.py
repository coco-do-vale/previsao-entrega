"""
Camada de acesso a dados (SQL Server via pyodbc).

IMPORTANTE: esta API deve rodar DENTRO da rede da empresa (ou em uma
máquina com acesso de rede ao SQL Server — VPN, mesma LAN, etc).
O Vercel NÃO consegue alcançar um SQL Server em rede interna; por isso
o frontend (Vercel) chama esta API por HTTPS, e é esta API que fala
diretamente com o banco.
"""
import pyodbc
import pandas as pd
from contextlib import contextmanager
from app.config import settings


def _build_connection_string() -> str:
    if settings.db_use_windows_auth:
        return (
            f"DRIVER={{{settings.db_driver}}};"
            f"SERVER={settings.db_server};"
            f"DATABASE={settings.db_database};"
            f"Trusted_Connection=yes;"
            f"TrustServerCertificate=yes;"
        )
    return (
        f"DRIVER={{{settings.db_driver}}};"
        f"SERVER={settings.db_server};"
        f"DATABASE={settings.db_database};"
        f"UID={settings.db_user};"
        f"PWD={settings.db_password};"
        f"TrustServerCertificate=yes;"
    )


@contextmanager
def get_connection():
    """Context manager simples. Para alta concorrência, trocar por um pool
    de conexões real (ex: sqlalchemy + pyodbc, ou pyodbc_pool)."""
    conn = pyodbc.connect(_build_connection_string(), timeout=15)
    try:
        yield conn
    finally:
        conn.close()


def query_df(sql: str, params: tuple = ()) -> pd.DataFrame:
    """Executa uma query e retorna um DataFrame pandas — equivalente a
    'puxar a tabela para dentro do contexto de cálculo', como o DAX faz
    implicitamente com a tabela do modelo."""
    with get_connection() as conn:
        return pd.read_sql(sql, conn, params=params)
