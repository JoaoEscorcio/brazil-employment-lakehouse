-- Catálogo do ambiente de desenvolvimento (dev).
-- O mesmo código do pipeline grava aqui quando roda o pipeline de dev, porque
-- o catálogo vem da configuração do pipeline, não do código.
-- Sem schema landing: o dev LÊ a landing do prod (arquivos brutos, só leitura
-- para o pipeline) e grava apenas bronze, silver e gold próprias.
-- IF NOT EXISTS: pode rodar várias vezes sem erro.

CREATE CATALOG IF NOT EXISTS brazil_employment_dev
  COMMENT 'Development environment of the youth labor market observatory. Safe to drop and rebuild from the prod landing.';

CREATE SCHEMA IF NOT EXISTS brazil_employment_dev.bronze
  COMMENT 'Dev copy of bronze. Built by the dev pipeline from the prod landing.';
CREATE SCHEMA IF NOT EXISTS brazil_employment_dev.silver
  COMMENT 'Dev copy of silver.';
CREATE SCHEMA IF NOT EXISTS brazil_employment_dev.gold
  COMMENT 'Dev copy of gold.';
