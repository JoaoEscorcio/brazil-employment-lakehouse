"""Porte de empresa e rotatividade pela metodologia do painel BID/MTE."""
import pytest

from regras.rais import (
    MOTIVOS_FORA_DA_ROTATIVIDADE,
    NATUREZAS_PORTE_ELEGIVEIS,
    SUBSETOR_ADMINISTRACAO_PUBLICA,
    SUBSETOR_AGRO_COMERCIO_SERVICOS,
    SUBSETOR_INDUSTRIA_CONSTRUCAO,
    TAMESTAB_PORTE_INDUSTRIA,
    TAMESTAB_PORTE_SERVICOS,
    TIPOS_VINCULO_ESTATUTARIO,
    porte,
)


@pytest.mark.parametrize(
    "subsetor, tamestab, esperado",
    [
        (5, 4, "Micro"),       # indústria com 10-19 empregados ainda é micro
        (19, 4, "Pequena"),    # serviços com 10-19 já é pequena: limites diferentes
        (5, 7, "Média"),       # indústria 100-249
        (19, 7, "Grande"),     # serviços 100-249
        (10, 10, "Grande"),
        (24, 10, None),        # achado A7: administração pública não tem porte
        (None, 5, None),
        (19, None, None),
    ],
)
def test_porte(subsetor, tamestab, esperado):
    assert porte(subsetor, tamestab) == esperado


@pytest.mark.parametrize("tabela", [TAMESTAB_PORTE_INDUSTRIA, TAMESTAB_PORTE_SERVICOS])
def test_todas_as_faixas_de_tamanho_tem_porte(tabela):
    assert set(tabela) == set(range(1, 11))


def test_subsetores_nao_se_sobrepoem():
    assert not SUBSETOR_INDUSTRIA_CONSTRUCAO & SUBSETOR_AGRO_COMERCIO_SERVICOS
    assert SUBSETOR_ADMINISTRACAO_PUBLICA not in SUBSETOR_INDUSTRIA_CONSTRUCAO | SUBSETOR_AGRO_COMERCIO_SERVICOS


def test_porte_so_para_empresas():
    # Sociedades empresárias (2xxx) e empresários / PF empregadoras (4xxx).
    assert all(str(n)[0] in "24" and len(str(n)) == 4 for n in NATUREZAS_PORTE_ELEGIVEIS)


def test_rotatividade_exclui_pedido_de_demissao_e_estatutarios():
    assert 21 in MOTIVOS_FORA_DA_ROTATIVIDADE           # pedido de demissão
    assert 11 not in MOTIVOS_FORA_DA_ROTATIVIDADE       # demissão sem justa causa conta
    assert TIPOS_VINCULO_ESTATUTARIO == {30, 31, 35}
