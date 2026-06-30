"""
Serviço de domínio: replica em Python/Pandas a lógica que estava no
modelo Power BI 'Logistica_Notas_matriz' — tanto a query SQL de origem
quanto as colunas calculadas DAX da tabela 'TFato Geral2'.

Cada função de cálculo aqui tem o comentário "DAX original:" mostrando
a fórmula DAX exata que ela replica, extraída via
INFO.VIEW.COLUMNS() do modelo real em 30/06/2026.
"""
from datetime import date, timedelta
import pandas as pd
from app.database import query_df
from app.services.sql_queries import SQL_FATO_GERAL, SQL_LOOKUP_NF_ENTRADA


# ---------------------------------------------------------------------
# 1) Cálculo das datas de referência (equivalente a D1..D5 no DAX
#    da medida HTML_Previsao_Entregas_v5)
# ---------------------------------------------------------------------

def _weekday_iso(d: date) -> int:
    """1=Segunda ... 7=Domingo, igual ao WEEKDAY(d,2) do DAX."""
    return d.isoweekday()


def calcular_datas_referencia(data_base: date) -> dict:
    """Replica D1..D5 do DAX: 1 dia útil anterior + hoje + 3 próximos
    dias úteis (pulando fins de semana)."""
    d2 = data_base

    wd = _weekday_iso(d2)
    delta_d1 = {1: 3, 2: 1, 3: 1, 4: 1, 5: 1, 6: 2, 7: 3}[wd]
    d1 = d2 - timedelta(days=delta_d1)

    wd2 = _weekday_iso(d2)
    delta_d3 = {5: 3, 6: 2, 7: 1}.get(wd2, 1)
    d3 = d2 + timedelta(days=delta_d3)

    d4 = d3 + timedelta(days=3 if _weekday_iso(d3) == 5 else 1)
    d5 = d4 + timedelta(days=3 if _weekday_iso(d4) == 5 else 1)

    return {"D1": d1, "D2": d2, "D3": d3, "D4": d4, "D5": d5}


# ---------------------------------------------------------------------
# 2) Carregamento da base + lookup de NF_ENTRADA
# ---------------------------------------------------------------------

def carregar_base() -> pd.DataFrame:
    df = query_df(SQL_FATO_GERAL)

    # Campos CHAR de tamanho fixo do Protheus vêm com espaços de preenchimento.
    for col in df.select_dtypes(include="object").columns:
        df[col] = df[col].str.strip()

    if "DT_SAÍDA" in df.columns and "DT_SAIDA" not in df.columns:
        df = df.rename(columns={"DT_SAÍDA": "DT_SAIDA"})

    for col_data in ["DT_EMISSAO", "DT_SAIDA", "DT_ENTREGA_REDESPACHO", "DT_ENTREGA_CLIENTE"]:
        if col_data in df.columns:
            df[col_data] = pd.to_datetime(df[col_data], errors="coerce").dt.date

    # Colunas calculadas (equivalentes às colunas DAX da tabela)
    df["DT_PREVISTA_REDESPACHO"] = df.apply(_calc_dt_prevista_redespacho, axis=1)
    df["DT_PREVISTA_CLIENTE_FINAL"] = df.apply(_calc_dt_prevista_cliente_final, axis=1)
    df["STATUS_OTD_TOTAL"] = df.apply(_calc_status_otd_total, axis=1)
    df["STATUS_OTD_REDESPACHO"] = df.apply(_calc_status_otd_redespacho, axis=1)

    # Lookup NF_ENTRADA (equivalente a LOOKUPVALUE(Leadtime[NF_ENTRADA], ...))
    try:
        lookup = query_df(SQL_LOOKUP_NF_ENTRADA)
        for col in lookup.select_dtypes(include="object").columns:
            lookup[col] = lookup[col].str.strip()
        df = df.merge(lookup[["NF", "NF_ENTRADA"]], on="NF", how="left")
    except Exception:
        df["NF_ENTRADA"] = None

    return df


# ---------------------------------------------------------------------
# 3) Colunas calculadas — fórmulas DAX replicadas fielmente
# ---------------------------------------------------------------------

