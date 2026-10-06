# =============================================================================
# CAMADA SILVER: TABELAS DE DIMENSÃO
# Tabelas pequenas de referência (códigos -> nomes), usadas em joins pela
# silver e pela gold. Saem do módulo de regras ou dos dicionários oficiais:
# mudou a regra ou o dicionário, mudou a tabela.
# =============================================================================

from pyspark import pipelines as dp
from pyspark.sql import functions as F

from regras.rais import SUBSETOR_AGRO_COMERCIO_SERVICOS, SUBSETOR_INDUSTRIA_CONSTRUCAO, porte
from regras.rmf import RMF_MUNICIPIOS, SALARIO_MINIMO_POR_ANO

REFERENCIA = "/Volumes/brazil_employment/landing/raw/referencia"


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


# Dicionários oficiais do CAGED (sexo, raça/cor, escolaridade, tipo de
# movimentação, unidade do salário, categoria, seção CNAE), num formato só:
# uma linha por (dominio, codigo). Vêm dos CSVs exportados do layout oficial
# do MTE na carga histórica; o domínio sai do nome do arquivo.
@dp.materialized_view(
    name="brazil_employment.silver.dim_caged_codigo",
    comment="Dicionários oficiais do Novo CAGED: dominio + codigo -> descricao",
)
def dim_caged_codigo():
    return (
        spark.read.option("header", True).csv(f"{REFERENCIA}/caged_*.csv")
        .withColumn("dominio", F.regexp_extract(F.col("_metadata.file_name"), r"caged_(.*)\.csv", 1))
        .select(
            "dominio",
            # A CBO tem 6 dígitos e começa com 0 nos militares (010105). O layout
            # oficial é um Excel que guarda o código como número e perde o zero
            # (10105); sem repor, o join com o CAGED falha para 28 ocupações.
            F.when(F.col("dominio") == "cbo2002ocupacao", F.lpad("codigo", 6, "0"))
             .otherwise(F.col("codigo")).alias("codigo"),
            F.col("descricao"),
        )
    )


# CNAE 2.0: classe (5 dígitos) -> seção (letra). A RAIS só traz a classe; o
# CAGED já traz a seção. Crosswalk oficial do IBGE/Concla, guardado em JSON.
@dp.materialized_view(
    name="brazil_employment.silver.dim_cnae_classe",
    comment="CNAE 2.0: classe -> seção (crosswalk oficial IBGE/Concla)",
)
def dim_cnae_classe():
    return (
        spark.read.option("wholetext", True).text(f"{REFERENCIA}/cnae_classe_secao.json")
        .select(F.explode(F.from_json("value", "map<string,string>")).alias("classe", "secao"))
        .select(F.col("classe").cast("int").alias("cnae_classe"), F.col("secao").alias("cnae_secao"))
    )


# Porte de empresa (metodologia BID/MTE): subsetor IBGE x tamanho do
# estabelecimento -> porte. Gerada a partir de regras/rais.py; a RAIS faz
# JOIN com ela (mais rápido que uma UDF e aparece no lineage).
@dp.materialized_view(
    name="brazil_employment.silver.dim_porte",
    comment="Porte de empresa: subsetor IBGE x TAMESTAB -> Micro/Pequena/Média/Grande (BID/MTE)",
)
def dim_porte():
    subsetores = sorted(SUBSETOR_INDUSTRIA_CONSTRUCAO | SUBSETOR_AGRO_COMERCIO_SERVICOS)
    linhas = [(s, t, porte(s, t)) for s in subsetores for t in range(1, 11)]
    return spark.createDataFrame(
        linhas, "ibge_subsetor_codigo INT, tamanho_estabelecimento_codigo INT, porte STRING"
    )


# Deflatores oficiais da PNAD (IBGE) para o Ceará: rendimento real =
# rendimento nominal x deflator. Base = trimestre mais recente do arquivo.
@dp.materialized_view(
    name="brazil_employment.silver.dim_pnad_deflator",
    comment="Deflatores trimestrais da PNAD Contínua para o Ceará (IBGE): rendimento real = nominal x deflator",
)
def dim_pnad_deflator():
    return (
        spark.read.option("header", True).csv(f"{REFERENCIA}/pnad_deflator_ceara.csv")
        .select(
            F.col("ano").cast("int").alias("ano"),
            F.col("trimestre").cast("int").alias("trimestre"),
            F.col("deflator_habitual").cast("double").alias("deflator_habitual"),
            F.col("deflator_efetivo").cast("double").alias("deflator_efetivo"),
        )
    )


# Salário mínimo nacional por ano: régua das faixas salariais em "salários
# mínimos" da gold. Sai de regras/rmf.py, a mesma usada na plausibilidade (A5).
@dp.materialized_view(
    name="brazil_employment.silver.dim_salario_minimo",
    comment="Salário mínimo nacional por ano (R$), régua das faixas em salários mínimos",
)
def dim_salario_minimo():
    return spark.createDataFrame(
        sorted(SALARIO_MINIMO_POR_ANO.items()), "ano INT, valor DOUBLE"
    )
