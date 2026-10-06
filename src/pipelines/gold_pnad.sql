-- =============================================================================
-- CAMADA GOLD: PNAD CONTÍNUA (contexto do mercado de trabalho, por trimestre)
-- Tabelas organizadas pelas perguntas do painel (docs/perguntas.md).
--
-- Regras que valem para todas:
--   * A PNAD é uma AMOSTRA: toda contagem de pessoas é uma soma de "peso".
--   * As TAXAS não se somam, mas as SOMAS DE PESO sim (desocupados de Fortaleza
--     + desocupados do resto da RMF = desocupados da RMF). Por isso a tabela base
--     guarda os componentes, e a de indicadores calcula as taxas a partir dela.
--   * Fórmulas do Glossário de Indicadores do painel BID/MTE, as mesmas do Emprega+.
--   * Amostra pequena: com ~250 desocupados entrevistados por trimestre na RMF,
--     recortes finos não são confiáveis. As colunas *_amostra mostram quantas
--     pessoas foram de fato entrevistadas em cada linha (achado A6).
-- =============================================================================


-- -----------------------------------------------------------------------------
-- pnad_mercado_trabalho: os componentes (somas de peso), aditivos.
-- Grão: trimestre x área (Fortaleza / demais municípios da RMF) x sexo x
--       faixa etária x grupo de raça/cor.
-- Qualquer taxa = SUM(componente) / SUM(componente) sobre o filtro desejado.
-- -----------------------------------------------------------------------------
CREATE OR REFRESH MATERIALIZED VIEW brazil_employment.gold.pnad_mercado_trabalho (
  CONSTRAINT ocupados_mais_desocupados_igual_forca EXPECT (
    abs(coalesce(ocupados, 0) + coalesce(desocupados, 0) - coalesce(forca_trabalho, 0)) < 1
  )
)
COMMENT 'Componentes da PNAD Contínua na RMF (somas de peso = pessoas estimadas). Grão: trimestre x área (Fortaleza / demais municípios) x sexo x faixa etária x grupo de raça. Aditivos: some os componentes do recorte e divida para obter qualquer taxa. Colunas *_amostra = pessoas entrevistadas (confiabilidade).'
AS
SELECT
  p.ano,
  p.trimestre,
  CASE WHEN p.mora_em_fortaleza THEN 'Fortaleza' ELSE 'Demais municípios da RMF' END AS area,
  coalesce(p.sexo, 'Não informado')                     AS sexo,
  coalesce(p.faixa_etaria, 'Não informada')             AS faixa_etaria,
  CASE
    WHEN p.raca_cor = 'Branca'            THEN 'Branca'
    WHEN p.raca_cor IN ('Preta', 'Parda') THEN 'Negra (preta ou parda)'
    ELSE                                       'Outras ou ignorada'
  END                                                   AS raca_grupo,
  -- tamanho da amostra
  COUNT(*)                                              AS pessoas_amostra,
  COUNT_IF(p.condicao_ocupacao = 2)                     AS desocupados_amostra,
  -- população e força de trabalho
  SUM(p.peso)                                           AS populacao,
  SUM(CASE WHEN p.idade >= 14 THEN p.peso END)          AS idade_trabalhar,
  SUM(CASE WHEN p.condicao_forca_trabalho = 1 THEN p.peso END) AS forca_trabalho,
  SUM(CASE WHEN p.condicao_ocupacao = 1 THEN p.peso END)       AS ocupados,
  SUM(CASE WHEN p.condicao_ocupacao = 2 THEN p.peso END)       AS desocupados,
  -- qualidade da ocupação
  SUM(CASE WHEN p.informal THEN p.peso END)             AS informais,
  SUM(CASE WHEN p.condicao_ocupacao = 1 AND p.posicao_ocupacao_codigo = 9 THEN p.peso END) AS conta_propria,
  SUM(CASE WHEN p.contribui_previdencia THEN p.peso END) AS contribuintes_previdencia,
  -- subutilização
  SUM(CASE WHEN p.subocupado THEN p.peso END)           AS subocupados,
  SUM(CASE WHEN p.forca_trabalho_potencial = 1 THEN p.peso END) AS forca_potencial,
  SUM(CASE WHEN p.desalentado THEN p.peso END)          AS desalentados,
  -- rendimento habitual dos ocupados: média = soma_renda / peso_renda
  SUM(CASE WHEN p.condicao_ocupacao = 1 THEN p.rendimento_habitual * p.peso END) AS soma_renda,
  SUM(CASE WHEN p.condicao_ocupacao = 1 AND p.rendimento_habitual IS NOT NULL THEN p.peso END) AS peso_renda,
  -- o mesmo em valores reais (IPCA, base = trimestre mais recente do deflator)
  SUM(CASE WHEN p.condicao_ocupacao = 1 THEN p.rendimento_habitual * p.peso * d.deflator_habitual END) AS soma_renda_real,
  -- rendimento de informais e formais (razão informal/formal)
  SUM(CASE WHEN p.condicao_ocupacao = 1 AND p.informal THEN p.rendimento_habitual * p.peso END) AS soma_renda_informal,
  SUM(CASE WHEN p.condicao_ocupacao = 1 AND p.informal AND p.rendimento_habitual IS NOT NULL THEN p.peso END) AS peso_renda_informal,
  SUM(CASE WHEN p.condicao_ocupacao = 1 AND NOT coalesce(p.informal, false) THEN p.rendimento_habitual * p.peso END) AS soma_renda_formal,
  SUM(CASE WHEN p.condicao_ocupacao = 1 AND NOT coalesce(p.informal, false) AND p.rendimento_habitual IS NOT NULL THEN p.peso END) AS peso_renda_formal