def _adicionar_dias_uteis(base: date | None, lead_time: float | None, subtrair_um: bool = True) -> date | None:
    """Replica o padrão repetido nas fórmulas DAX:
        N = LeadTime - 1   (ou LeadTime, quando subtrair_um=False)
        W = INT(N/5); R = MOD(N,5); DS = WEEKDAY(Base,2)
        Extras = IF(DS+R>5, 2, 0)
        Resultado = Base + (W*7) + R + Extras

    subtrair_um=True  -> usado em DT_PREVISTA_REDESPACHO e na perna
                         DIRETA de DT_PREVISTA_CLIENTE_FINAL (valida-
                         do contra dados reais do modelo).
    subtrair_um=False -> usado na perna de REDESPACHO (PrevRedesp)
                         dentro de DT_PREVISTA_CLIENTE_FINAL — validado
                         com NFs 279673/279689/279690 (LR=3,2,1 ->
                         resultados batem exatamente sem o -1).
    """
    if base is None or pd.isna(base) or lead_time is None or pd.isna(lead_time):
        return None
    n = (lead_time - 1) if subtrair_um else lead_time
    w = int(n // 5)
    r = int(n % 5)
    ds = _weekday_iso(base)
    extras = 2 if (ds + r) > 5 else 0
    return base + timedelta(days=int(w * 7 + r + extras))


def _calc_dt_prevista_redespacho(row: pd.Series) -> date | None:
    """DAX original:
        VAR Base = DT_SAÍDA
        VAR N = LEAD_TIME_DIRETA - 1
        VAR W = INT(N/5); VAR R = MOD(N,5)
        VAR DS = WEEKDAY(Base,2)
        VAR Extras = IF(DS+R>5, 2, 0)
        RETURN Base + (W*7) + R + Extras
    """
    base = row.get("DT_SAIDA")
    lt_direta = row.get("LEAD_TIME_DIRETA")
    if base is None or pd.isna(base) or lt_direta is None or pd.isna(lt_direta):
        return None
    n = lt_direta - 1
    w = int(n // 5)
    r = int(n % 5)
    ds = _weekday_iso(base)
    extras = 2 if (ds + r) > 5 else 0
    return base + timedelta(days=int(w * 7 + r + extras))


def _calc_dt_prevista_cliente_final(row: pd.Series) -> date | None:
    """DAX original (resumido, validado contra dados reais):
        PrevDireta  = Base + dias_úteis(LEAD_TIME_DIRETA - 1)
        Hub         = COALESCE(DT_ENTREGA_REDESPACHO, DT_PREVISTA_REDESPACHO)
        PrevRedesp  = Hub + dias_úteis(LEAD_TIME_REDESPACHO)      [SEM o -1 aqui]
        RETURN: se TIPO_FLUXO = REDESPACHO -> PrevRedesp, senão -> PrevDireta
    """
    base = row.get("DT_SAIDA")
    if base is None or pd.isna(base):
        return None

    ld = row.get("LEAD_TIME_DIRETA")
    lr = row.get("LEAD_TIME_REDESPACHO")
    tipo_fluxo = row.get("TIPO_FLUXO")

    if tipo_fluxo == "REDESPACHO":
        hub_real = row.get("DT_ENTREGA_REDESPACHO")
        hub_prev = row.get("DT_PREVISTA_REDESPACHO")
        hub = hub_real if (hub_real is not None and not pd.isna(hub_real)) else hub_prev
        return _adicionar_dias_uteis(hub, lr, subtrair_um=False) if hub is not None else None
    else:
        if ld is None or pd.isna(ld):
            return None
        return _adicionar_dias_uteis(base, ld, subtrair_um=False)


def _calc_status_otd_total(row: pd.Series) -> str:
    """DAX original: SWITCH(TRUE(), ...) — replicado na mesma ordem
    de avaliação das condições."""
    ld = row.get("LEAD_TIME_DIRETA")
    lr = row.get("LEAD_TIME_REDESPACHO")
    tipo_fluxo = row.get("TIPO_FLUXO")
    dt_entrega = row.get("DT_ENTREGA_CLIENTE")
    dt_prevista = row.get("DT_PREVISTA_CLIENTE_FINAL")

    if ld is None or pd.isna(ld):
        return "Sem Lead Time"
    if tipo_fluxo == "REDESPACHO" and (lr is None or pd.isna(lr)):
        return "Sem Lead Time"

    if dt_entrega is None or pd.isna(dt_entrega) or dt_prevista is None or pd.isna(dt_prevista):
        no_prazo = False
    else:
        no_prazo = dt_entrega <= dt_prevista

    if tipo_fluxo == "ENTREGA DIRETA":
        return "No Prazo" if no_prazo else "Atrasado"
    if tipo_fluxo == "REDESPACHO":
        return "No Prazo" if no_prazo else "Atrasado"
    return ""


def _calc_status_otd_redespacho(row: pd.Series) -> str | None:
    """DAX original:
        IF TIPO_FLUXO <> REDESPACHO -> BLANK()
        ELSE IF ISBLANK(LEAD_TIME_REDESPACHO) -> "Sem Lead Time"
        ELSE IF ISBLANK(DT_ENTREGA_CLIENTE) -> BLANK()  (= Pendente, no front)
        ELSE IF DT_ENTREGA_CLIENTE <= DT_PREVISTA_CLIENTE_FINAL -> "No Prazo"
        ELSE -> "Atrasado"
    """
    tipo_fluxo = row.get("TIPO_FLUXO")
    if tipo_fluxo != "REDESPACHO":
        return None

    lr = row.get("LEAD_TIME_REDESPACHO")
    if lr is None or pd.isna(lr):
        return "Sem Lead Time"

    dt_entrega = row.get("DT_ENTREGA_CLIENTE")
    if dt_entrega is None or pd.isna(dt_entrega):
        return None

    dt_prevista = row.get("DT_PREVISTA_CLIENTE_FINAL")
    if dt_prevista is None or pd.isna(dt_prevista):
        return "Atrasado"

    return "No Prazo" if dt_entrega <= dt_prevista else "Atrasado"


# ---------------------------------------------------------------------
# 4) KPIs gerais
# ---------------------------------------------------------------------

def calcular_kpis(df: pd.DataFrame, hoje: date) -> dict:
    sem_lt = df[df["STATUS_OTD_TOTAL"] == "Sem Lead Time"]
    sem_lt_naoentregue = sem_lt[sem_lt["DT_ENTREGA_CLIENTE"].isna()]
    sem_lt_direta = sem_lt_naoentregue[sem_lt_naoentregue["TIPO_FLUXO"] == "ENTREGA DIRETA"]
    sem_lt_redesp = sem_lt_naoentregue[sem_lt_naoentregue["TIPO_FLUXO"] == "REDESPACHO"]

    mes_inicio = hoje.replace(day=1)
    base_mes_otd = df[
        (df["DT_ENTREGA_CLIENTE"].notna())
        & (df["DT_ENTREGA_CLIENTE"] >= mes_inicio)
        & (df["DT_ENTREGA_CLIENTE"] <= hoje)
    ]
    ot_ok = base_mes_otd[base_mes_otd["STATUS_OTD_TOTAL"] == "No Prazo"]
    ot_atr = base_mes_otd[base_mes_otd["STATUS_OTD_TOTAL"] == "Atrasado"]
    ot_ant = ot_ok[ot_ok["DT_ENTREGA_CLIENTE"] < ot_ok["DT_PREVISTA_CLIENTE_FINAL"]]

    pendentes = df[df["DT_ENTREGA_CLIENTE"].isna()]

    # Faturamento: baseado em DT_EMISSAO (não DT_ENTREGA_CLIENTE), igual à
    # medida "HTML Analise Faturamento" original.
    fat_mes_df = df[
        (df["DT_EMISSAO"].notna())
        & (df["DT_EMISSAO"] >= mes_inicio)
        & (df["DT_EMISSAO"] <= hoje)
    ]
    fat_mes_bruto = float(fat_mes_df["VALOR_NF"].sum())
    fat_mes_com_rom_df = fat_mes_df[fat_mes_df["ROMANEIO"].notna() & (fat_mes_df["ROMANEIO"] != "")]
    fat_mes_com_rom = float(fat_mes_com_rom_df["VALOR_NF"].sum())
    nfs_mes = int(fat_mes_df["NF"].nunique())
    nfs_mes_com_romaneio = int(fat_mes_com_rom_df["NF"].nunique())
    sem_romaneio_mes_qtd = nfs_mes - nfs_mes_com_romaneio

    # Devolução: NF de saída que tem uma NF de entrada correspondente
    # (LOOKUPVALUE NF_ENTRADA na tabela Leadtime — equivalente a "voltou").
    devolvido_mes_df = fat_mes_df[fat_mes_df["NF_ENTRADA"].notna() & (fat_mes_df["NF_ENTRADA"] != "")]
    devolvido_mes_valor = float(devolvido_mes_df["VALOR_NF"].sum())
    devolvido_mes_qtd = int(devolvido_mes_df["NF"].nunique())
    faturamento_mes_liquido = fat_mes_bruto - devolvido_mes_valor
    nfs_mes_liquido = nfs_mes - devolvido_mes_qtd

    fat_hoje_df = df[df["DT_EMISSAO"] == hoje]
    fat_hoje_bruto = float(fat_hoje_df["VALOR_NF"].sum())
    nfs_hoje = int(fat_hoje_df["NF"].nunique())
    sem_romaneio_hoje_df = fat_hoje_df[fat_hoje_df["ROMANEIO"].isna() | (fat_hoje_df["ROMANEIO"] == "")]
    sem_romaneio_hoje = int(sem_romaneio_hoje_df["NF"].nunique())
    valor_sem_romaneio_hoje = float(sem_romaneio_hoje_df["VALOR_NF"].sum())

    devolvido_hoje_df = fat_hoje_df[fat_hoje_df["NF_ENTRADA"].notna() & (fat_hoje_df["NF_ENTRADA"] != "")]
    devolvido_hoje_valor = float(devolvido_hoje_df["VALOR_NF"].sum())
    devolvido_hoje_qtd = int(devolvido_hoje_df["NF"].nunique())
    faturamento_hoje_liquido = fat_hoje_bruto - devolvido_hoje_valor
    nfs_hoje_liquido = nfs_hoje - devolvido_hoje_qtd

    em_transito = df[df["DT_ENTREGA_CLIENTE"].isna() & df["DT_SAIDA"].notna()]

    return {
        "faturamento_mes_bruto": fat_mes_bruto,
        "faturamento_mes_liquido": faturamento_mes_liquido,
        "faturamento_mes_com_romaneio": fat_mes_com_rom,
        "nfs_mes": nfs_mes,
        "nfs_mes_liquido": nfs_mes_liquido,
        "nfs_mes_com_romaneio": nfs_mes_com_romaneio,
        "sem_romaneio_mes_qtd": sem_romaneio_mes_qtd,
        "devolvido_mes_valor": devolvido_mes_valor,
        "devolvido_mes_qtd": devolvido_mes_qtd,
        "faturamento_hoje": fat_hoje_bruto,
        "faturamento_hoje_liquido": faturamento_hoje_liquido,
        "nfs_hoje": nfs_hoje,
        "nfs_hoje_liquido": nfs_hoje_liquido,
        "sem_romaneio_hoje": sem_romaneio_hoje,
        "valor_sem_romaneio_hoje": valor_sem_romaneio_hoje,
        "devolvido_hoje_valor": devolvido_hoje_valor,
        "devolvido_hoje_qtd": devolvido_hoje_qtd,
        "sem_lead_time_total": len(sem_lt_naoentregue),
        "sem_lead_time_valor": float(sem_lt_naoentregue["VALOR_NF"].sum()),
        "sem_lead_time_redespacho_qtd": len(sem_lt_redesp),
        "sem_lead_time_redespacho_valor": float(sem_lt_redesp["VALOR_NF"].sum()),
        "sem_lead_time_direta_qtd": len(sem_lt_direta),
        "sem_lead_time_direta_valor": float(sem_lt_direta["VALOR_NF"].sum()),
        "otd_pct": round((len(ot_ok) / max(len(ot_ok) + len(ot_atr), 1)) * 100, 1),
        "otd_no_prazo": len(ot_ok),
        "otd_atrasado": len(ot_atr),
        "otd_antecipado": len(ot_ant),
        "otd_base": len(ot_ok) + len(ot_atr),
        "pendentes_total": len(pendentes),
        "em_transito_total": len(em_transito),
        "em_transito_valor": float(em_transito["VALOR_NF"].sum()),
    }


def calcular_pontualidade_periodo(df: pd.DataFrame, data_referencia: date) -> dict:
    """Pontualidade detalhada por perna (direta/redespacho) para um dia
    específico — alimenta os blocos 'Pontualidade direta' e 'Pontualidade
    redespacho' de cada cartão do painel."""
    subset = df[df["DT_PREVISTA_CLIENTE_FINAL"] == data_referencia]

    direta = subset[subset["TIPO_FLUXO"] == "ENTREGA DIRETA"]
    redesp = subset[subset["TIPO_FLUXO"] == "REDESPACHO"]

    def _contagem(sub: pd.DataFrame) -> dict:
        entregue = sub[sub["DT_ENTREGA_CLIENTE"].notna()]
        antecipada = entregue[entregue["DT_ENTREGA_CLIENTE"] < entregue["DT_PREVISTA_CLIENTE_FINAL"]]
        no_prazo = entregue[entregue["DT_ENTREGA_CLIENTE"] == entregue["DT_PREVISTA_CLIENTE_FINAL"]]
        atrasada = entregue[entregue["DT_ENTREGA_CLIENTE"] > entregue["DT_PREVISTA_CLIENTE_FINAL"]]
        return {
            "qtd_total": len(sub),
            "qtd_entregue": len(entregue),
            "valor_total": float(sub["VALOR_NF"].sum()),
            "valor_entregue": float(entregue["VALOR_NF"].sum()),
            "antecipada": len(antecipada),
            "no_prazo": len(no_prazo),
            "atrasada": len(atrasada),
        }

    return {
        "direta": _contagem(direta),
        "redespacho": _contagem(redesp),
    }


# ---------------------------------------------------------------------
# 5) Status final de exibição (Pendente/Antecipada/No prazo/Atrasado)
# ---------------------------------------------------------------------

def status_primeira_perna_exibicao(row: pd.Series) -> str:
    if row.get("TIPO_FLUXO") != "REDESPACHO":
        return "—"
    raw = row.get("STATUS_OTD_REDESPACHO")
    if raw is None or (not isinstance(raw, str) and pd.isna(raw)):
        if pd.isna(row.get("DT_ENTREGA_REDESPACHO")):
            return "Pendente"
        return "—"
    return raw


def status_final_exibicao(row: pd.Series) -> str:
    dt_entrega = row.get("DT_ENTREGA_CLIENTE")
    if dt_entrega is None or pd.isna(dt_entrega):
        return "Pendente"
    dt_prevista = row.get("DT_PREVISTA_CLIENTE_FINAL")
    if dt_prevista is None or pd.isna(dt_prevista):
        return row.get("STATUS_OTD_TOTAL") or "—"
    if dt_entrega < dt_prevista:
        return "Antecipada"
    if dt_entrega == dt_prevista:
        return "No prazo"
    return "Atrasado"


# ---------------------------------------------------------------------
# 6) Tabela detalhada de notas fiscais por período
# ---------------------------------------------------------------------

def _formatar_linhas(subset: pd.DataFrame) -> list[dict]:
    if subset.empty:
        return []
    subset = subset.copy()

    subset["lt_1a"] = subset["LEAD_TIME_DIRETA"].apply(
        lambda v: "—" if pd.isna(v) else f"{int(v)}d"
    )
    subset["lt_2a"] = subset.apply(
        lambda r: "—" if r["TIPO_FLUXO"] != "REDESPACHO" or pd.isna(r.get("LEAD_TIME_REDESPACHO"))
        else f"{int(r['LEAD_TIME_REDESPACHO'])}d",
        axis=1,
    )
    subset["entrega_redesp"] = subset.apply(
        lambda r: "—" if r["TIPO_FLUXO"] != "REDESPACHO" or pd.isna(r.get("DT_ENTREGA_REDESPACHO"))
        else r["DT_ENTREGA_REDESPACHO"].strftime("%d/%m"),
        axis=1,
    )
    subset["transp_redesp"] = subset.apply(
        lambda r: "—" if r["TIPO_FLUXO"] != "REDESPACHO" else (r.get("TRANSP_REDESPACHO") or "—"),
        axis=1,
    )
    subset["status_1a"] = subset.apply(status_primeira_perna_exibicao, axis=1)
    subset["status_final"] = subset.apply(status_final_exibicao, axis=1)

    colunas_saida = [
        "ROMANEIO", "NF", "CLIENTE", "CIDADE_CLIENTE", "UF_CLIENTE", "TIPO_FLUXO",
        "TRANSP_PRINCIPAL", "lt_1a", "entrega_redesp", "status_1a",
        "transp_redesp", "lt_2a", "VALOR_NF", "DT_EMISSAO", "DT_PREVISTA_CLIENTE_FINAL",
        "DT_ENTREGA_CLIENTE", "status_final", "NF_ENTRADA",
    ]
    saida = subset[colunas_saida]
    saida = saida.astype(object).where(saida.notna(), None)
    return saida.to_dict(orient="records")


def montar_tabela_periodo(df: pd.DataFrame, data_referencia: date | None, pendente: bool = False) -> list[dict]:
    if pendente:
        filtro = df["DT_ENTREGA_CLIENTE"].isna() & (df["DT_PREVISTA_CLIENTE_FINAL"] < data_referencia)
    else:
        filtro = df["DT_PREVISTA_CLIENTE_FINAL"] == data_referencia
    return _formatar_linhas(df[filtro])


def montar_tabela_mes_com_romaneio(df: pd.DataFrame, hoje: date) -> list[dict]:
    """Todas as NFs emitidas no mês que têm romaneio atribuído — equivalente
    ao cartão "Faturamento do Mês (com Romaneio)"."""
    mes_inicio = hoje.replace(day=1)
    fat_mes_df = df[
        (df["DT_EMISSAO"].notna())
        & (df["DT_EMISSAO"] >= mes_inicio)
        & (df["DT_EMISSAO"] <= hoje)
    ]
    subset = fat_mes_df[fat_mes_df["ROMANEIO"].notna() & (fat_mes_df["ROMANEIO"] != "")]
    return _formatar_linhas(subset)


def montar_tabela_mes_sem_romaneio(df: pd.DataFrame, hoje: date) -> list[dict]:
    """Todas as NFs emitidas no mês que ainda NÃO têm romaneio atribuído —
    equivalente ao cartão "Sem Romaneio" do faturamento do mês."""
    mes_inicio = hoje.replace(day=1)
    fat_mes_df = df[
        (df["DT_EMISSAO"].notna())
        & (df["DT_EMISSAO"] >= mes_inicio)
        & (df["DT_EMISSAO"] <= hoje)
    ]
    subset = fat_mes_df[fat_mes_df["ROMANEIO"].isna() | (fat_mes_df["ROMANEIO"] == "")]
    return _formatar_linhas(subset)


def montar_tabela_hoje(df: pd.DataFrame, hoje: date) -> list[dict]:
    """Todas as NFs emitidas hoje — equivalente ao cartão "Faturamento de Hoje"."""
    subset = df[df["DT_EMISSAO"] == hoje]
    return _formatar_linhas(subset)


def montar_tabela_hoje_sem_romaneio(df: pd.DataFrame, hoje: date) -> list[dict]:
    """NFs emitidas hoje que ainda NÃO têm romaneio atribuído."""
    fat_hoje_df = df[df["DT_EMISSAO"] == hoje]
    subset = fat_hoje_df[fat_hoje_df["ROMANEIO"].isna() | (fat_hoje_df["ROMANEIO"] == "")]
    return _formatar_linhas(subset)


def montar_sem_lead_time(df: pd.DataFrame) -> dict:
    """Equivalente à medida DAX 'HTML Transp Sem Lead Cidades': NFs pendentes
    de entrega (DT_ENTREGA_CLIENTE em branco) cujo lead time não está
    cadastrado (1ª perna para ENTREGA DIRETA, 2ª perna para REDESPACHO),
    agrupadas por transportadora/cidade/UF, com o detalhe das NFs.

    Diferença em relação à DAX original: lá a lista de cidades vem de uma
    tabela cadastral 'Leadtime' separada (mostra cidades sem LT mesmo sem
    nenhuma NF pendente). Aqui partimos das NFs pendentes sem LT já
    calculadas — mostra só combinações transportadora/cidade que têm pelo
    menos 1 NF parada por isso, que é o subconjunto realmente acionável.
    """
    sem_lt = df[df["STATUS_OTD_TOTAL"] == "Sem Lead Time"]
    sem_lt_naoentregue = sem_lt[sem_lt["DT_ENTREGA_CLIENTE"].isna()]

    tem_romaneio = sem_lt_naoentregue["ROMANEIO"].notna() & (sem_lt_naoentregue["ROMANEIO"] != "")

    direta = sem_lt_naoentregue[(sem_lt_naoentregue["TIPO_FLUXO"] == "ENTREGA DIRETA") & tem_romaneio]
    redesp = sem_lt_naoentregue[
        (sem_lt_naoentregue["TIPO_FLUXO"] == "REDESPACHO") & tem_romaneio
        & sem_lt_naoentregue["TRANSP_REDESPACHO"].notna()
        & (sem_lt_naoentregue["TRANSP_REDESPACHO"] != "SEM ROMANEIO")
    ]

    sem_romaneio_df = sem_lt_naoentregue[~tem_romaneio]
    sem_romaneio_qtd = int(len(sem_romaneio_df))
    sem_romaneio_nfs = _formatar_linhas(sem_romaneio_df)

    def _resumo_cidades(sub: pd.DataFrame, col_transp: str) -> list[dict]:
        if sub.empty:
            return []
        g = (
            sub.groupby([col_transp, "CIDADE_CLIENTE", "UF_CLIENTE"])
            .size()
            .reset_index(name="qtd")
            .sort_values([col_transp, "CIDADE_CLIENTE"])
        )
        g = g.rename(columns={col_transp: "TRANSPORTADORA"})
        return g.to_dict(orient="records")

    def _resumo_perna(sub: pd.DataFrame, col_transp: str) -> dict:
        return {
            "nfs": _formatar_linhas(sub),
            "cidades": _resumo_cidades(sub, col_transp),
            "nfs_total": len(sub),
            "transportadoras_total": int(sub[col_transp].nunique()) if not sub.empty else 0,
            "cidades_total": int(sub["CIDADE_CLIENTE"].nunique()) if not sub.empty else 0,
            "ufs_total": int(sub["UF_CLIENTE"].nunique()) if not sub.empty else 0,
        }

    return {
        "direta": _resumo_perna(direta, "TRANSP_PRINCIPAL"),
        "redespacho": _resumo_perna(redesp, "TRANSP_REDESPACHO"),
        "sem_romaneio_qtd": sem_romaneio_qtd,
        "sem_romaneio_nfs": sem_romaneio_nfs,
    }


def montar_analise_previsao(df: pd.DataFrame) -> list[dict]:
    """Equivalente à medida DAX 'HTML Analise Previsao v2': base completa de
    NFs com data prevista de entrega (de qualquer período), para a página
    de análise de OTD. Filtros (mês/ano/dia/UF/transportadora) e KPIs são
    recalculados no frontend a partir desta base, igual aos slicers do
    Power BI.
    """
    base = df[df["DT_PREVISTA_CLIENTE_FINAL"].notna()].copy()

    # NFs que são, elas mesmas, o documento de entrada/devolução de outra
    # NF (aparecem como NF_ENTRADA de alguma linha) — excluídas das
    # pendentes para não duplicar a mesma devolução nos dois lados.
    nfs_entrada_set = set(df["NF_ENTRADA"].dropna().unique())
    pendente_a_excluir = base["DT_ENTREGA_CLIENTE"].isna() & base["NF"].isin(nfs_entrada_set)
    base = base[~pendente_a_excluir]

    def _status(row):
        if pd.isna(row["DT_ENTREGA_CLIENTE"]):
            return "pend"
        if row["DT_ENTREGA_CLIENTE"] < row["DT_PREVISTA_CLIENTE_FINAL"]:
            return "ant"
        if row["DT_ENTREGA_CLIENTE"] == row["DT_PREVISTA_CLIENTE_FINAL"]:
            return "prz"
        return "atr"

    base["status"] = base.apply(_status, axis=1)
    base["delta"] = base.apply(
        lambda r: None if pd.isna(r["DT_ENTREGA_CLIENTE"])
        else (r["DT_ENTREGA_CLIENTE"] - r["DT_PREVISTA_CLIENTE_FINAL"]).days,
        axis=1,
    )

    colunas = [
        "NF", "CLIENTE", "CIDADE_CLIENTE", "UF_CLIENTE", "TIPO_FLUXO",
        "TRANSP_PRINCIPAL", "TRANSP_REDESPACHO", "VALOR_NF",
        "DT_PREVISTA_CLIENTE_FINAL", "DT_ENTREGA_CLIENTE", "delta", "status", "NF_ENTRADA",
    ]
    saida = base[colunas]
    saida = saida.astype(object).where(saida.notna(), None)
    return saida.to_dict(orient="records")


# ---------------------------------------------------------------------
# 7) Orquestrador principal
# ---------------------------------------------------------------------

def montar_payload_completo(data_base: date | None = None) -> dict:
    hoje = date.today()
    data_base = data_base or hoje

    df = carregar_base()
    datas = calcular_datas_referencia(data_base)
    kpis = calcular_kpis(df, hoje)

    periodos = {
        "pendentes": montar_tabela_periodo(df, datas["D1"], pendente=True),
        "d1": montar_tabela_periodo(df, datas["D1"]),
        "d2": montar_tabela_periodo(df, datas["D2"]),
        "d3": montar_tabela_periodo(df, datas["D3"]),
        "d4": montar_tabela_periodo(df, datas["D4"]),
        "d5": montar_tabela_periodo(df, datas["D5"]),
    }

    pontualidade = {
        "d1": calcular_pontualidade_periodo(df, datas["D1"]),
        "d2": calcular_pontualidade_periodo(df, datas["D2"]),
        "d3": calcular_pontualidade_periodo(df, datas["D3"]),
        "d4": calcular_pontualidade_periodo(df, datas["D4"]),
        "d5": calcular_pontualidade_periodo(df, datas["D5"]),
    }

    # Pendentes: NFs com prazo já vencido (antes de D1) e ainda sem entrega,
    # separadas por fluxo — alimenta o cartão "NF Pendentes".
    pend_df = df[
        df["DT_ENTREGA_CLIENTE"].isna()
        & (df["DT_PREVISTA_CLIENTE_FINAL"] < datas["D1"])
    ]
    pend_direta = pend_df[pend_df["TIPO_FLUXO"] == "ENTREGA DIRETA"]
    pend_redesp = pend_df[pend_df["TIPO_FLUXO"] == "REDESPACHO"]
    resumo_pendentes = {
        "direta_qtd": len(pend_direta),
        "direta_valor": float(pend_direta["VALOR_NF"].sum()),
        "redespacho_qtd": len(pend_redesp),
        "redespacho_valor": float(pend_redesp["VALOR_NF"].sum()),
    }

    return {
        "datas_referencia": {k: v.isoformat() for k, v in datas.items()},
        "kpis": kpis,
        "periodos": periodos,
        "pontualidade": pontualidade,
        "resumo_pendentes": resumo_pendentes,
    }
