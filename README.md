# Previsão de Entregas — Coco do Vale

Aplicação web (FastAPI + HTML/JS) que substitui um conjunto de medidas
DAX do Power BI (`HTML_Previsao_Entregas_v5`, `HTML Transp Sem Lead
Cidades`, `HTML Analise Previsao v2`), lendo direto do SQL Server
(Protheus/TOTVS) da empresa.

## Arquitetura

```
Navegador (qualquer máquina da rede interna)
        │  HTTP
        ▼
FastAPI (uvicorn) — roda no servidor da empresa
  ├─ serve o frontend estático (frontend/*.html)
  ├─ /api/auth/*   → login, cadastro, sessão, reset de senha (SQLite local)
  └─ /api/*        → dados (pandas + pyodbc)
        │
        ▼
SQL Server da empresa (Protheus/TOTVS)
```

Um único processo serve frontend e API na mesma origem — sem CORS, sem
depender de "localhost", acessível por qualquer máquina da rede interna
pelo IP/nome do servidor. **O backend precisa rodar dentro da rede da
empresa** (ou com VPN/túnel de acesso ao SQL Server) — hoje o projeto
está deliberadamente restrito à rede interna (sem exposição à internet).

## Páginas

| Arquivo | O que é |
|---|---|
| `login.html` | Login / cadastro (restrito a e-mail `@cocodovale.com.br`) / esqueci minha senha |
| `redefinir-senha.html` | Definir nova senha a partir do link de reset |
| `index.html` | Painel principal — KPIs, faturamento, pontualidade por dia, sem lead time |
| `analise-previsao.html` | Análise de OTD com filtros (mês/ano/dia/UF/transportadora) e projeção de cenários |

Todas exigem sessão válida (exceto login/cadastro/reset). O painel principal
e a análise de previsão se atualizam sozinhos a cada 60s.

## Passo 1 — Descobrir o schema real (só na primeira vez)

```bash
cd backend
python -m venv venv
venv\Scripts\activate          # Windows
pip install -r requirements.txt
cp .env.example .env
# edite o .env com os dados reais (server, porta, database, usuário, senha)
python discover_schema.py
```

`DB_SERVER` aceita o formato `IP,PORTA` quando a porta não é a padrão
(ex: `181.41.170.237,1319`). Use `DB_USE_WINDOWS_AUTH=false` para login
de SQL (usuário/senha, não Windows).

Se a estrutura do banco mudar no futuro, rode o script de novo e ajuste
`backend/app/services/sql_queries.py` com os nomes reais de tabela/coluna.

## Passo 2 — Rodar localmente (desenvolvimento)

```bash
cd backend
venv\Scripts\activate
uvicorn app.main:app --reload --port 8000
```

Acesse `http://localhost:8000/` — o próprio backend já serve o frontend
junto. Crie uma conta com e-mail `@cocodovale.com.br` na primeira tela.

Scripts de diagnóstico úteis se a conexão com o banco falhar:
```bash
python check_env.py          # confere se o .env está sendo lido certo
python check_connection.py   # testa a conexão pyodbc isolada
```

## Passo 3 — Rodar como serviço (produção / servidor da empresa)

Deixa o backend de pé sozinho, mesmo após reiniciar o Windows ou sem
ninguém logado:

```powershell
# Num PowerShell aberto como Administrador:
cd C:\previsao-entregas\backend
.\instalar-servico.ps1
```

Isso registra uma tarefa agendada do Windows (`PrevisaoEntregas-Backend`)
rodando `uvicorn` sem `--reload`, escutando em `0.0.0.0:8000`, e libera a
porta no firewall do Windows para acesso pela rede.

**Sempre que o código do backend mudar**, reinicie o serviço (mudanças no
frontend — `.html`/`.js` — não precisam, são servidas direto do disco):
```powershell
Stop-ScheduledTask -TaskName "PrevisaoEntregas-Backend"
Start-ScheduledTask -TaskName "PrevisaoEntregas-Backend"
```

### Tela cheia / modo quiosque

- Botão **⛶** na barra superior do painel alterna tela cheia (ou tecle `F11`)
- `abrir-modo-quiosque.bat` (raiz do projeto) abre o navegador sem nenhuma
  barra/aba, ideal pra fixar numa TV/monitor da operação. Edite a variável
  `URL` dentro dele se for rodar numa máquina diferente do servidor.

## Autenticação

- Cadastro livre, mas só para e-mails `@cocodovale.com.br`
- Senha com hash bcrypt (nunca gravada em texto puro)
- Sessão via cookie (7 dias)
- Auditoria de login (quem/quando/sucesso ou falha) — sem guardar senha
- **"Esqueci minha senha" ainda não envia e-mail de verdade** (não há SMTP
  configurado): o link de redefinição é gravado em
  `backend/reset_pendentes.log` (não versionado) e precisa ser repassado
  manualmente pelo admin até a TI liberar um servidor de e-mail

