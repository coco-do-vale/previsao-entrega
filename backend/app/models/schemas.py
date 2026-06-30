from pydantic import BaseModel
from datetime import date


class KPIs(BaseModel):
    faturamento_mes_bruto: float
    faturamento_mes_liquido: float
    faturamento_mes_com_romaneio: float
    nfs_mes: int
    nfs_mes_liquido: int
    nfs_mes_com_romaneio: int
    sem_romaneio_mes_qtd: int
    devolvido_mes_valor: float
    devolvido_mes_qtd: int
    faturamento_hoje: float
    faturamento_hoje_liquido: float
    nfs_hoje: int
    nfs_hoje_liquido: int
    sem_romaneio_hoje: int
    valor_sem_romaneio_hoje: float
    devolvido_hoje_valor: float
    devolvido_hoje_qtd: int
    sem_lead_time_total: int
    sem_lead_time_valor: float
    sem_lead_time_redespacho_qtd: int
    sem_lead_time_redespacho_valor: float
    sem_lead_time_direta_qtd: int
    sem_lead_time_direta_valor: float
    otd_pct: float
    otd_no_prazo: int
    otd_atrasado: int
    otd_antecipado: int
    otd_base: int
    pendentes_total: int
    em_transito_total: int
    em_transito_valor: float


class PontualidadePerna(BaseModel):
    qtd_total: int
    qtd_entregue: int
    valor_total: float
    valor_entregue: float
    antecipada: int
    no_prazo: int
    atrasada: int


class PontualidadeDia(BaseModel):
    direta: PontualidadePerna
    redespacho: PontualidadePerna


class ResumoPendentes(BaseModel):
    direta_qtd: int
    direta_valor: float
    redespacho_qtd: int
    redespacho_valor: float


class NotaFiscalLinha(BaseModel):
    ROMANEIO: str | None = None
    NF: int | str
    CLIENTE: str
    CIDADE_CLIENTE: str | None = None
    UF_CLIENTE: str | None = None
    TIPO_FLUXO: str
    TRANSP_PRINCIPAL: str | None = None
    lt_1a: str
    entrega_redesp: str
    status_1a: str
    transp_redesp: str
    lt_2a: str
    VALOR_NF: float
    DT_EMISSAO: date | None = None
    DT_PREVISTA_CLIENTE_FINAL: date | None = None
    DT_ENTREGA_CLIENTE: date | None = None
    status_final: str
    NF_ENTRADA: str | None = None


class PayloadCompleto(BaseModel):
    datas_referencia: dict[str, str]
    kpis: KPIs
    periodos: dict[str, list[NotaFiscalLinha]]
    pontualidade: dict[str, PontualidadeDia]
    resumo_pendentes: ResumoPendentes
