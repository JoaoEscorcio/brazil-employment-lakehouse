-- =============================================================================
-- CAMADA GOLD: RAIS (estoque de emprego formal em 31/12)
-- Tabelas organizadas pelas perguntas do painel (docs/perguntas.md).
--
-- Regras que valem para todas:
--   * Estoque = só vínculos ativos em 31/12 (achado A6). Os encerrados no ano
--     só entram na rotatividade.
--   * Porte oficial só para empresas (natureza jurídica elegível, glossário
--     BID/MTE); o resto aparece como 'Não se aplica' (achado A7).
--   * Médias são guardadas como SOMA e CONTAGEM, nunca prontas: assim qualquer
--     filtro do painel calcula a média certa com SUM(soma) / SUM(contagem).
--   * Remuneração ".00" já virou NULL na silver (achado A4): não entra nas médias.
-- =============================================================================


-- -----------------------------------------------------------------------------
-- rais_estoque: o retrato do emprego formal.
-- Grão: município x seção CNAE x porte x estatutário x faixa etária x sexo x
--       raça/cor x escolaridade x faixa de horas x faixa de renda (SM do ano).
-- Atende: /kpis, /escolaridade, /faixa-etaria, /estoque-sexo, /porte-oficial,
--         /porte-atividade, /salario-setor, /faixa-renda, /faixa-horas,
--         /escolaridade-sexo, /tempo-emprego, /salario-hora e /rendimentos.
-- -----------------------------------------------------------------------------
CREATE OR REFRESH MATERIALIZED VIEW brazil_employment.gold.rais_estoque (
  ano_base INT COMMENT 'Ano de referência da RAIS (situação em 31/12 desse ano).',
  municipio_codigo INT COMMENT 'Código do município no MTE (IBGE de 7 dígitos sem o dígito verificador; 230440 = Fortaleza).',
  municipio_nome STRING COMMENT 'Nome do município da Região Metropolitana de Fortaleza (RMF, 19 municípios).',
  cnae_secao STRING COMMENT 'Seção da CNAE 2.0 (letra A a U) da atividade do empregador.',
  cnae_secao_descricao STRING COMMENT 'Nome da seção da CNAE 2.0 (setor de atividade), ex.: Comércio, Construção.',
  porte_oficial STRING COMMENT 'Porte da empresa (Micro, Pequena, Média, Grande) pela metodologia BID/MTE; ''Não se aplica'' para setor público, associações e fundações.',
  estatutario BOOLEAN COMMENT 'true para servidores públicos estatutários (não existem no CAGED).',
  faixa_etaria STRING COMMENT 'Faixa de idade: <15, 15-17, 18-24, 25-29, 30+ ou ''Não informada''. Jovem = faixas 15-17, 18-24 e 25-29.',
  sexo STRING COMMENT 'Homem, Mulher ou ''Não informado'' (rótulo comum às três fontes).',
  raca_cor STRING COMMENT 'Raça/cor: Branca, Preta, Parda, Amarela, Indígena ou ''Não informada''.',
  grau_instrucao_codigo INT COMMENT 'Código do grau de instrução (1 = analfabeto ... 7 = médio completo ... 9 = superior completo, 11 = doutorado).',
  escolaridade STRING COMMENT 'Grau de instrução (ex.: Médio Completo, Superior Completo).',
  faixa_horas STRING COMMENT 'Faixa de horas semanais contratadas.',
  faixa_renda_sm STRING COMMENT 'Faixa da remuneração média do ano em salários mínimos de 2025 (R$ 1.518).',
  vinculos BIGINT COMMENT 'Número de empregos formais (vínculos ativos em 31/12). Aditivo: pode somar.',
  soma_rem_dezembro DOUBLE COMMENT 'Soma das remunerações de dezembro (R$). Salário médio = SUM(soma_rem_dezembro) / SUM(n_rem_dezembro).',
  n_rem_dezembro BIGINT COMMENT 'Vínculos com remuneração de dezembro informada (denominador do salário médio).',
  soma_rem_media DOUBLE COMMENT 'Soma das remunerações médias do ano (R$). Média = SUM(soma_rem_media) / SUM(n_rem_media).',
  n_rem_media BIGINT COMMENT 'Vínculos com remuneração média informada.',
  soma_tempo_emprego DOUBLE COMMENT 'Soma do tempo no emprego (meses). Tempo médio = SUM(soma_tempo_emprego) / SUM(n_tempo_emprego).',
  n_tempo_emprego BIGINT COMMENT 'Vínculos com tempo de emprego informado.',
  soma_rem_media_com_horas DOUBLE COMMENT 'Remuneração média dos vínculos com horas informadas (R$). Salário-hora = SUM(soma_rem_media_com_horas) / SUM(soma_horas_mes).',
  soma_horas_mes DECIMAL(25,3) COMMENT 'Horas contratadas por mês (horas semanais x 4,345), denominador do salário-hora.',
  CONSTRAINT contagens_coerentes EXPECT (n_rem_media <= vinculos AND n_rem_dezembro <= vinculos)
)
COMMENT 'Estoque de vínculos formais ativos em 31/12 na RMF (RAIS). Grão: município x seção CNAE x porte x estatutário x faixa etária x sexo x raça x escolaridade x faixa de horas x faixa de renda. Médias como soma + contagem: média = SUM(soma_*) / SUM(n_*). Inclui servidores estatutários (o CAGED não).'
AS
SELECT
  r.ano_base,
  r.municipio_codigo,
  dm.municipio_nome,
  r.cnae_secao,
  sec.descricao                                          AS cnae_secao_descricao,
  CASE WHEN r.elegivel_porte AND r.porte IS NOT NULL THEN r.porte
       ELSE 'Não se aplica' END                          AS porte_oficial,
  r.estatutario,
  coalesce(r.faixa_etaria, 'Não informada')              AS faixa_etaria,
  coalesce(r.sexo, 'Não informado')                      AS sexo,
  coalesce(r.raca_cor, 'Não informada')                  AS raca_cor,
  r.grau_instrucao_codigo,
  coalesce(esc.descricao, 'Não informada')               AS escolaridade,
  CASE
    WHEN r.horas_contratuais IS NULL OR r.horas_contratuais <= 0 THEN 'Não informada'
    WHEN r.horas_contratuais <= 30 THEN '1. Até 30 horas'
    WHEN r.horas_contratuais <= 40 THEN '2. 31 a 40 horas'
    WHEN r.horas_contratuais <= 44 THEN '3. 41 a 44 horas'
    ELSE                                '4. 45 horas ou mais'
  END                                                    AS faixa_horas,
  CASE
    WHEN r.remuneracao_media_nominal IS NULL       THEN 'Sem remuneração informada'
    WHEN r.remuneracao_media_nominal / sm.valor <= 1   THEN '1. Até 1 SM'
    WHEN r.remuneracao_media_nominal / sm.valor <= 1.5 THEN '2. 1 a 1,5 SM'
    WHEN r.remuneracao_media_nominal / sm.valor <= 2   THEN '3. 1,5 a 2 SM'
    WHEN r.remuneracao_media_nominal / sm.valor <= 3   THEN '4. 2 a 3 SM'
    WHEN r.remuneracao_media_nominal / sm.valor <= 5   THEN '5. 3 a 5 SM'
    ELSE                                                    '6. Mais de 5 SM'
  END                                                    AS faixa_renda_sm,
  COUNT(*)                                               AS vinculos,
  -- salário médio de dezembro (o "salário médio" do painel)
  SUM(r.remuneracao_dezembro_nominal)                    AS soma_rem_dezembro,
  COUNT(r.remuneracao_dezembro_nominal)                  AS n_rem_dezembro,
  -- remuneração média do ano (faixas de renda, salário por setor, razões)
  SUM(r.remuneracao_media_nominal)                       AS soma_rem_media,
  COUNT(r.remuneracao_media_nominal)                     AS n_rem_media,
  -- tempo de emprego (meses)
  SUM(r.tempo_emprego_meses)                             AS soma_tempo_emprego,
  COUNT(r.tempo_emprego_meses)                           AS n_tempo_emprego,
  -- salário por hora = SUM(soma_rem_media_com_horas) / SUM(soma_horas_mes)
  SUM(CASE WHEN r.horas_contratuais > 0 THEN r.remuneracao_media_nominal END) AS soma_rem_media_com_horas,
  SUM(CASE WHEN r.horas_contratuais > 0 AND r.remuneracao_media_nominal IS NOT NULL
           THEN r.horas_contratuais * 4.345 END)        AS soma_horas_mes
