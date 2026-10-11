"""Informalidade pela definição oficial (Glossário BID/MTE)."""
import pytest

from regras.pnad import informal


@pytest.mark.parametrize(
    "posicao, cnpj, esperado",
    [
        (1, None, False),   # privado com carteira
        (2, None, True),    # privado sem carteira
        (4, None, True),    # doméstico sem carteira
        (7, None, False),   # militar / estatutário
        (8, 1, False),      # empregador com CNPJ
        (8, 2, True),       # empregador sem CNPJ
        (9, 1, False),      # conta própria com CNPJ
        (9, 2, True),       # conta própria sem CNPJ
        (10, None, True),   # familiar auxiliar: sempre informal
        (None, None, None), # não ocupado: a pergunta não se aplica
    ],
)
def test_informal(posicao, cnpj, esperado):
    assert informal(posicao, cnpj) is esperado
