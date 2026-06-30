from fastapi import APIRouter, HTTPException, Query
from datetime import date
import io
import csv
import traceback
from fastapi.responses import StreamingResponse

from app.services.logica_previsao import (
    montar_payload_completo, carregar_base, montar_tabela_periodo,
    montar_tabela_mes_com_romaneio, montar_tabela_mes_sem_romaneio,
    montar_tabela_hoje, montar_tabela_hoje_sem_romaneio,
    montar_sem_lead_time,
    calcular_datas_referencia,
)

router = APIRouter(prefix="/api", tags=["previsao-entregas"])

PERIODOS_VALIDOS = {
    "pendentes", "d1", "d2", "d3", "d4", "d5",
    "mes-com-romaneio", "mes-sem-romaneio",
    "hoje", "hoje-sem-romaneio",
}


@router.get("/previsao-entregas")
def get_previsao_entregas(data_base: date | None = Query(None, description="Data base do painel (default: hoje)")):
    """Endpoint principal — substitui inteiramente a medida
    HTML_Previsao_Entregas_v5. Retorna KPIs + tabelas por período."""
    try:
        return montar_payload_completo(data_base)
    except Exception as e:
        # Durante o desenvolvimento, expor o erro completo ajuda a diagnosticar
        # problemas de conexão/schema sem precisar olhar o terminal.
        detalhe = f"{type(e).__name__}: {e}"
        print("=" * 70)
        print("ERRO em /api/previsao-entregas:")
        traceback.print_exc()
        print("=" * 70)
        raise HTTPException(status_code=500, detail=detalhe)


@router.get("/notas-fiscais/{periodo}")
def get_notas_por_periodo(
    periodo: str,
    data_base: date | None = Query(None),
):
    """periodo: 'pendentes', 'd1', 'd2', 'd3', 'd4' ou 'd5'.
    Usado quando o usuário clica em um cartão para abrir o modal."""
    periodo = periodo.lower()
    if periodo not in PERIODOS_VALIDOS:
        raise HTTPException(status_code=400, detail="Período inválido")

    df = carregar_base()
    hoje = data_base or date.today()

    if periodo == "mes-com-romaneio":
        return montar_tabela_mes_com_romaneio(df, hoje)
    if periodo == "mes-sem-romaneio":
        return montar_tabela_mes_sem_romaneio(df, hoje)
    if periodo == "hoje":
        return montar_tabela_hoje(df, hoje)
    if periodo == "hoje-sem-romaneio":
        return montar_tabela_hoje_sem_romaneio(df, hoje)

    datas = calcular_datas_referencia(hoje)

    if periodo == "pendentes":
        return montar_tabela_periodo(df, datas["D1"], pendente=True)
    mapa = {"d1": "D1", "d2": "D2", "d3": "D3", "d4": "D4", "d5": "D5"}
    return montar_tabela_periodo(df, datas[mapa[periodo]])


@router.get("/notas-fiscais/{periodo}/export.csv")
def exportar_csv(periodo: str, data_base: date | None = Query(None)):
    """Exportação CSV — muito mais simples aqui do que no DAX/JS original."""
    dados = get_notas_por_periodo(periodo, data_base)
    if not dados:
        raise HTTPException(status_code=404, detail="Sem dados para exportar")

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=dados[0].keys(), delimiter=";")
    writer.writeheader()
    writer.writerows(dados)
    output.seek(0)

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=NFs_{periodo}.csv"},
    )


@router.get("/sem-lead-time")
def get_sem_lead_time():
    """Transportadoras/cidades sem lead time cadastrado — NFs pendentes de
    entrega cujo cálculo de prazo não pôde ser feito por falta de LT."""
    df = carregar_base()
    return montar_sem_lead_time(df)


@router.get("/health")
def health_check():
    """Para monitoramento (Vercel/uptime check)."""
    return {"status": "ok"}