FROM brazil_employment.silver.rais_vinculo r
JOIN brazil_employment.silver.dim_municipio dm
  ON dm.municipio_codigo = r.municipio_codigo
LEFT JOIN brazil_employment.silver.dim_caged_codigo sec
  ON sec.dominio = 'secao' AND sec.codigo = r.cnae_secao
-- a RAIS usa a mesma escala de escolaridade do CAGED (1 = analfabeto ... 11 = doutorado)
LEFT JOIN brazil_employment.silver.dim_caged_codigo esc
  ON esc.dominio = 'graudeinstrucao' AND esc.codigo = CAST(r.grau_instrucao_codigo AS STRING)
LEFT JOIN brazil_employment.silver.dim_salario_minimo sm
  ON sm.ano = r.ano_base
WHERE r.ativo_31_12
GROUP BY ALL;


-- -----------------------------------------------------------------------------
-- rais_ocupacoes: estoque e salário por ocupação (CBO) e grande grupo.
-- Grão: município x CBO. Atende: /ocupacoes e /grupamento-ocupacao.
-- -----------------------------------------------------------------------------
CREATE OR REFRESH MATERIALIZED VIEW brazil_employment.gold.rais_ocupacoes (
  ano_base INT COMMENT 'Ano de referência da RAIS (situação em 31/12 desse ano).',
  municipio_codigo INT COMMENT 'Código do município no MTE (IBGE de 7 dígitos sem o dígito verificador; 230440 = Fortaleza).',
  municipio_nome STRING COMMENT 'Nome do município da Região Metropolitana de Fortaleza (RMF, 19 municípios).',
  cbo_codigo STRING COMMENT 'Código da ocupação na CBO 2002 (6 dígitos).',
  cbo_descricao STRING COMMENT 'Nome da ocupação na CBO 2002 (ex.: Vendedor de Comercio Varejista).',
  grande_grupo STRING COMMENT 'Grande grupo ocupacional da CBO (primeiro dígito), ex.: ''5. Trabalhadores dos serviços e vendedores''.',
  vinculos BIGINT COMMENT 'Empregos formais na ocupação (31/12). Aditivo: pode somar.',
  soma_rem_dezembro DOUBLE COMMENT 'Soma das remunerações de dezembro (R$). Salário médio = SUM(soma_rem_dezembro) / SUM(n_rem_dezembro).',
  n_rem_dezembro BIGINT COMMENT 'Vínculos com remuneração de dezembro informada.'
)
COMMENT 'Estoque de vínculos ativos em 31/12 na RMF por ocupação (CBO 2002) e grande grupo ocupacional. Grão: município x CBO. Salário médio de dezembro = SUM(soma_rem_dezembro) / SUM(n_rem_dezembro).'
AS
SELECT
  r.ano_base,
  r.municipio_codigo,
  dm.municipio_nome,
  r.cbo_codigo,
  coalesce(cbo.descricao, 'CBO ' || r.cbo_codigo)       AS cbo_descricao,
  CASE substr(r.cbo_codigo, 1, 1)
    WHEN '0' THEN '0. Forças armadas, policiais e bombeiros militares'
    WHEN '1' THEN '1. Dirigentes e gerentes'
    WHEN '2' THEN '2. Profissionais das ciências e das artes'
    WHEN '3' THEN '3. Técnicos de nível médio'
    WHEN '4' THEN '4. Trabalhadores de serviços administrativos'
    WHEN '5' THEN '5. Trabalhadores dos serviços e vendedores'
    WHEN '6' THEN '6. Trabalhadores agropecuários, florestais e da pesca'
    WHEN '7' THEN '7. Trabalhadores da produção de bens e serviços industriais'
    WHEN '8' THEN '8. Trabalhadores da produção industrial (processos contínuos)'
    WHEN '9' THEN '9. Trabalhadores de reparação e manutenção'
    ELSE          'Não informado'
  END                                                    AS grande_grupo,
  COUNT(*)                                               AS vinculos,
  SUM(r.remuneracao_dezembro_nominal)                    AS soma_rem_dezembro,
  COUNT(r.remuneracao_dezembro_nominal)                  AS n_rem_dezembro
