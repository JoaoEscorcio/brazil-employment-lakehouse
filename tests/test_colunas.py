"""Funções Spark de conversão de colunas (src/comum/colunas.py).

Pulados quando não há Spark (ver conftest.py); rodam na CI e no Databricks.
"""
import pytest

pytest.importorskip("pyspark")

from comum.colunas import decimal_ponto, decimal_virgula, faixa_etaria_col, inteiro, traduzir  # noqa: E402
from regras.codigos import SEXO_CAGED  # noqa: E402
from regras.rmf import faixa_etaria  # noqa: E402


def _valores(spark, valores, expressao, tipo="string"):
    df = spark.createDataFrame([(v,) for v in valores], f"v {tipo}")
    return [linha[0] for linha in df.select(expressao).collect()]


def test_inteiro_tira_espacos_e_nao_quebra(spark):
    # Achado A2: a RAIS traz " 84116"; texto inválido vira NULL em vez de derrubar o pipeline.
    assert _valores(spark, [" 84116", "12", "abc", None], inteiro("v")) == [84116, 12, None, None]


def test_decimais(spark):
    assert _valores(spark, ["1628,51", "x"], decimal_virgula("v")) == [1628.51, None]     # CAGED
    assert _valores(spark, ["000411.81", "1518.00"], decimal_ponto("v")) == [411.81, 1518.0]  # PNAD, RAIS


def test_traduzir_codigo_desconhecido_vira_nulo(spark):
    assert _valores(spark, ["1", "3", "9"], traduzir("v", SEXO_CAGED)) == ["Homem", "Mulher", None]


def test_faixa_etaria_spark_igual_a_python(spark):
    # A mesma regra existe em Python (testes, app) e em Spark (pipeline): as duas têm que concordar.
    # Foi uma divergência aqui que gerou o achado A8 (idade nula caindo em "30+").
    idades = [None, -1, 0, 10, 14, 15, 17, 18, 24, 25, 29, 30, 75]
    from pyspark.sql import functions as F

    spark_resultado = _valores(spark, idades, faixa_etaria_col(F.col("v")), tipo="int")
    assert spark_resultado == [faixa_etaria(i) for i in idades]
