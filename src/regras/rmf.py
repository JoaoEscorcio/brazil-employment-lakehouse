"""Regras de negócio do Observatório: fonte única para pipeline, app e testes.

Python puro, sem Spark, para poder ser testado em milissegundos.
"""

# -----------------------------------------------------------------------------
# Região Metropolitana de Fortaleza: 19 municípios (LC Estadual 154/2015).
# Código MTE = código IBGE de 7 dígitos sem o dígito verificador
# (ex.: Fortaleza IBGE 2304400 -> 230440), confirmado no layout oficial.
# -----------------------------------------------------------------------------
RMF_MUNICIPIOS = {
    230440: "Fortaleza", 230100: "Aquiraz", 230350: "Cascavel", 230370: "Caucaia",
    230395: "Chorozinho", 230428: "Eusébio", 230495: "Guaiúba", 230523: "Horizonte",
    230625: "Itaitinga", 230765: "Maracanaú", 230770: "Maranguape", 230960: "Pacajus",
    230970: "Pacatuba", 231085: "Pindoretama", 231240: "São Gonçalo do Amarante",
    231260: "São Luís do Curu", 231025: "Paraipaba", 231020: "Paracuru", 231350: "Trairi",
}

# -----------------------------------------------------------------------------
# Faixas etárias do Observatório (foco em juventude).
# -----------------------------------------------------------------------------
FAIXAS = [(15, 17, "15-17"), (18, 24, "18-24"), (25, 29, "25-29")]


def faixa_etaria(idade: int | None) -> str | None:
    # Idade ausente ou 0 (a RAIS usa 0 para "não informada") não tem faixa.
    if idade is None or idade <= 0:
        return None
    if idade < 15:
        return "<15"
    for inicio, fim, rotulo in FAIXAS:
        if inicio <= idade <= fim:
            return rotulo
    return "30+"


# -----------------------------------------------------------------------------
# Efeito no saldo (Nota Técnica 11/2021 do Novo CAGED): MOV e FOR somam
# normalmente; EXC entra com o sinal invertido (excluir uma admissão reduz o
# saldo, excluir um desligamento aumenta).
# -----------------------------------------------------------------------------
def sinal_efeito(tipo_arquivo: str) -> int:
    return -1 if tipo_arquivo == "EXC" else 1


# -----------------------------------------------------------------------------
# Plausibilidade do salário mensal (achado A5 do perfilamento).
# A régua é o salário mínimo VIGENTE NO MÊS da movimentação: uma admissão de
# 2025 se compara com o mínimo de 2025. Valores oficiais (decretos federais),
# usados também pelo Emprega+: 2025 = R$ 1.518; 2026 = R$ 1.621 (é o valor
# mais frequente no CAGED de jan/2026). Anos anteriores aparecem só em linhas
# FOR/EXC fora da janela do projeto.
# Piso de 0,3 SM preserva contratos de tempo parcial; teto de 30 SM corta erros.
# -----------------------------------------------------------------------------
SALARIO_MINIMO_POR_ANO = {
    2020: 1045.0, 2021: 1100.0, 2022: 1212.0, 2023: 1320.0,
    2024: 1412.0, 2025: 1518.0, 2026: 1621.0,
}
SALARIO_MENSAL_MIN_SM = 0.3
SALARIO_MENSAL_MAX_SM = 30.0
UNIDADE_SALARIO_MENSAL = "5"
