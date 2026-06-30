"""
CHECK_CONNECTION.PY
====================
Teste de conexão MÍNIMO, isolado de tudo (sem FastAPI, sem pandas).
Só pyodbc puro + dotenv. Se este script falhar, o problema é 100%
de conexão/autenticação — não tem nenhuma outra camada do projeto
no caminho que possa estar interferindo.

Rode de dentro da pasta backend/:
    python check_connection.py
"""
import os
import pyodbc
from dotenv import load_dotenv

load_dotenv()

server = os.getenv("DB_SERVER", "")
database = os.getenv("DB_DATABASE", "")
user = os.getenv("DB_USER", "")
password = os.getenv("DB_PASSWORD", "")
driver = os.getenv("DB_DRIVER", "ODBC Driver 18 for SQL Server")

print(f"Tentando conectar:")
print(f"  Server:   {server}")
print(f"  Database: {database}")
print(f"  User:     {user}")
print(f"  Driver:   {driver}")
print()

conn_str = (
    f"DRIVER={{{driver}}};"
    f"SERVER={server};"
    f"DATABASE={database};"
    f"UID={user};"
    f"PWD={password};"
    f"TrustServerCertificate=yes;"
    f"Encrypt=yes;"
)

try:
    conn = pyodbc.connect(conn_str, timeout=15)
    print("✓✓✓ CONEXÃO BEM-SUCEDIDA! ✓✓✓")
    cursor = conn.cursor()
    cursor.execute("SELECT @@VERSION")
    print(cursor.fetchone()[0])
    conn.close()
except pyodbc.Error as e:
    print("✗✗✗ FALHA NA CONEXÃO ✗✗✗")
    print(e)
    print()
    print("Se a mesma senha funciona no SSMS/DBeaver mas falha aqui, tente:")
    print("  1. Confirmar se há espaços/aspas acidentais na senha do .env")
    print("  2. Tentar SEM 'Encrypt=yes' (algumas configurações de servidor exigem isso desligado)")
    print("  3. Confirmar se o usuário precisa de TrustServerCertificate=no")
    print("  4. Verificar se a conta SQL não está com 'must change password' marcado")
