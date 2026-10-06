-- =============================================================================
-- CAMADA GOLD: CAGED (fluxo de emprego formal)
-- Tabelas organizadas pelas PERGUNTAS do painel (docs/perguntas.md), não pela
-- fonte. Escritas em SQL: é a língua comum de analistas, dashboard e Genie.
--
-- Regras que valem para as três tabelas:
--   * Janela móvel: os 12 meses até a competência mais recente do MOV, pelo mês
--     em que o fato ocorreu (competencia_mov). Meses antigos que chegam pelo FOR
--     e pelo EXC ficam de fora (achado A1).
--   * Os 3 meses mais recentes são "preliminares": ainda serão revisados.
--   * Admissão = saldo_movimentacao 1, desligamento = -1, ambos somando o
--     "efeito" (EXC entra com o sinal invertido, NT 11/2021).
-- =============================================================================


-- -----------------------------------------------------------------------------
-- caged_fluxo: admissões, desligamentos e saldo.
-- Grão: mês x município x faixa etária x sexo x raça/cor x seção CNAE x
--       escolaridade x aprendiz x faixa salarial (em salários mínimos do ano).
-- Medidas ADITIVAS: qualquer filtro do painel é só um SUM sobre esta tabela.
-- Atende: /kpis, /evolucao-mensal, /setores e /perfil do Emprega+.
-- -----------------------------------------------------------------------------
CREATE OR REFRESH MATERIALIZED VIEW brazil_employment.gold.caged_fluxo (
  CONSTRAINT saldo_consistente EXPECT (saldo = admissoes - desligamentos)
)
COMMENT 'Fluxo de emprego formal (CLT) na RMF. Grão: mês x município x faixa etária x sexo x raça x seção CNAE x escolaridade x aprendiz x faixa salarial. Medidas aditivas. Janela móvel de 12 meses; os 3 últimos meses são preliminares.'
AS
WITH ultima AS (
  SELECT to_date(CAST(MAX(competencia_mov) AS STRING), 'yyyyMM') AS mes
  FROM brazil_employment.silver.caged_movimentacao
  WHERE origem_arquivo = 'MOV'
),
mov AS (
  SELECT *, to_date(CAST(competencia_mov AS STRING), 'yyyyMM') AS mes
  FROM brazil_employment.silver.caged_movimentacao
)
SELECT
  m.competencia_mov,
  m.mes > add_months(u.mes, -3)                     AS preliminar,
  m.municipio_codigo,
  dm.municipio_nome,
  coalesce(m.faixa_etaria, 'Não informada')         AS faixa_etaria,
  coalesce(m.sexo, 'Não informado')                 AS sexo,
  coalesce(m.raca_cor, 'Não informada')             AS raca_cor,
  m.cnae_secao,
  sec.descricao                                     AS cnae_secao_descricao,
  coalesce(esc.descricao, 'Não informada')          AS escolaridade,
  m.categoria_codigo = '103'                        AS aprendiz,
  CASE
    WHEN m.salario_mensal IS NULL                 THEN 'Sem salário mensal'
    WHEN m.salario_mensal / sm.valor <= 1         THEN '1. Até 1 SM'
    WHEN m.salario_mensal / sm.valor <= 1.5       THEN '2. 1 a 1,5 SM'
    WHEN m.salario_mensal / sm.valor <= 2         THEN '3. 1,5 a 2 SM'
    WHEN m.salario_mensal / sm.valor <= 3         THEN '4. 2 a 3 SM'
    WHEN m.salario_mensal / sm.valor <= 5         THEN '5. 3 a 5 SM'
    ELSE                                               '6. Mais de 5 SM'
  END                                               AS faixa_salarial_sm,
  SUM(CASE WHEN m.saldo_movimentacao = 1  THEN m.efeito ELSE 0 END)  AS admissoes,
  -SUM(CASE WHEN m.saldo_movimentacao = -1 THEN m.efeito ELSE 0 END) AS desligamentos,
  SUM(m.efeito)                                                      AS saldo
FROM mov m
CROSS JOIN ultima u
JOIN brazil_employment.silver.dim_municipio dm
  ON dm.municipio_codigo = m.municipio_codigo
LEFT JOIN brazil_employment.silver.dim_salario_minimo sm
  ON sm.ano = CAST(m.competencia_mov / 100 AS INT)
LEFT JOIN brazil_employment.silver.dim_caged_codigo sec
  ON sec.dominio = 'secao' AND sec.codigo = m.cnae_secao
LEFT JOIN brazil_employment.silver.dim_caged_codigo esc
  ON esc.dominio = 'graudeinstrucao' AND esc.codigo = CAST(m.grau_instrucao_codigo AS STRING)
WHERE m.mes > add_months(u.mes, -12)
GROUP BY ALL;