FROM brazil_employment.silver.rais_vinculo r
JOIN brazil_employment.silver.dim_municipio dm
  ON dm.municipio_codigo = r.municipio_codigo
LEFT JOIN brazil_employment.silver.dim_caged_codigo cbo
  ON cbo.dominio = 'cbo2002ocupacao' AND cbo.codigo = r.cbo_codigo
WHERE r.ativo_31_12
GROUP BY ALL;


-- -----------------------------------------------------------------------------
-- rais_indicadores_municipio: indicadores que NÃO se somam (Gini e
-- rotatividade), pré-calculados por município e para a RMF inteira.
-- Atende: /gini e /rotatividade.
-- -----------------------------------------------------------------------------
CREATE OR REFRESH MATERIALIZED VIEW brazil_employment.gold.rais_indicadores_municipio (
  recorte STRING COMMENT 'Município da RMF ou ''RMF'' (região inteira). Ler a linha desejada; não somar.',
  estoque BIGINT COMMENT 'Empregos formais ativos em 31/12.',
  admissoes_rotatividade BIGINT COMMENT 'Admissões no ano consideradas na rotatividade (sem estatutários).',
  desligamentos_rotatividade BIGINT COMMENT 'Desligamentos no ano considerados na rotatividade (sem estatutários, pedidos de demissão, transferências, mortes e aposentadorias).',
  taxa_rotatividade_pct DECIMAL(26,1) COMMENT 'Taxa de rotatividade descontada (DIEESE), em %: min(admissões, desligamentos) / estoque. Não somar.',
  gini DOUBLE COMMENT 'Índice de Gini da remuneração (0 = todos ganham igual, 1 = máxima desigualdade). Não somar.',
  CONSTRAINT gini_entre_0_e_1 EXPECT (gini BETWEEN 0 AND 1)
)
COMMENT 'Indicadores não aditivos da RAIS por município e para a RMF inteira (linha "RMF"): índice de Gini da remuneração média e taxa de rotatividade descontada (metodologia DIEESE). Ler a linha do recorte desejado; não somar.'
AS
WITH vinculos AS (
  SELECT r.*, dm.municipio_nome
  FROM brazil_employment.silver.rais_vinculo r
  JOIN brazil_employment.silver.dim_municipio dm
    ON dm.municipio_codigo = r.municipio_codigo
),
-- Gini: G = 2 * soma(posição x salário) / (n x soma(salário)) - (n + 1) / n,
-- com os salários em ordem crescente. Calculado por município e para a RMF.
salarios AS (
  SELECT municipio_nome AS recorte, remuneracao_media_nominal AS salario
  FROM vinculos WHERE ativo_31_12 AND remuneracao_media_nominal > 0
  UNION ALL
  SELECT 'RMF', remuneracao_media_nominal
  FROM vinculos WHERE ativo_31_12 AND remuneracao_media_nominal > 0
),
ordenados AS (
  SELECT recorte, salario, ROW_NUMBER() OVER (PARTITION BY recorte ORDER BY salario) AS posicao
  FROM salarios
),
gini AS (
  SELECT
    recorte,
    2.0 * SUM(posicao * salario) / (COUNT(*) * SUM(salario)) - (COUNT(*) + 1.0) / COUNT(*) AS gini
  FROM ordenados
  GROUP BY recorte
),
-- Rotatividade DIEESE: min(admissões, desligamentos) / estoque em 31/12.
rotatividade AS (
  SELECT
    coalesce(municipio_nome, 'RMF')                         AS recorte,
    COUNT_IF(admissao_rotatividade)                         AS admissoes_rotatividade,
    COUNT_IF(desligamento_rotatividade)                     AS desligamentos_rotatividade,
    COUNT_IF(ativo_31_12)                                   AS estoque
  FROM vinculos
  GROUP BY GROUPING SETS ((municipio_nome), ())
)
SELECT
  r.recorte,
  r.estoque,
  r.admissoes_rotatividade,
  r.desligamentos_rotatividade,
  ROUND(100.0 * LEAST(r.admissoes_rotatividade, r.desligamentos_rotatividade) / r.estoque, 1) AS taxa_rotatividade_pct,
  ROUND(g.gini, 3)                                          AS gini
