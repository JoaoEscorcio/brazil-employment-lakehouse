"""Funções de conversão de colunas usadas pela silver das três fontes.

Separadas de regras/ porque dependem do Spark; regras/ é Python puro.
"""

from pyspark.sql import functions as F

from regras.rmf import FAIXAS


# A2: números como texto. trim() porque a RAIS traz espaços à esquerda
# (" 84116"). try_cast devolve NULL em vez de quebrar o pipeline; quem
# usa estas funções mede as falhas com uma expectation.
def inteiro(coluna: str):
    return F.expr(f"try_cast(trim({coluna}) AS INT)")


def decimal_virgula(coluna: str):          # CAGED: "1628,51"
    return F.expr(f"try_cast(replace(trim({coluna}), ',', '.') AS DOUBLE)")


def decimal_ponto(coluna: str):            # RAIS: "1518.00"; PNAD: "000411.81"
    return F.expr(f"try_cast(trim({coluna}) AS DOUBLE)")


# A3 + A4: código da fonte -> rótulo comum. Códigos fora do dicionário
# ("não identificado") viram NULL automaticamente.
def traduzir(coluna: str, dicionario: dict):
    expr = None
    for codigo, rotulo in dicionario.items():
        cond = F.col(coluna) == codigo
        expr = F.when(cond, rotulo) if expr is None else expr.when(cond, rotulo)
    return expr


# Faixa etária a partir da mesma lista FAIXAS usada nos testes.
def faixa_etaria_col(idade):
    expr = F.lit("30+")
    for inicio, fim, rotulo in reversed(FAIXAS):
        expr = F.when(idade.between(inicio, fim), rotulo).otherwise(expr)
    return F.when(idade < 15, "<15").otherwise(expr)
