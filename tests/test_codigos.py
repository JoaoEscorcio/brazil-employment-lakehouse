"""Dimensões conformadas: cada fonte codifica diferente, mas os rótulos têm que ser os mesmos."""
import pytest

from regras.codigos import RACA_CAGED, RACA_PNAD, RACA_RAIS, SEXO_CAGED, SEXO_PNAD, SEXO_RAIS


def test_sexo_tem_os_mesmos_rotulos_nas_tres_fontes():
    assert set(SEXO_CAGED.values()) == set(SEXO_RAIS.values()) == set(SEXO_PNAD.values()) == {"Homem", "Mulher"}


def test_raca_tem_os_mesmos_rotulos_nas_tres_fontes():
    rotulos = {"Branca", "Preta", "Parda", "Amarela", "Indígena"}
    assert set(RACA_CAGED.values()) == set(RACA_RAIS.values()) == set(RACA_PNAD.values()) == rotulos


@pytest.mark.parametrize(
    "dicionario, codigo, rotulo",
    [
        (SEXO_CAGED, "3", "Mulher"),   # achado A3: mulher é 3 no CAGED...
        (SEXO_RAIS, "2", "Mulher"),    # ...e 2 na RAIS e na PNAD
        (SEXO_PNAD, "2", "Mulher"),
        (RACA_RAIS, "8", "Parda"),
        (RACA_PNAD, "4", "Parda"),
    ],
)
def test_codigos_oficiais(dicionario, codigo, rotulo):
    assert dicionario[codigo] == rotulo


@pytest.mark.parametrize("dicionario", [SEXO_CAGED, RACA_CAGED, SEXO_RAIS, RACA_RAIS, SEXO_PNAD, RACA_PNAD])
def test_nao_identificado_fica_fora_do_dicionario(dicionario):
    # Achado A4: códigos de "não identificado" viram NULL, não uma categoria falsa.
    for codigo in ("9", "99", "-1"):
        assert codigo not in dicionario
