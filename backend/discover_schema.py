"""
DISCOVER_SCHEMA.PY
==================
Script standalone de diagnóstico. Rode ISOLADO, dentro da rede da empresa,
ANTES de qualquer outra coisa do projeto. Ele não depende do FastAPI nem
de mais nada — só de pyodbc e python-dotenv.

Objetivo: descobrir o nome real da tabela e das colunas no SQL Server,
para alinhar com os nomes que hoje existem na medida DAX
(TFato Geral2, ROMANEIO, DT_ENTREGA_REDESPACHO, etc).

USO:
    1. pip install pyodbc python-dotenv
    2. Copie .env.example para .env e preencha com os dados reais
       (DB_SERVER aceita o formato "IP,PORTA", ex: 181.41.170.237,1319)
    3. python discover_schema.py
    4. Copie a SAÍDA COMPLETA do terminal e me envie — com isso eu ajusto
       o restante do projeto (queries, modelos Pydantic, etc.) para bater
       exatamente com sua estrutura real.
"""

import os
import sys
import pyodbc
from dotenv import load_dotenv

load_dotenv()  # lê o arquivo .env na mesma pasta

# ============================================================
# CONFIGURAÇÃO — lida automaticamente do .env (não edite valores aqui)
# ============================================================
SERVER = os.getenv("DB_SERVER", "")          # aceita "IP,PORTA" ex: 181.41.170.237,1319
DATABASE = os.getenv("DB_DATABASE", "")
USE_WINDOWS_AUTH = os.getenv("DB_USE_WINDOWS_AUTH", "false").strip().lower() == "true"
USER = os.getenv("DB_USER", "")
PASSWORD = os.getenv("DB_PASSWORD", "")
DRIVER_PREFERIDO = os.getenv("DB_DRIVER", "")

if not SERVER or not DATABASE:
    print("✗ DB_SERVER ou DB_DATABASE não encontrados.")
    print("  Verifique se o arquivo .env existe nesta pasta (backend/) e está preenchido.")
    print("  Copie .env.example para .env se ainda não fez isso.")
    sys.exit(1)

# Nomes candidatos a tabela principal — ajuste se já souber o nome real.
# O script vai testar e também listar TODAS as tabelas do banco para você escolher.
CANDIDATOS_TABELA = ["TFato Geral2", "TFatoGeral2", "Fato_Geral2", "TFATO_GERAL2"]

# Colunas que a lógica DAX espera encontrar — usadas para o "diff" de schema
COLUNAS_ESPERADAS = [
    "NF", "CLIENTE", "CIDADE_CLIENTE", "UF_CLIENTE", "TIPO_FLUXO",
    "TRANSP_PRINCIPAL", "ROMANEIO", "LEAD_TIME_DIRETA", "LEAD_TIME_REDESPACHO",
    "LEAD_TIME_TOTAL", "DT_ENTREGA_REDESPACHO", "DT_PREVISTA_REDESPACHO",
    "TRANSP_REDESPACHO", "STATUS_OTD_REDESPACHO", "STATUS_OTD_TOTAL",
    "VALOR_NF", "DT_PREVISTA_CLIENTE_FINAL", "DT_ENTREGA_CLIENTE",
    "QTD Sem Lead Time",
]
# ============================================================


def get_connection_string():
    driver_candidates = [
        DRIVER_PREFERIDO,
        "ODBC Driver 18 for SQL Server",
        "ODBC Driver 17 for SQL Server",
        "SQL Server Native Client 11.0",
        "SQL Server",
    ]
    driver_candidates = [d for d in driver_candidates if d]  # remove vazios
    available = pyodbc.drivers()
    installed = [d for d in driver_candidates if d in available]
    if not installed:
        print("⚠️  Nenhum driver ODBC conhecido encontrado. Drivers instalados:")
        for d in available:
            print(f"   - {d}")
        sys.exit(1)

    driver = installed[0]
    print(f"✓ Usando driver: {driver}\n")

    if USE_WINDOWS_AUTH:
        return (
            f"DRIVER={{{driver}}};SERVER={SERVER};DATABASE={DATABASE};"
            f"Trusted_Connection=yes;TrustServerCertificate=yes;"
        )
    else:
        return (
            f"DRIVER={{{driver}}};SERVER={SERVER};DATABASE={DATABASE};"
            f"UID={USER};PWD={PASSWORD};TrustServerCertificate=yes;"
        )