## Estrutura de arquivos

```
backend/
  discover_schema.py        <- rodar na primeira vez
  check_env.py / check_connection.py   <- diagnóstico de conexão
  instalar-servico.ps1      <- registra o serviço Windows (rodar como admin)
  app/
    config.py                 <- variáveis de ambiente
    database.py                <- conexão pyodbc
    main.py                     <- app FastAPI + serve o frontend
    auth_db.py                   <- usuários/sessões/auditoria (SQLite local)
    routers/
      auth.py                     <- login, cadastro, sessão, reset de senha
      previsao.py                  <- endpoints de dados (protegidos por login)
    services/
      sql_queries.py                <- queries SQL (extraídas do Power Query)
      logica_previsao.py             <- lógica de negócio (equivalente ao DAX)
    models/schemas.py                 <- contrato JSON (Pydantic, parcial)
frontend/
  index.html                          <- painel principal
  analise-previsao.html                <- página de análise de OTD
  login.html / redefinir-senha.html     <- autenticação
abrir-modo-quiosque.bat                  <- atalho de modo quiosque
```

## Pontos de atenção / pendências conhecidas

- **Filtro de data fixo no SQL** (`F2_EMISSAO >= '20260101'` em
  `sql_queries.py`) — precisa ser atualizado manualmente a cada virada de
  ano, senão o painel silenciosamente para de trazer dados novos.
- **Servidor atual é provisório** — rodando num notebook, não numa máquina
  dedicada. Migrar para servidor/VM definitivo da empresa quando disponível
  (processo de deploy é o mesmo: clonar, configurar `.env`, instalar
  serviço).
- **Sem SMTP** para reset de senha (ver seção Autenticação acima).
- **Sem rate-limit** no login (sem bloqueio após tentativas erradas).
- `backend/.env` deve ter `DEBUG=false` e `FRONTEND_ORIGIN` atualizado (ou
  removido) antes de qualquer exposição mais ampla — hoje em
  desenvolvimento está com `DEBUG=true`.
- `backend/auth.db` (contas de usuário) não tem backup automático — fazer
  cópia periódica do arquivo.

## Git / GitHub

Repositório: https://github.com/coco-do-vale/previsao-entrega

```bash
git add .
git commit -m "..."
git push
```

**Nunca commitar** `backend/.env`, `backend/auth.db` ou
`backend/reset_pendentes.log` — já estão no `.gitignore`.

## Checklist — migrar para o servidor definitivo da empresa

Hoje o backend roda provisoriamente num notebook (ver "Pontos de atenção"
acima). Quando a TI liberar a máquina/VM definitiva, seguir esta ordem:

### 1. Preparar o servidor
- [ ] Windows com Python 3.x instalado
- [ ] ODBC Driver 18 for SQL Server instalado
- [ ] Acesso de rede liberado para o SQL Server (`181.41.170.237:1319`, ou
      o endereço atual — confirmar com a TI)
- [ ] Máquina configurada para **nunca dormir/hibernar** (é ela que vai
      ficar de pé 24/7)

### 2. Deploy
- [ ] `git clone https://github.com/coco-do-vale/previsao-entrega.git`
- [ ] Criar `backend/.env` com as credenciais reais (não vem no clone —
      copiar de `backend/.env.example` e preencher)
- [ ] Setar `DEBUG=false` no `.env`
- [ ] Corrigir/remover `FRONTEND_ORIGIN` (resquício de quando frontend e
      backend eram servidos separados — hoje não é mais necessário)
- [ ] `cd backend && python -m venv venv && venv\Scripts\activate`
- [ ] `pip install -r requirements.txt`
- [ ] Rodar `python discover_schema.py` pra confirmar que a estrutura do
      banco é a mesma (se a TI migrou pra outro servidor/instância)
- [ ] Rodar `instalar-servico.ps1` **como Administrador** (registra o
      serviço Windows + libera o firewall)
- [ ] Testar em `http://<nome-ou-ip-do-servidor>:8000/` de outra máquina
      da rede

### 3. Antes de liberar pro time todo
- [ ] Configurar SMTP (provavelmente Office 365/Exchange da empresa) para
      o "esqueci minha senha" enviar e-mail de verdade — hoje é manual
      (`backend/reset_pendentes.log`)
- [ ] Adicionar algum rate-limit/bloqueio no login (hoje não existe)
- [ ] Definir rotina de backup do `backend/auth.db` (cópia periódica já
      resolve — é onde ficam as contas de usuário)
- [ ] Conferir de novo que `DEBUG=false` está ativo

### 4. Recorrente (não esquecer)
- [ ] **Todo início de ano**: atualizar `F2_EMISSAO >= 'AAAA0101'` em
      `backend/app/services/sql_queries.py` (hoje fixo em `20260101`)