FROM brazil_employment.silver.pnad_pessoa p
LEFT JOIN brazil_employment.silver.dim_pnad_deflator d
  ON d.ano = p.ano AND d.trimestre = p.trimestre
GROUP BY ALL;


-- -----------------------------------------------------------------------------
-- pnad_indicadores: as taxas prontas, para os recortes do painel.
-- Recorte: RMF ou só Fortaleza. Sexo: Todos / Homem / Mulher.
-- Público: Todos / Jovens (15 a 29 anos).
-- Atende: /kpis, /populacao, /informalidade, /informalidade-conta-propria,
--         /contribuicao-previdenciaria, /subocupacao-desalento, /rendimentos,
--         /evolucao e /evolucao-rendimento do Emprega+.
-- -----------------------------------------------------------------------------
CREATE OR REFRESH MATERIALIZED VIEW brazil_employment.gold.pnad_indicadores (
  CONSTRAINT taxa_desocupacao_valida EXPECT (taxa_desocupacao_pct BETWEEN 0 AND 100)
)
COMMENT 'Indicadores da PNAD Contínua prontos, por trimestre, recorte (RMF / Fortaleza), sexo e público (Todos / Jovens 15-29). Fórmulas do Glossário BID/MTE. Colunas pessoas_* = população estimada (soma de pesos); amostra_suficiente = false quando menos de 30 desocupados foram entrevistados (estimativa pouco confiável).'
AS
WITH base AS (
  SELECT 'RMF' AS recorte, * FROM brazil_employment.gold.pnad_mercado_trabalho
  UNION ALL
  SELECT 'Fortaleza', * FROM brazil_employment.gold.pnad_mercado_trabalho WHERE area = 'Fortaleza'
),
publico AS (
  SELECT *,
    CASE WHEN faixa_etaria IN ('15-17', '18-24', '25-29') THEN 'Jovens (15 a 29 anos)' ELSE 'Demais' END AS grupo
  FROM base
),
agregado AS (
  SELECT
    recorte, ano, trimestre,
    CASE WHEN grouping(sexo) = 1  THEN 'Todos' ELSE sexo  END AS sexo,
    CASE WHEN grouping(grupo) = 1 THEN 'Todos' ELSE grupo END AS publico,
    SUM(pessoas_amostra)        AS pessoas_amostra,
    SUM(desocupados_amostra)    AS desocupados_amostra,
    SUM(idade_trabalhar)        AS idade_trabalhar,
    SUM(forca_trabalho)         AS forca_trabalho,
    SUM(ocupados)               AS ocupados,
    SUM(desocupados)            AS desocupados,
    SUM(informais)              AS informais,
    SUM(conta_propria)          AS conta_propria,
    SUM(contribuintes_previdencia) AS contribuintes_previdencia,
    SUM(subocupados)            AS subocupados,
    SUM(forca_potencial)        AS forca_potencial,
    SUM(desalentados)           AS desalentados,
    SUM(soma_renda)             AS soma_renda,
    SUM(peso_renda)             AS peso_renda,
    SUM(soma_renda_real)        AS soma_renda_real,
    SUM(soma_renda_informal)    AS soma_renda_informal,
    SUM(peso_renda_informal)    AS peso_renda_informal,
    SUM(soma_renda_formal)      AS soma_renda_formal,
    SUM(peso_renda_formal)      AS peso_renda_formal,
    SUM(CASE WHEN sexo = 'Homem'  THEN soma_renda END) / SUM(CASE WHEN sexo = 'Homem'  THEN peso_renda END) AS renda_homem,
    SUM(CASE WHEN sexo = 'Mulher' THEN soma_renda END) / SUM(CASE WHEN sexo = 'Mulher' THEN peso_renda END) AS renda_mulher,
    SUM(CASE WHEN raca_grupo = 'Branca' THEN soma_renda END)
      / SUM(CASE WHEN raca_grupo = 'Branca' THEN peso_renda END)                 AS renda_branca,
    SUM(CASE WHEN raca_grupo = 'Negra (preta ou parda)' THEN soma_renda END)
      / SUM(CASE WHEN raca_grupo = 'Negra (preta ou parda)' THEN peso_renda END) AS renda_negra
  FROM publico
  GROUP BY recorte, ano, trimestre, GROUPING SETS ((), (sexo), (grupo), (sexo, grupo))
)
SELECT
  recorte, ano, trimestre, sexo, publico,
  pessoas_amostra,
  desocupados_amostra,
  ROUND(idade_trabalhar)                                          AS pessoas_idade_trabalhar,
  ROUND(forca_trabalho)                                           AS pessoas_forca_trabalho,
  ROUND(ocupados)                                                 AS pessoas_ocupadas,
  ROUND(desocupados)                                              AS pessoas_desocupadas,
  ROUND(100 * desocupados / forca_trabalho, 1)                    AS taxa_desocupacao_pct,
  ROUND(100 * forca_trabalho / idade_trabalhar, 1)                AS taxa_participacao_pct,
  ROUND(100 * ocupados / idade_trabalhar, 1)                      AS nivel_ocupacao_pct,
  ROUND(100 * informais / ocupados, 1)                            AS taxa_informalidade_pct,
  ROUND(100 * conta_propria / ocupados, 1)                        AS conta_propria_pct,
  ROUND(100 * contribuintes_previdencia / ocupados, 1)            AS contribuicao_previdencia_pct,
  ROUND(100 * subocupados / ocupados, 1)                          AS taxa_subocupacao_pct,
  ROUND(100 * desalentados / forca_potencial, 1)                  AS taxa_desalento_pct,
  ROUND(100 * (desocupados + subocupados + forca_potencial)
            / (forca_trabalho + forca_potencial), 1)              AS taxa_subutilizacao_pct,
  ROUND(soma_renda / peso_renda, 2)                               AS renda_media_habitual,
  ROUND(soma_renda_real / peso_renda, 2)                          AS renda_media_real,
  ROUND(100 * renda_mulher / renda_homem, 1)                      AS razao_renda_mulher_homem_pct,
  ROUND(100 * renda_negra / renda_branca, 1)                      AS razao_renda_negra_branca_pct,
  ROUND(100 * (soma_renda_informal / peso_renda_informal)
            / (soma_renda_formal / peso_renda_formal), 1)         AS razao_renda_informal_formal_pct,
  desocupados_amostra >= 30                                       AS amostra_suficiente
