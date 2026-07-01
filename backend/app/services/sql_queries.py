"""
Centraliza todas as queries SQL do projeto.

Estas queries foram extraídas DIRETAMENTE do Power Query (M) do modelo
Power BI 'Logistica_Notas_matriz', tabelas 'TFato Geral2' e 'Leadtime'.
Não são tabelas físicas no banco — são o resultado de SELECTs complexos
contra o ERP Protheus/TOTVS (tabelas SF2010, SA1010, GU3010, etc.).

IMPORTANTE: o filtro de data 'F2_EMISSAO >= 20260101' está hardcoded
no Power Query original. Mantive aqui para fidelidade, mas isso significa
que a cada virada de ano alguém precisa atualizar esse valor (tanto aqui
quanto no Power BI original). Considere parametrizar no futuro.
"""

SQL_FATO_GERAL = """
WITH VENDEDORES_PERMITIDOS AS (
    SELECT
        REPLACE(LTRIM(RTRIM(ZB5_IDVEND)), '_', '') AS COD_VENDEDOR
    FROM ZB5010
    WHERE D_E_L_E_T_ = ' '
      AND LTRIM(RTRIM(ISNULL(ZB5_COORD, ''))) <> ''
      AND REPLACE(LTRIM(RTRIM(ZB5_IDVEND)), '_', '') NOT IN (
            '000900', '000901', '0305', 'EX0018', 'EX0019', 'S00035'
      )
)
SELECT DISTINCT

    -- TRANSPORTADORA PRINCIPAL (1ª PERNA)
    GWN.GWN_CDTRP AS COD_TRANSP_PRINCIPAL,
    NULLIF(RTRIM(TP1.GU3_CDTERP), ' ') AS COD_ERP_PRINCIPAL,
    COALESCE(TP1.GU3_NMFAN, 'SEM ROMANEIO') AS TRANSP_PRINCIPAL,

    -- REDESPACHO
    COALESCE(
        NULLIF(GWU.GWU_CDTRP, ' '),
        NULLIF(SF2.F2_REDESP, ' ')
    ) AS COD_TRANSP_REDESPACHO,
    COALESCE(
        NULLIF(SF2.F2_REDESP, ' '),
        NULLIF(TP2.GU3_CDTERP, ' '),
        NULLIF(REDLKP.GU3_CDTERP, ' ')
    ) AS COD_REDESPACHO,
    COALESCE(TP2.GU3_NMFAN, RED.GU3_NMFAN) AS TRANSP_REDESPACHO,

    -- ROMANEIO
    GWN.GWN_NRROM AS ROMANEIO,

    -- NOTA
    SF2.F2_DOC AS NF,
    SF2.F2_SERIE AS SERIE,

    -- DATAS
    SF2.F2_EMISSAO AS DT_EMISSAO,
    SF2.F2_DTCARGA AS DT_SAIDA,
    GWU.GWU_DTENT AS DT_ENTREGA_REDESPACHO,
    SF2.F2_DTENTR AS DT_ENTREGA_CLIENTE,

    -- VALORES
    CAST(ITENS.VL_PRODUTOS AS DECIMAL(15,2)) AS VALOR_NF,

    -- CARGA
    SF2.F2_CARGA AS NR_CARGA,

    -- PESOS
    CAST(SF2.F2_PBRUTO AS DECIMAL(15,2)) AS PESO_BRUTO,

    -- CLIENTE
    SF2.F2_CLIENTE AS COD_CLIENTE,
    SA1.A1_LOJA AS LOJA,
    SA1.A1_NOME AS CLIENTE,
    SA1.A1_MUN AS CIDADE_CLIENTE,
    SA1.A1_EST AS UF_CLIENTE,

    -- VENDEDOR
    SF2.F2_VEND1 AS COD_VENDEDOR,
    SA3.A3_SUPER AS SUPERVISOR,

    -- TIPO FLUXO
    CASE
        WHEN GWU.GWU_CDTRP IS NOT NULL THEN 'REDESPACHO'
        ELSE 'ENTREGA DIRETA'
    END AS TIPO_FLUXO,

    -- LEAD TIME
    CAST(LT_DIRETA.Z00_LDTIME AS INT) AS LEAD_TIME_DIRETA,
    CAST(LT_REDESP.Z00_LDTIME AS INT) AS LEAD_TIME_REDESPACHO,
    CASE
        WHEN GWU.GWU_CDTRP IS NOT NULL
        THEN CAST(LT_DIRETA.Z00_LDTIME AS INT) + ISNULL(CAST(LT_REDESP.Z00_LDTIME AS INT), 0)
        ELSE CAST(LT_DIRETA.Z00_LDTIME AS INT)
    END AS LEAD_TIME_TOTAL

FROM SF2010 SF2
INNER JOIN SA1010 SA1
        ON SA1.A1_COD = SF2.F2_CLIENTE
       AND SA1.A1_LOJA = SF2.F2_LOJA
       AND SA1.D_E_L_E_T_ = ' '
INNER JOIN SA3010 SA3
        ON SA3.A3_COD = SF2.F2_VEND1
       AND SA3.D_E_L_E_T_ = ' '
INNER JOIN VENDEDORES_PERMITIDOS VP
        ON VP.COD_VENDEDOR = REPLACE(LTRIM(RTRIM(SF2.F2_VEND1)), '_', '')
INNER JOIN (
    SELECT
        D2_DOC,
        D2_SERIE,
        D2_FILIAL,
        SUM(D2_TOTAL) AS VL_PRODUTOS
    FROM SD2010
    WHERE D_E_L_E_T_ = ' '
      AND D2_FILIAL = '02'
      AND RTRIM(D2_CF) IN ('5101','5102','5105','5118','5551',
                           '6101','6102','6105','6107','6108','6109','6110','6118',
                           '6401','6403','6501','6551','7101','7127')
    GROUP BY D2_DOC, D2_SERIE, D2_FILIAL
) ITENS
        ON ITENS.D2_DOC = SF2.F2_DOC
       AND ITENS.D2_SERIE = SF2.F2_SERIE
       AND ITENS.D2_FILIAL = SF2.F2_FILIAL
LEFT JOIN GW1010 GW1
        ON GW1.GW1_NRDC = SF2.F2_DOC
       AND GW1.GW1_SERDC = SF2.F2_SERIE
       AND GW1.D_E_L_E_T_ = ' '
LEFT JOIN GWN010 GWN
        ON GWN.GWN_NRROM = GW1.GW1_NRROM
       AND GWN.D_E_L_E_T_ = ' '
LEFT JOIN GWU010 GWU
        ON GWU.GWU_NRDC = SF2.F2_DOC
       AND GWU.GWU_SERDC = SF2.F2_SERIE
       AND GWU.D_E_L_E_T_ = ' '
       AND GWU.GWU_CDTRP <> GWN.GWN_CDTRP
LEFT JOIN GU3010 TP1
        ON TP1.GU3_CDEMIT = GWN.GWN_CDTRP
       AND TP1.D_E_L_E_T_ = ' '
LEFT JOIN GU3010 TP2
        ON TP2.GU3_CDEMIT = COALESCE(NULLIF(GWU.GWU_CDTRP, ' '), NULLIF(SF2.F2_REDESP, ' '))
       AND TP2.D_E_L_E_T_ = ' '
LEFT JOIN GU3010 RED
        ON RED.GU3_CDEMIT = SF2.F2_REDESP
       AND RED.D_E_L_E_T_ = ' '
LEFT JOIN (
    SELECT
        GU3_NMFAN,
        MAX(NULLIF(RTRIM(GU3_CDTERP), ' ')) AS GU3_CDTERP
    FROM GU3010
    WHERE D_E_L_E_T_ = ' '
      AND NULLIF(RTRIM(GU3_CDTERP), ' ') IS NOT NULL
    GROUP BY GU3_NMFAN
) REDLKP
        ON REDLKP.GU3_NMFAN = TP2.GU3_NMFAN
LEFT JOIN (
    SELECT
        Z00_TRANSP, Z00_EST, Z00_CODCID,
        MAX(Z00_LDTIME) AS Z00_LDTIME
    FROM Z00010
    WHERE D_E_L_E_T_ = ' '
    GROUP BY Z00_TRANSP, Z00_EST, Z00_CODCID
) LT_DIRETA
        ON LT_DIRETA.Z00_TRANSP = NULLIF(RTRIM(TP1.GU3_CDTERP), ' ')
       AND LT_DIRETA.Z00_EST = SA1.A1_EST
       AND LT_DIRETA.Z00_CODCID = SA1.A1_COD_MUN
LEFT JOIN (
    SELECT
        Z00_TRANSP, Z00_EST, Z00_CODCID,
        MAX(Z00_LDTIME) AS Z00_LDTIME
    FROM Z00010
    WHERE D_E_L_E_T_ = ' '
    GROUP BY Z00_TRANSP, Z00_EST, Z00_CODCID
) LT_REDESP
        ON LT_REDESP.Z00_TRANSP = NULLIF(RTRIM(TP2.GU3_CDTERP), ' ')
       AND LT_REDESP.Z00_EST = SA1.A1_EST
       AND LT_REDESP.Z00_CODCID = SA1.A1_COD_MUN

WHERE SF2.F2_FILIAL = '02'
  AND SF2.D_E_L_E_T_ = ' '
  AND SA1.A1_EST <> 'EX'
  AND SF2.F2_VEND1 NOT LIKE 'EX%'
  AND SF2.F2_EMISSAO >= '20260101'
  AND SF2.F2_TRANSP <> ' '
  AND SF2.F2_TRANSP IS NOT NULL
  AND SA3.A3_SUPER <> ' '
  AND SA3.A3_SUPER <> 'S00090'
  AND SF2.F2_CLIENTE <> '015269'

ORDER BY
    SF2.F2_DOC,
    GWU.GWU_DTENT
"""


