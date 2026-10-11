"""Regras gerais do Observatório: municípios, faixa etária, sinal do saldo e salário mínimo."""
from datetime import date

import pytest

from regras.rmf import (
    FAIXAS,
    RMF_MUNICIPIOS,
    SALARIO_MENSAL_MAX_SM,
    SALARIO_MENSAL_MIN_SM,
    SALARIO_MINIMO_POR_ANO,
    faixa_etaria,
    sinal_efeito,
)


def test_rmf_tem_19_municipios_com_codigo_mte_de_6_digitos():
    assert len(RMF_MUNICIPIOS) == 19          # LC Estadual 154/2015
    assert RMF_MUNICIPIOS[230440] == "Fortaleza"
    assert all(100000 <= codigo <= 999999 for codigo in RMF_MUNICIPIOS)
    assert all(str(codigo).startswith("23") for codigo in RMF_MUNICIPIOS)   # 23 = Ceará


@pytest.mark.parametrize(
    "idade, esperado",
    [
        (None, None),      # achado A8: idade ausente não pode cair em "30+"
        (0, None),         # a RAIS usa 0 para "não informada"
        (-1, None),
        (14, "<15"),
        (15, "15-17"), (17, "15-17"),
        (18, "18-24"), (24, "18-24"),
        (25, "25-29"), (29, "25-29"),
        (30, "30+"), (75, "30+"),
    ],
)
def test_faixa_etaria(idade, esperado):
    assert faixa_etaria(idade) == esperado


def test_faixas_jovens_cobrem_15_a_29_sem_buracos():
    idades = [i for inicio, fim, _ in FAIXAS for i in range(inicio, fim + 1)]
    assert idades == list(range(15, 30))


@pytest.mark.parametrize("tipo, sinal", [("MOV", 1), ("FOR", 1), ("EXC", -1)])
def test_exclusao_entra_com_sinal_invertido(tipo, sinal):
    # Nota Técnica 11/2021 do Novo CAGED (achado A10)
    assert sinal_efeito(tipo) == sinal


def test_salario_minimo_cresce_todo_ano():
    anos = sorted(SALARIO_MINIMO_POR_ANO)
    valores = [SALARIO_MINIMO_POR_ANO[a] for a in anos]
    assert anos == list(range(anos[0], anos[-1] + 1))      # sem ano faltando
    assert valores == sorted(valores)


def test_salario_minimo_do_ano_corrente_esta_cadastrado():
    """Alarme anual: em janeiro, o CAGED do ano novo chega e precisa da régua do ano.

    Sem o valor, a silver não consegue avaliar a plausibilidade dos salários
    do ano. Ao falhar: incluir o mínimo oficial do ano em SALARIO_MINIMO_POR_ANO
    (ver docs/manutencao.md).
    """
    assert date.today().year in SALARIO_MINIMO_POR_ANO


def test_faixa_de_plausibilidade_do_salario():
    assert 0 < SALARIO_MENSAL_MIN_SM < 1 < SALARIO_MENSAL_MAX_SM
