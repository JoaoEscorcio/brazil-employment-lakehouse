"""Configuração comum dos testes.

As regras de negócio ficam em src/ e são importadas como no pipeline
(`from regras.rmf import ...`), por isso src/ entra no caminho de import.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


@pytest.fixture(scope="session")
def spark():
    """Sessão Spark para os testes de src/comum.

    No Databricks reaproveita a sessão ativa; fora dele cria uma local.
    Sem PySpark ou sem Java (ex.: notebook pessoal), os testes que pedem
    esta fixture são pulados, não falham. Na CI eles rodam.
    """
    pytest.importorskip("pyspark")
    from pyspark.sql import SparkSession

    try:
        return SparkSession.getActiveSession() or (
            SparkSession.builder.master("local[1]").appName("testes").getOrCreate()
        )
    except Exception as erro:  # Java ausente, por exemplo
        pytest.skip(f"Spark indisponível: {erro}")