SQL_CARTEIRA_PEDIDOS = """
SELECT
    C5.C5_NUM                                                   AS [N PEDIDO],
    C5.C5_PEDCLIE                                               AS [PED CLIENTE],
    C6.C6_NOTA                                                  AS [INVOICE],
    CASE WHEN LTRIM(RTRIM(C6.C6_NOTA)) <> '' THEN 'PARCIAL' ELSE 'PENDENTE' END AS [SITUACAO],
    C5.C5_EMISSAO                                               AS [EMISSAO],
    C5.C5_CLIENTE                                               AS [CODIGO],
    C5.C5_LOJACLI                                               AS [LJ],
    A1.A1_NOME                                                  AS [NOME CLIENTE],
    A1.A1_EST                                                   AS [UF],
    A1.A1_MUN                                                   AS [MUNICIPIO],
    C5.C5_VEND1                                                 AS [COD VEND],
    A3.A3_NOME                                                  AS [VENDEDOR],
    C6.C6_DATFAT                                                AS [PRVFAT],
    C6.C6_ENTREG                                                AS [DT ENTREGA],
    C6.C6_ITEM                                                  AS [IT],
    C6.C6_PRODUTO                                               AS [COD PRODUTO],
    C6.C6_RESERVA                                               AS [RES S/N],
    C6.C6_QTDVEN                                                AS [QTD PEDIDA],
    C6.C6_QTDENT                                                AS [QTD ENTREGUE],
    CAST(NULL AS VARCHAR(10))                                   AS [CARGA COMPARTILHADA],
    (C6.C6_QTDVEN - C6.C6_QTDENT)                              AS [QTD PENDENTE],
    CAST(NULL AS VARCHAR(10))                                   AS [PALETE MISTO],
    ISNULL(B2.B2_QATU, 0) - (C6.C6_QTDVEN - C6.C6_QTDENT)    AS [SALDO ESTOQUE],
    C6.C6_PRUNIT                                                AS [PRECO MEDIO],
    (C6.C6_QTDVEN - C6.C6_QTDENT) * C6.C6_PRUNIT              AS [VAL TO DO ITEM],
    (C6.C6_QTDVEN - C6.C6_QTDENT) * B1.B1_PESBRU              AS [PESO BRUTO],
    E4.E4_DESCRI                                                AS [PRAZO],
    A1.A1_CGC                                                   AS [CNPJ]
FROM SC5010 C5
JOIN SC6010 C6
        ON C6.C6_FILIAL = C5.C5_FILIAL
       AND C6.C6_NUM    = C5.C5_NUM
       AND C6.D_E_L_E_T_ = ' '
JOIN SA1010 A1
        ON A1.A1_COD  = C5.C5_CLIENTE
       AND A1.A1_LOJA = C5.C5_LOJACLI
       AND A1.D_E_L_E_T_ = ' '
JOIN SB1010 B1
        ON B1.B1_COD = C6.C6_PRODUTO
       AND B1.D_E_L_E_T_ = ' '
LEFT JOIN SA3010 A3
        ON A3.A3_COD = C5.C5_VEND1
       AND A3.D_E_L_E_T_ = ' '
LEFT JOIN SB2010 B2
        ON B2.B2_FILIAL = C6.C6_FILIAL
       AND B2.B2_COD    = C6.C6_PRODUTO
       AND B2.B2_LOCAL  = C6.C6_LOCAL
       AND B2.D_E_L_E_T_ = ' '
LEFT JOIN SE4010 E4
        ON E4.E4_CODIGO = C5.C5_CONDPAG
       AND E4.D_E_L_E_T_ = ' '
WHERE C5.D_E_L_E_T_ = ' '
  AND (C6.C6_QTDVEN - C6.C6_QTDENT) > 0
  AND C5.C5_CLIENTE <> '000517'
  AND C5.C5_EMISSAO >= '20260101'
  AND A1.A1_EST <> 'EX'
  AND C5.C5_VEND1 NOT IN (
        '000900','000901','0305','EX0018','EX0019','S00035',
        '000000','000450','000902','S00007','S00005','0307'
  )
ORDER BY C5.C5_EMISSAO DESC, C5.C5_NUM, C6.C6_ITEM
"""


SQL_LOOKUP_NF_ENTRADA = """
SELECT DISTINCT
    SF2.F2_DOC AS NF,
    SF1.F1_DOC AS NF_ENTRADA
FROM GWN010 GWN
INNER JOIN GW1010 GW1
        ON GW1.GW1_NRROM = GWN.GWN_NRROM
       AND GW1.D_E_L_E_T_ = ' '
INNER JOIN SF2010 SF2
        ON SF2.F2_DOC = GW1.GW1_NRDC
       AND SF2.F2_SERIE = GW1.GW1_SERDC
       AND SF2.F2_FILIAL = '02'
       AND SF2.D_E_L_E_T_ = ' '
LEFT JOIN SF1010 SF1
        ON SF1.F1_NFORIG = SF2.F2_DOC
       AND SF1.F1_FILIAL = '02'
       AND SF1.D_E_L_E_T_ = ' '
       AND SF1.F1_SERIE = '5'
WHERE GWN.D_E_L_E_T_ = ' '
"""

