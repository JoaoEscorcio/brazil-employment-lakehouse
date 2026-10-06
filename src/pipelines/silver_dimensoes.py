# =============================================================================
# CAMADA SILVER: TABELAS DE DIMENSÃO
# Tabelas pequenas de referência (códigos -> nomes), usadas em joins pela
# silver e pela gold. Saem do módulo de regras: mudou a regra, mudou a tabela.
# =============================================================================

from pyspark import pipelines as dp

from regras.rmf import RMF_MUNICIPIOS


# Municípios da RMF: código MTE -> nome. Materialized view porque é uma carga
# pequena e estática (não há arquivos chegando, não faz sentido streaming).
@dp.materialized_view(
    name="brazil_employment.silver.dim_municipio",
    comment="Os 19 municípios da Região Metropolitana de Fortaleza (LC Estadual 154/2015)",
)
def dim_municipio():
    return spark.createDataFrame(
        sorted(RMF_MUNICIPIOS.items()),
        "municipio_codigo INT, municipio_nome STRING",
    )
