-- Recria a estrutura do Unity Catalog do projeto.
-- IF NOT EXISTS: pode rodar várias vezes sem erro; o que já existe é mantido.

CREATE CATALOG IF NOT EXISTS brazil_employment
  COMMENT 'Youth labor market observatory for the Fortaleza Metropolitan Region (CAGED, RAIS, PNAD). Proof of concept.';

CREATE SCHEMA IF NOT EXISTS brazil_employment.landing
  COMMENT 'Raw files received from the local ingestion (RMF filtered extract).';
CREATE SCHEMA IF NOT EXISTS brazil_employment.bronze
  COMMENT 'Source data as delivered, as Delta tables. No business rules.';
CREATE SCHEMA IF NOT EXISTS brazil_employment.silver
  COMMENT 'Cleaned, typed and harmonized data with business rules applied.';
CREATE SCHEMA IF NOT EXISTS brazil_employment.gold
  COMMENT 'Aggregated indicators ready for dashboards, Genie and the app.';

CREATE VOLUME IF NOT EXISTS brazil_employment.landing.raw
  COMMENT 'Parquet extracts of CAGED, RAIS and PNAD filtered to the 19 RMF municipalities.';
