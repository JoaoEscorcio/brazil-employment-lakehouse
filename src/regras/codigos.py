"""Tradução dos códigos de cada fonte para rótulos comuns (achado A3).

Cada fonte codifica sexo e raça/cor de um jeito (ex.: mulher = 3 no CAGED e 2
na RAIS e na PNAD). Mapear tudo para os mesmos rótulos é o que permite comparar
as fontes: em modelagem dimensional, isso é uma "dimensão conformada".

Códigos de "não identificado" (9, 6, -1...) ficam FORA dos dicionários de
propósito: o mapeamento devolve NULL para eles (achado A4), e eles não viram
uma categoria falsa nos gráficos.
"""

# Layout Novo CAGED (abas sexo e raçacor)
SEXO_CAGED = {"1": "Homem", "3": "Mulher"}
RACA_CAGED = {"1": "Branca", "2": "Preta", "3": "Parda", "4": "Amarela", "5": "Indígena"}

# RAIS_vinculos_layout.xls (aba RAISD - layout)
SEXO_RAIS = {"1": "Homem", "2": "Mulher"}
RACA_RAIS = {"1": "Indígena", "2": "Branca", "4": "Preta", "6": "Amarela", "8": "Parda"}

# Dicionário PNAD Contínua trimestral (V2007 e V2010)
SEXO_PNAD = {"1": "Homem", "2": "Mulher"}
RACA_PNAD = {"1": "Branca", "2": "Preta", "3": "Amarela", "4": "Parda", "5": "Indígena"}
