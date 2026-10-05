"""Transform: filtra Fortaleza+RMF, resolve faixa etária e calcula o efeito de cada movimentação.

Regra de efeito (confirmada na Nota Técnica 11/2021 e no Leia-me oficial do FTP):
MOV e FOR somam normalmente ao saldo; EXC entra com o sinal invertido (exclusão de
admissão reduz o saldo, exclusão de desligamento aumenta o saldo).
"""
from __future__ import annotations

from pathlib import Path

import polars as pl

# código MTE do município = código IBGE de 7 dígitos sem o dígito verificador
# confirmado contra o layout oficial (docs_oficiais/Layout Nao-identificado Novo Caged Movimentacao.xlsx)
RMF_MUNICIPIOS = {
    230440: "Fortaleza",
    230100: "Aquiraz",
    230350: "Cascavel",
    230370: "Caucaia",
    230395: "Chorozinho",
    230428: "Eusébio",
    230495: "Guaiúba",
    230523: "Horizonte",
    230625: "Itaitinga",
    230765: "Maracanaú",
    230770: "Maranguape",
    230960: "Pacajus",
    230970: "Pacatuba",
    231085: "Pindoretama",
    231240: "São Gonçalo do Amarante",
    231260: "São Luís do Curu",
    231025: "Paraipaba",
    231020: "Paracuru",
    231350: "Trairi",
}

FAIXAS = [
    (15, 17, "15-17"),
    (18, 24, "18-24"),
    (25, 29, "25-29"),
]

COLUNAS_SAIDA = [
    "origem_arquivo",
    "competencia_mov",
    "competencia_dec",
    "competencia_exc",
    "municipio_codigo",
    "cbo_codigo",
    "cnae_secao",
    "cnae_subclasse",
    "saldo_movimentacao",
    "efeito",
    "tipo_movimentacao",
    "categoria",
    "grau_instrucao_codigo",
    "idade",
    "faixa_etaria",
    "sexo",
    "raca_cor",
    "salario",
    "indicador_exclusao",
    "indicador_fora_prazo",
]


def _faixa_etaria_expr() -> pl.Expr:
    expr = pl.lit("30+")
    for lo, hi, label in reversed(FAIXAS):
        expr = pl.when(pl.col("idade").is_between(lo, hi)).then(pl.lit(label)).otherwise(expr)
    return pl.when(pl.col("idade") < 15).then(pl.lit("<15")).otherwise(expr).alias("faixa_etaria")


def carregar_competencia(tipo: str, txt_path: Path) -> pl.DataFrame:
    """Lê um arquivo MOV/FOR/EXC, filtra Fortaleza+RMF e devolve as colunas prontas pro load."""
    lf = pl.scan_csv(txt_path, separator=";", encoding="utf8", infer_schema_length=10000)
    schema = lf.collect_schema().names()
    tem_exc = "competênciaexc" in schema

    lf = lf.filter(pl.col("município").is_in(list(RMF_MUNICIPIOS.keys())))

    sinal = -1 if tipo == "EXC" else 1

    lf = lf.with_columns(
        pl.lit(tipo).alias("origem_arquivo"),
        pl.col("competênciamov").alias("competencia_mov"),
        pl.col("competênciadec").alias("competencia_dec"),
        (pl.col("competênciaexc") if tem_exc else pl.lit(None, dtype=pl.Int64)).alias("competencia_exc"),
        pl.col("município").alias("municipio_codigo"),
        pl.col("cbo2002ocupação").alias("cbo_codigo"),
        pl.col("seção").alias("cnae_secao"),
        pl.col("subclasse").alias("cnae_subclasse"),
        pl.col("saldomovimentação").alias("saldo_movimentacao"),
        (pl.col("saldomovimentação") * sinal).alias("efeito"),
        pl.col("tipomovimentação").alias("tipo_movimentacao"),
        pl.col("categoria").alias("categoria"),
        pl.col("graudeinstrução").alias("grau_instrucao_codigo"),
        pl.col("raçacor").alias("raca_cor"),
        pl.col("salário").str.replace(",", ".").cast(pl.Float64).alias("salario"),
        pl.col("indicadordeforadoprazo").cast(pl.Boolean).alias("indicador_fora_prazo"),
        (
            pl.col("indicadordeexclusão").cast(pl.Boolean)
            if tem_exc
            else pl.lit(False)
        ).alias("indicador_exclusao"),
        _faixa_etaria_expr(),
    )

    return lf.select(COLUNAS_SAIDA).collect()