FROM agregado;


-- -----------------------------------------------------------------------------
-- pnad_posicao_ocupacao: que tipo de trabalho as pessoas ocupadas têm.
-- Grão: trimestre x recorte (RMF / Fortaleza) x posição na ocupação (VD4009).
-- Atende: /categoria-ocupacao.
-- -----------------------------------------------------------------------------
CREATE OR REFRESH MATERIALIZED VIEW brazil_employment.gold.pnad_posicao_ocupacao
COMMENT 'Pessoas ocupadas por posição na ocupação (PNAD VD4009), por trimestre e recorte (RMF / Fortaleza). pessoas = soma de peso; pessoas_amostra = entrevistados.'
AS
WITH ocupados AS (
  SELECT 'RMF' AS recorte, * FROM brazil_employment.silver.pnad_pessoa WHERE condicao_ocupacao = 1
  UNION ALL
  SELECT 'Fortaleza', * FROM brazil_employment.silver.pnad_pessoa WHERE condicao_ocupacao = 1 AND mora_em_fortaleza
)
SELECT
  recorte, ano, trimestre,
  posicao_ocupacao_codigo,
  CASE posicao_ocupacao_codigo
    WHEN 1  THEN 'Empregado no setor privado com carteira'
    WHEN 2  THEN 'Empregado no setor privado sem carteira'
    WHEN 3  THEN 'Trabalhador doméstico com carteira'
    WHEN 4  THEN 'Trabalhador doméstico sem carteira'
    WHEN 5  THEN 'Empregado no setor público com carteira'
    WHEN 6  THEN 'Empregado no setor público sem carteira'
    WHEN 7  THEN 'Militar e servidor estatutário'
    WHEN 8  THEN 'Empregador'
    WHEN 9  THEN 'Conta própria'
    WHEN 10 THEN 'Trabalhador familiar auxiliar'
    ELSE         'Não informada'
  END                                AS posicao_ocupacao,
  ROUND(SUM(peso))                   AS pessoas,
  COUNT(*)                           AS pessoas_amostra
FROM ocupados
GROUP BY ALL;
