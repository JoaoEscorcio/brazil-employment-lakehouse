"""Regras da RAIS: porte de empresa pela metodologia oficial do painel BID/MTE.

A RAIS pública não identifica a empresa, então o porte é derivado de duas
colunas: o subsetor IBGE (indústria/construção x comércio/serviços/agro) e o
tamanho do estabelecimento (TAMESTAB, 10 faixas de número de empregados).
Os limites de porte são diferentes para cada grupo de subsetor.
"""

# Subsetor IBGE: 01-15 = Indústria e Construção; 16-23 e 25 = Agropecuária,
# Comércio e Serviços; 24 = Administração pública direta e autárquica.
# O 24 fica fora do porte de propósito: órgão público não é empresa, então não
# tem porte (Micro/Pequena/...). Confirmado nos dados: os 351.914 vínculos do
# subsetor 24 na RMF têm natureza jurídica pública (1xxx) e CNAE da seção O.
SUBSETOR_INDUSTRIA_CONSTRUCAO = set(range(1, 16))
SUBSETOR_AGRO_COMERCIO_SERVICOS = {16, 17, 18, 19, 20, 21, 22, 23, 25}
SUBSETOR_ADMINISTRACAO_PUBLICA = 24

# TAMESTAB: 1=zero, 2=1-4, 3=5-9, 4=10-19, 5=20-49, 6=50-99, 7=100-249,
# 8=250-499, 9=500-999, 10=1000+ empregados.
TAMESTAB_PORTE_INDUSTRIA = {1: "Micro", 2: "Micro", 3: "Micro", 4: "Micro",
                            5: "Pequena", 6: "Pequena", 7: "Média", 8: "Média",
                            9: "Grande", 10: "Grande"}
TAMESTAB_PORTE_SERVICOS = {1: "Micro", 2: "Micro", 3: "Micro", 4: "Pequena",
                           5: "Pequena", 6: "Média", 7: "Grande", 8: "Grande",
                           9: "Grande", 10: "Grande"}


def porte(subsetor: int | None, tamestab: int | None) -> str | None:
    if subsetor in SUBSETOR_INDUSTRIA_CONSTRUCAO:
        return TAMESTAB_PORTE_INDUSTRIA.get(tamestab)
    if subsetor in SUBSETOR_AGRO_COMERCIO_SERVICOS:
        return TAMESTAB_PORTE_SERVICOS.get(tamestab)
    return None