def main():
    print("=" * 70)
    print("DIAGNÓSTICO DE SCHEMA — SQL Server")
    print("=" * 70)
    print(f"Server:   {SERVER}")
    print(f"Database: {DATABASE}")
    print(f"Auth:     {'Windows' if USE_WINDOWS_AUTH else f'SQL Login (usuário: {USER})'}")
    print()

    conn_str = get_connection_string()

    try:
        conn = pyodbc.connect(conn_str, timeout=10)
        print(f"✓ Conectado a {SERVER}/{DATABASE}\n")
    except pyodbc.Error as e:
        print(f"✗ FALHA DE CONEXÃO: {e}\n")
        print("Possíveis causas:")
        print("  - Servidor/banco incorretos")
        print("  - Sem acesso de rede (VPN/firewall) a partir desta máquina")
        print("  - Credenciais inválidas (se USE_WINDOWS_AUTH=False)")
        sys.exit(1)

    cursor = conn.cursor()

    # 1) Listar TODAS as tabelas do banco
    print("-" * 70)
    print("1) TABELAS DISPONÍVEIS NO BANCO")
    print("-" * 70)
    cursor.execute("""
        SELECT TABLE_SCHEMA, TABLE_NAME
        FROM INFORMATION_SCHEMA.TABLES
        WHERE TABLE_TYPE = 'BASE TABLE'
        ORDER BY TABLE_SCHEMA, TABLE_NAME
    """)
    tabelas = cursor.fetchall()
    for schema, nome in tabelas:
        marcador = " <-- candidata" if nome in CANDIDATOS_TABELA else ""
        print(f"  {schema}.{nome}{marcador}")
    print(f"\nTotal: {len(tabelas)} tabelas\n")

    # 2) Tentar localizar a tabela principal
    print("-" * 70)
    print("2) LOCALIZANDO TABELA PRINCIPAL")
    print("-" * 70)
    tabela_encontrada = None
    schema_encontrado = None
    for schema, nome in tabelas:
        if nome in CANDIDATOS_TABELA or nome.upper().replace("_", "").replace(" ", "") in [
            c.upper().replace("_", "").replace(" ", "") for c in CANDIDATOS_TABELA
        ]:
            tabela_encontrada = nome
            schema_encontrado = schema
            print(f"✓ Encontrada: {schema}.{nome}")
            break

    if not tabela_encontrada:
        print("✗ Nenhuma tabela candidata encontrada automaticamente.")
        print("  Revise a lista acima e ajuste CANDIDATOS_TABELA no script,")
        print("  ou me informe manualmente o nome correto.\n")
        cursor.close()
        conn.close()
        return

    # 3) Colunas da tabela encontrada
    print("\n" + "-" * 70)
    print(f"3) COLUNAS DE {schema_encontrado}.{tabela_encontrada}")
    print("-" * 70)
    cursor.execute("""
        SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE, CHARACTER_MAXIMUM_LENGTH
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = ? AND TABLE_NAME = ?
        ORDER BY ORDINAL_POSITION
    """, schema_encontrado, tabela_encontrada)
    colunas = cursor.fetchall()
    colunas_reais = [c[0] for c in colunas]

    for nome_col, tipo, nullable, max_len in colunas:
        tam = f"({max_len})" if max_len else ""
        print(f"  {nome_col:35s} {tipo}{tam:10s} {'NULL' if nullable=='YES' else 'NOT NULL'}")

    # 4) DIFF: o que a lógica DAX espera vs. o que existe
    print("\n" + "-" * 70)
    print("4) COMPARAÇÃO COM CAMPOS ESPERADOS PELA LÓGICA DAX")
    print("-" * 70)
    colunas_reais_upper = {c.upper(): c for c in colunas_reais}
    faltando = []
    encontradas = []
    for esperada in COLUNAS_ESPERADAS:
        if esperada.upper() in colunas_reais_upper:
            encontradas.append((esperada, colunas_reais_upper[esperada.upper()]))
        else:
            faltando.append(esperada)

    print(f"\n✓ ENCONTRADAS ({len(encontradas)}/{len(COLUNAS_ESPERADAS)}):")
    for esperada, real in encontradas:
        marca = "" if esperada == real else f"  [nome real diverge: '{real}']"
        print(f"   {esperada}{marca}")

    if faltando:
        print(f"\n✗ NÃO ENCONTRADAS ({len(faltando)}):")
        for f in faltando:
            print(f"   {f}")
        print("\n  >> Essas colunas precisam ser localizadas manualmente")
        print("     (podem ter outro nome, estar em outra tabela, ou ser")
        print("     calculadas/derivadas no Power Query/DAX e não existir")
        print("     fisicamente no banco).")

    # 5) Amostra de dados (3 linhas) para verificar formato
    print("\n" + "-" * 70)
    print("5) AMOSTRA DE DADOS (3 primeiras linhas)")
    print("-" * 70)
    try:
        cursor.execute(f"SELECT TOP 3 * FROM [{schema_encontrado}].[{tabela_encontrada}]")
        rows = cursor.fetchall()
        col_names = [c[0] for c in cursor.description]
        print("Colunas:", ", ".join(col_names))
        print()
        for row in rows:
            print(dict(zip(col_names, row)))
            print()
    except pyodbc.Error as e:
        print(f"✗ Erro ao buscar amostra: {e}")

    cursor.close()
    conn.close()

    print("=" * 70)
    print("FIM DO DIAGNÓSTICO — copie toda a saída acima e envie de volta")
    print("=" * 70)


if __name__ == "__main__":
    main()
