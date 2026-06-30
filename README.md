# Previsão de Entregas — Migração DAX → Python + Web

Projeto que substitui a medida DAX `HTML_Previsao_Entregas_v5` do Power BI
por uma aplicação web (FastAPI + HTML/JS), lendo direto do SQL Server.

## Arquitetura

```
Vercel (frontend estático)  --HTTPS-->  FastAPI (servidor da empresa)  --pyodbc-->  SQL Server
```

O backend **precisa rodar dentro da rede da empresa** (ou com VPN/túnel
de acesso ao SQL Server). O Vercel hospeda só o HTML/JS estático e
nunca toca o banco diretamente.

## Passo 1 — Descobrir o schema real (FAZER PRIMEIRO)

Antes de qualquer outra coisa, dentro da rede da empresa:

```bash
cd backend
pip install pyodbc python-dotenv
cp .env.example .env
# edite o .env com os dados reais (server, porta, database, usuário, senha)
python discover_schema.py
```

O `DB_SERVER` aceita o formato `IP,PORTA` quando a porta não é a padrão
(ex: `181.41.170.237,1319`). Se o banco usa login de SQL (usuário/senha,
não Windows), deixe `DB_USE_WINDOWS_AUTH=false`.

O script vai listar todas as tabelas do banco, tentar localizar a
tabela principal e comparar as colunas existentes com as que a lógica
espera. **Copie a saída completa e use para ajustar `app/services/sql_queries.py`.**

## Passo 2 — Configurar e rodar o backend

```bash
cd backend
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
# o .env já foi criado no Passo 1 — confirme que está completo
uvicorn app.main:app --reload --port 8000
```

Teste em `http://localhost:8000/api/previsao-entregas`.

## Passo 3 — Rodar o frontend localmente

Abra `frontend/index.html` num navegador, ou sirva com:

```bash
cd frontend
python -m http.server 5173
```

No `index.html`, ajuste `API_BASE_URL` se a API não estiver em
`localhost:8000`.

## Passo 4 — Subir para o GitHub

```bash
git init
git add .
git commit -m "Projeto inicial: migração DAX -> Python/Web"
git remote add origin <url-do-seu-repo>
git push -u origin main
```

**Confirme que o `.env` NÃO foi commitado** (`git status` não deve
mostrá-lo — já está no `.gitignore`).

## Passo 5 — Deploy do frontend no Vercel

1. Conecte o repositório no Vercel
2. Configure o "Root Directory" como `frontend`
3. Deploy automático a cada push

## Passo 6 — Backend no servidor da empresa

O backend (FastAPI) precisa rodar num servidor com acesso de rede ao
SQL Server — isso significa o servidor interno da empresa ("Coco do
Vale"), não o Vercel. Opções:

- `uvicorn` rodando como serviço (systemd no Linux, Task Scheduler/NSSM no Windows)
- Atrás de um reverse proxy (nginx) com HTTPS
- Exposto à internet apenas na rota necessária, com firewall restringindo
  origem se possível

Depois de no ar, atualize `API_BASE_URL` no frontend (e o `FRONTEND_ORIGIN`
no `.env` do backend, para o CORS funcionar) com a URL pública do backend.

## Estrutura de arquivos

```
backend/
  discover_schema.py       <- rodar primeiro, standalone
  app/
    config.py               <- variáveis de ambiente
    database.py              <- conexão pyodbc
    main.py                   <- app FastAPI
    routers/previsao.py        <- endpoints da API
    services/
      sql_queries.py           <- AJUSTAR após discover_schema.py
      logica_previsao.py        <- lógica de negócio (equivalente ao DAX)
    models/schemas.py            <- contrato JSON (Pydantic)
frontend/
  index.html                      <- interface (réplica visual do painel)
  vercel.json
```

## Próximos passos depois do discover_schema.py

Quando você rodar o script e me enviar a saída, eu ajusto:
1. `sql_queries.py` com os nomes reais de tabela/colunas
2. Qualquer lógica em `logica_previsao.py` que dependa de campo
   inexistente (ex: se `DT_PREVISTA_REDESPACHO` não existir fisicamente
   no banco, preciso saber como ela é calculada hoje no Power Query)