FROM rotatividade r
LEFT JOIN gini g ON g.recorte = r.recorte;


-- -----------------------------------------------------------------------------
-- rais_quociente_locacional: em que setores cada município (e a RMF) é
-- especializado, comparado com o Ceará.
-- QL = (vínculos do setor no recorte / vínculos do recorte)
--      / (vínculos do setor no Ceará / vínculos do Ceará).
-- QL > 1: o setor pesa mais no recorte do que no estado.
-- Atende: /quociente-locacional.
-- -----------------------------------------------------------------------------
CREATE OR REFRESH MATERIALIZED VIEW brazil_employment.gold.rais_quociente_locacional (
  recorte STRING COMMENT 'Município da RMF ou ''RMF'' (região inteira).',
  cnae_secao STRING COMMENT 'Seção da CNAE 2.0 (letra A a U) da atividade do empregador.',
  cnae_secao_descricao STRING COMMENT 'Nome da seção da CNAE 2.0 (setor de atividade), ex.: Comércio, Construção.',
  vinculos_setor BIGINT COMMENT 'Empregos formais do setor no recorte.',
  participacao_recorte_pct DECIMAL(27,2) COMMENT 'Peso do setor no emprego do recorte (%).',
  participacao_ceara_pct DECIMAL(27,2) COMMENT 'Peso do setor no emprego do Ceará (%).',
  quociente_locacional DOUBLE COMMENT 'Quociente locacional: peso do setor no recorte / peso no Ceará. Acima de 1 = recorte especializado no setor.'
)
COMMENT 'Quociente locacional por seção CNAE, de cada município da RMF e da RMF inteira (linha "RMF"), em relação ao Ceará (RAIS, vínculos ativos em 31/12). QL > 1 = setor mais concentrado no recorte do que no estado.'
AS
WITH ceara AS (
  SELECT municipio_codigo, cnae_secao, vinculos_ativos
  FROM brazil_employment.silver.rais_estoque_ceara_secao
  WHERE cnae_secao IS NOT NULL
),
estado AS (
  SELECT cnae_secao, SUM(vinculos_ativos) AS setor_estado, SUM(SUM(vinculos_ativos)) OVER () AS total_estado
  FROM ceara GROUP BY cnae_secao
),
recortes AS (
  SELECT coalesce(dm.municipio_nome, 'RMF') AS recorte, c.cnae_secao, SUM(c.vinculos_ativos) AS setor_recorte
  FROM ceara c
  JOIN brazil_employment.silver.dim_municipio dm
    ON dm.municipio_codigo = c.municipio_codigo
  GROUP BY GROUPING SETS ((dm.municipio_nome, c.cnae_secao), (c.cnae_secao))
),
totais AS (
  SELECT recorte, cnae_secao, setor_recorte, SUM(setor_recorte) OVER (PARTITION BY recorte) AS total_recorte
  FROM recortes
)
SELECT
  t.recorte,
  t.cnae_secao,
  sec.descricao                                             AS cnae_secao_descricao,
  t.setor_recorte                                           AS vinculos_setor,
  ROUND(100.0 * t.setor_recorte / t.total_recorte, 2)       AS participacao_recorte_pct,
  ROUND(100.0 * e.setor_estado / e.total_estado, 2)         AS participacao_ceara_pct,
  ROUND((t.setor_recorte / t.total_recorte) / (e.setor_estado / e.total_estado), 2) AS quociente_locacional
FROM totais t
JOIN estado e ON e.cnae_secao = t.cnae_secao
LEFT JOIN brazil_employment.silver.dim_caged_codigo sec
  ON sec.dominio = 'secao' AND sec.codigo = t.cnae_secao;