-- -----------------------------------------------------------------------------
-- caged_ocupacoes: admissões e saldo por ocupação (CBO).
-- Grão: mês x município x faixa etária x sexo x CBO. Medidas aditivas.
-- Atende: /ocupacoes do Emprega+.
-- -----------------------------------------------------------------------------
CREATE OR REFRESH MATERIALIZED VIEW brazil_employment.gold.caged_ocupacoes
COMMENT 'Admissões, desligamentos e saldo por ocupação (CBO 2002) na RMF. Grão: mês x município x faixa etária x sexo x CBO. Medidas aditivas. Mesma janela e mesma regra de preliminar da caged_fluxo.'
AS
WITH ultima AS (
  SELECT to_date(CAST(MAX(competencia_mov) AS STRING), 'yyyyMM') AS mes
  FROM brazil_employment.silver.caged_movimentacao
  WHERE origem_arquivo = 'MOV'
),
mov AS (
  SELECT *, to_date(CAST(competencia_mov AS STRING), 'yyyyMM') AS mes
  FROM brazil_employment.silver.caged_movimentacao
)
SELECT
  m.competencia_mov,
  m.mes > add_months(u.mes, -3)                     AS preliminar,
  m.municipio_codigo,
  dm.municipio_nome,
  coalesce(m.faixa_etaria, 'Não informada')         AS faixa_etaria,
  coalesce(m.sexo, 'Não informado')                 AS sexo,
  m.cbo_codigo,
  coalesce(cbo.descricao, 'CBO ' || m.cbo_codigo)   AS cbo_descricao,
  SUM(CASE WHEN m.saldo_movimentacao = 1  THEN m.efeito ELSE 0 END)  AS admissoes,
  -SUM(CASE WHEN m.saldo_movimentacao = -1 THEN m.efeito ELSE 0 END) AS desligamentos,
  SUM(m.efeito)                                                      AS saldo
FROM mov m
CROSS JOIN ultima u
JOIN brazil_employment.silver.dim_municipio dm
  ON dm.municipio_codigo = m.municipio_codigo
LEFT JOIN brazil_employment.silver.dim_caged_codigo cbo
  ON cbo.dominio = 'cbo2002ocupacao' AND cbo.codigo = m.cbo_codigo
WHERE m.mes > add_months(u.mes, -12)
GROUP BY ALL;


-- -----------------------------------------------------------------------------
-- caged_salario_mediano: salário mediano de admissão.
-- A mediana NÃO é aditiva: a de Fortaleza + a de Caucaia não dão a dos dois.
-- Por isso ela é pré-calculada para cada combinação de filtro do painel:
-- CUBE gera todas as combinações de período x município x faixa x sexo,
-- e as linhas de "total" de cada dimensão aparecem como 'Todos'.
-- Considera só admissões do MOV e do FOR (o EXC cancela, não admite) com
-- salário mensal plausível (achado A5).
-- Atende: o salário de admissão de /kpis (que no Emprega+ era a média).
-- -----------------------------------------------------------------------------
CREATE OR REFRESH MATERIALIZED VIEW brazil_employment.gold.caged_salario_mediano (
  CONSTRAINT amostra_minima EXPECT (admissoes_com_salario >= 30)
)
COMMENT 'Salário mensal MEDIANO de admissão na RMF, pré-calculado para cada combinação de período (mês ou janela de 12 meses), município, faixa etária e sexo. ''Todos'' = sem filtro naquela dimensão. Não somar nem tirar média desta tabela: filtrar a combinação desejada.'
AS
WITH ultima AS (
  SELECT to_date(CAST(MAX(competencia_mov) AS STRING), 'yyyyMM') AS mes
  FROM brazil_employment.silver.caged_movimentacao
  WHERE origem_arquivo = 'MOV'
),
admissoes AS (
  SELECT
    CAST(m.competencia_mov AS STRING)            AS periodo,
    dm.municipio_nome,
    coalesce(m.faixa_etaria, 'Não informada')    AS faixa_etaria,
    coalesce(m.sexo, 'Não informado')            AS sexo,
    m.salario_mensal
  FROM brazil_employment.silver.caged_movimentacao m
  CROSS JOIN ultima u
  JOIN brazil_employment.silver.dim_municipio dm
    ON dm.municipio_codigo = m.municipio_codigo
  WHERE m.saldo_movimentacao = 1
    AND m.origem_arquivo IN ('MOV', 'FOR')
    AND m.salario_mensal IS NOT NULL
    AND to_date(CAST(m.competencia_mov AS STRING), 'yyyyMM') > add_months(u.mes, -12)
)
SELECT
  CASE WHEN grouping(periodo) = 1        THEN 'Últimos 12 meses' ELSE periodo        END AS periodo,
  CASE WHEN grouping(municipio_nome) = 1 THEN 'Todos'            ELSE municipio_nome END AS municipio_nome,
  CASE WHEN grouping(faixa_etaria) = 1   THEN 'Todos'            ELSE faixa_etaria   END AS faixa_etaria,
  CASE WHEN grouping(sexo) = 1           THEN 'Todos'            ELSE sexo           END AS sexo,
  ROUND(percentile_approx(salario_mensal, 0.5), 2) AS salario_mediano,
  COUNT(*)                                         AS admissoes_com_salario
FROM admissoes
GROUP BY CUBE (periodo, municipio_nome, faixa_etaria, sexo);
