"""
CHECK_ENV.PY
============
Diagnóstico rápido: confirma que o .env está sendo encontrado e lido
corretamente, SEM expor a senha completa no terminal (só tamanho e
primeiro/último caractere, para detectar espaços/aspas acidentais).

Rode de dentro da pasta backend/:
    python check_env.py
"""
import os
from pathlib import Path
from dotenv import load_dotenv

env_path = Path(".env")
print("=" * 60)
print("DIAGNÓSTICO DO ARQUIVO .env")
print("=" * 60)
print(f"Procurando .env em: {env_path.resolve()}")
print(f"Arquivo existe? {env_path.exists()}")
print()

if not env_path.exists():
    print("✗ O arquivo .env NÃO foi encontrado nesta pasta.")
    print("  Rode este script de dentro da pasta 'backend/'.")
    exit(1)

load_dotenv(env_path)

server = os.getenv("DB_SERVER", "")
database = os.getenv("DB_DATABASE", "")
use_windows_auth = os.getenv("DB_USE_WINDOWS_AUTH", "")
user = os.getenv("DB_USER", "")
password = os.getenv("DB_PASSWORD", "")
driver = os.getenv("DB_DRIVER", "")


def mascarar(valor: str) -> str:
    if not valor:
        return "(VAZIO)"
    if len(valor) <= 4:
        return f"'{valor[0]}***' (tamanho={len(valor)})"
    return f"'{valor[0]}***{valor[-1]}' (tamanho={len(valor)})"


print(f"DB_SERVER            = '{server}'")
print(f"DB_DATABASE           = '{database}'")
print(f"DB_USE_WINDOWS_AUTH    = '{use_windows_auth}'")
print(f"DB_USER                 = '{user}'")
print(f"DB_PASSWORD              = {mascarar(password)}")
print(f"DB_DRIVER                 = '{driver}'")
print()

# Alertas de problemas comuns
alertas = []
if password != password.strip():
    alertas.append("⚠️  A senha tem espaços no início/fim — isso quebra o login!")
if password.startswith('"') or password.startswith("'"):
    alertas.append("⚠️  A senha começa com aspas — provavelmente as aspas foram incluídas como parte do valor!")
if "#" in password:
    alertas.append("⚠️  A senha contém '#' — em alguns casos isso é tratado como início de comentário no .env!")
if user != user.strip():
    alertas.append("⚠️  O usuário tem espaços no início/fim!")
if not server or "," not in server and ":" not in server:
    alertas.append("ℹ️  DB_SERVER não tem porta explícita (formato esperado: IP,PORTA) — confirme se a porta padrão 1433 está correta para seu caso.")

if alertas:
    print("PROBLEMAS DETECTADOS:")
    for a in alertas:
        print(f"  {a}")
else:
    print("✓ Nenhum problema óbvio detectado na formatação dos valores.")

print()
print("=" * 60)
print("Se a senha realmente bate com o que você usa no SSMS/DBeaver,")
print("e nenhum alerta apareceu acima, o próximo passo é testar a")
print("conexão com um comando ODBC mínimo (ver check_connection.py).")
print("=" * 60)
