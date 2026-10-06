"""Regras da PNAD Contínua: informalidade pela definição oficial.

Glossário de Indicadores do Painel da Rede de Observatórios do Trabalho
(BID/MTE): informal = união de 4 grupos de ocupados.
Posição na ocupação (VD4009): 01 privado com carteira, 02 privado sem carteira,
03 doméstico com carteira, 04 doméstico sem carteira, 05 público com carteira,
06 público sem carteira, 07 militar/estatutário, 08 empregador,
09 conta própria, 10 trabalhador familiar auxiliar.
"""

POSICAO_SEM_CARTEIRA = {2, 4}          # empregado privado e doméstico sem carteira
POSICAO_DEPENDE_DE_CNPJ = {8, 9}       # empregador e conta própria: informais se sem CNPJ
POSICAO_FAMILIAR_AUXILIAR = {10}       # sempre informal
NEGOCIO_SEM_CNPJ = 2                   # V4019: 1 = tem CNPJ, 2 = não tem


def informal(posicao: int | None, negocio_cnpj: int | None) -> bool | None:
    if posicao is None:                # não ocupado: a pergunta não se aplica
        return None
    return (
        posicao in POSICAO_SEM_CARTEIRA
        or (posicao in POSICAO_DEPENDE_DE_CNPJ and negocio_cnpj == NEGOCIO_SEM_CNPJ)
        or posicao in POSICAO_FAMILIAR_AUXILIAR
    )
