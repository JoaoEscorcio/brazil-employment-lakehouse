"""Transform: filtra RAIS Vínculos para Fortaleza+RMF e prepara as colunas pro load.

O arquivo real do RAIS_VINC_PUB (confirmado empiricamente, não presumido a partir do layout
.xls): delimitador vírgula, encoding latin-1, cabeçalho com nomes descritivos entre aspas
(ex. "Município - Código"). polars só aceita encoding utf8/utf8-lossy no scan_csv, então a
filtragem RMF é feita em streaming com csv.reader puro (que também recodifica pra UTF-8),
e só depois o arquivo já filtrado (bem menor) é lido com polars.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

import polars as pl

from pipeline.transform import FAIXAS, RMF_MUNICIPIOS

COL_MUNICIPIO = "Munic\xedpio - C\xf3digo"
COL_ATIVO_31_12 = "Ind V\xednculo Ativo 31/12 - C\xf3digo"

# Crosswalk oficial CNAE 2.0 classe -> seção, derivado de docs_oficiais/CNAE20_EstruturaDetalhada.xls
# (IBGE/Concla, "2.2 - Estrutura detalhada da CNAE 2.0"). A RAIS só traz classe (5 dígitos) e
# subclasse (7 dígitos = classe*100 + sufixo) — não traz a seção (letra) diretamente, diferente
# do CAGED, que já vem com o campo seção pronto.
with open(Path(__file__).parent / "cnae_classe_secao.json", encoding="utf-8") as _f:
    CNAE_CLASSE_SECAO: dict[int, str] = {int(k): v for k, v in json.load(_f).items()}

# Agrupamento de subsetor IBGE -> "Indústria e Construção" vs "Agropecuária, Comércio e
# Serviços", confirmado no Glossário de Indicadores oficial do painel BID/MTE (seção "Porte
# de empresas"). Código 24 não consta na tabela oficial (não usado/reservado).
SUBSETOR_INDUSTRIA_CONSTRUCAO = set(range(1, 16))  # 01-15
SUBSETOR_AGRO_COMERCIO_SERVICOS = {16, 17, 18, 19, 20, 21, 22, 23, 25}

# TAMESTAB (10 categorias oficiais da RAIS) -> porte de empresa (4 categorias do painel BID/MTE).
# Os limites do TAMESTAB batem exatamente com os limites oficiais do painel (confirmado
# comparando as duas tabelas), então dá pra reclassificar sem precisar de headcount por
# estabelecimento (que não está disponível no microdado público, sem identificador de empresa).
# TAMESTAB: 1=zero,2=1-4,3=5-9,4=10-19,5=20-49,6=50-99,7=100-249,8=250-499,9=500-999,10=1000+
TAMESTAB_PORTE_INDUSTRIA = {1: "Micro", 2: "Micro", 3: "Micro", 4: "Micro", 5: "Pequena", 6: "Pequena",
                            7: "M\xe9dia", 8: "M\xe9dia", 9: "Grande", 10: "Grande"}
TAMESTAB_PORTE_SERVICOS = {1: "Micro", 2: "Micro", 3: "Micro", 4: "Pequena", 5: "Pequena",
                           6: "M\xe9dia", 7: "Grande", 8: "Grande", 9: "Grande", 10: "Grande"}


def filtrar_rmf(caminho_comt: Path, destino_csv: Path) -> Path:
    """Filtra o arquivo bruto (Nordeste, latin-1) para Fortaleza+RMF e regrava em UTF-8. Idempotente."""
    if destino_csv.exists():
        return destino_csv

    destino_csv.parent.mkdir(parents=True, exist_ok=True)
    municipios_rmf = set(RMF_MUNICIPIOS.keys())

    with open(caminho_comt, encoding="latin-1", newline="") as fin, open(
        destino_csv, "w", encoding="utf-8", newline=""
    ) as fout:
        reader = csv.reader(fin, delimiter=",")
        header = next(reader)
        writer = csv.writer(fout, delimiter=",")
        writer.writerow(header)
        idx_mun = header.index(COL_MUNICIPIO)
        for row in reader:
            if int(row[idx_mun]) in municipios_rmf:
                writer.writerow(row)

    return destino_csv


def _faixa_etaria_expr() -> pl.Expr:
    expr = pl.lit("30+")
    for lo, hi, label in reversed(FAIXAS):
        expr = pl.when(pl.col("idade").is_between(lo, hi)).then(pl.lit(label)).otherwise(expr)
    return pl.when(pl.col("idade") < 15).then(pl.lit("<15")).otherwise(expr).alias("faixa_etaria")


COLUNAS_SAIDA = [
    "municipio_codigo",
    "bairro_fortaleza_codigo",
    "cbo_codigo",
    "cnae_classe",
    "cnae_subclasse",
    "cnae_secao",
    "natureza_juridica_codigo",
    "tipo_estabelecimento_codigo",
    "tamanho_estabelecimento_codigo",
    "tipo_vinculo_codigo",
    "tipo_admissao_codigo",
    "vinculo_ativo_31_12",
    "mes_admissao",
    "mes_desligamento",
    "motivo_desligamento_codigo",
    "grau_instrucao_codigo",
    "sexo",
    "raca_cor",
    "idade",
    "faixa_etaria",
    "horas_contratuais",
    "tempo_emprego_meses",
    "remuneracao_dezembro_nominal",
    "remuneracao_media_nominal",
    "indicador_pcd",
    "tipo_deficiencia_codigo",
    "nacionalidade_codigo",
    "categoria_trabalhador_codigo",
    "ibge_subsetor_codigo",
    "porte_oficial",
]


def carregar_rmf(caminho_rmf_csv: Path) -> pl.DataFrame:
    """Lê o CSV já filtrado (Fortaleza+RMF, UTF-8) e devolve as colunas prontas pro load."""
    lf = pl.scan_csv(caminho_rmf_csv, separator=",", encoding="utf8", infer_schema_length=50000)

    def _int_or_null(col: str) -> pl.Expr:
        # vários campos numéricos do arquivo real vêm com espaço à esquerda (padding de largura fixa
        # preservado dentro do CSV, ex. " 85139") — confirmado empiricamente que .cast() sozinho não
        # trata isso (retorna null em vez de aparar o espaço), por isso o strip_chars() é obrigatório aqui.
        return pl.col(col).cast(pl.Utf8).str.strip_chars().cast(pl.Int64, strict=False)

    def _float_or_null(col: str) -> pl.Expr:
        return pl.col(col).cast(pl.Utf8).str.strip_chars().cast(pl.Float64, strict=False)

    municipio_codigo = _int_or_null("Munic\xedpio - C\xf3digo")

    lf = lf.with_columns(
        municipio_codigo.alias("municipio_codigo"),
        # 999997 é o código-sentinela oficial de "não informado" (mesmo usado nos campos Bairros SP/RJ e
        # Distrito SP) — confirmado empiricamente que em 100% das linhas de Fortaleza no arquivo real
        # (ano-base 2025) esse campo vem com o sentinela, ou seja, bairro não está populado nesta extração.
        pl.when((municipio_codigo == 230440) & (_int_or_null("Bairros Fortaleza - C\xf3digo") != 999997))
        .then(_int_or_null("Bairros Fortaleza - C\xf3digo"))
        .otherwise(None)
        .alias("bairro_fortaleza_codigo"),
        _int_or_null("CBO 2002 Ocupa\xe7\xe3o - C\xf3digo").alias("cbo_codigo"),
        _int_or_null("CNAE 2.0 Classe - C\xf3digo").alias("cnae_classe"),
        _int_or_null("CNAE 2.0 Subclasse - Codigo").alias("cnae_subclasse"),
        _int_or_null("Natureza Jur\xeddica - C\xf3digo").alias("natureza_juridica_codigo"),
        _int_or_null("Tipo Estabelecimento - C\xf3digo").alias("tipo_estabelecimento_codigo"),
        _int_or_null("Tamanho Estabelecimento - C\xf3digo").alias("tamanho_estabelecimento_codigo"),
        _int_or_null("Tipo V\xednculo - C\xf3digo").alias("tipo_vinculo_codigo"),
        _int_or_null("Tipo Admiss\xe3o Trabalhador - C\xf3digo").alias("tipo_admissao_codigo"),
        (_int_or_null("Ind V\xednculo Ativo 31/12 - C\xf3digo") == 1).alias("vinculo_ativo_31_12"),
        _int_or_null("M\xeas Admiss\xe3o - C\xf3digo").alias("mes_admissao"),
        _int_or_null("M\xeas Desligamento - C\xf3digo").alias("mes_desligamento"),
        _int_or_null("Motivo Desligamento - C\xf3digo").alias("motivo_desligamento_codigo"),
        _int_or_null("Escolaridade Ap\xf3s 2005 - C\xf3digo").alias("grau_instrucao_codigo"),
        _int_or_null("Sexo - C\xf3digo").alias("sexo"),
        _int_or_null("Ra\xe7a Cor - C\xf3digo").alias("raca_cor"),
        _int_or_null("Idade").alias("idade"),
        _int_or_null("Qtd Hora Contr").alias("horas_contratuais"),
        _float_or_null("Tempo Emprego").alias("tempo_emprego_meses"),
        _float_or_null("Vl Rem Dezembro Nom").alias("remuneracao_dezembro_nominal"),
        _float_or_null("Vl Rem M\xe9dia Nom").alias("remuneracao_media_nominal"),
        (_int_or_null("Ind Portador Defic - C\xf3digo") == 1).alias("indicador_pcd"),
        _int_or_null("Tipo Defici\xeancia - C\xf3digo").alias("tipo_deficiencia_codigo"),
        _int_or_null("Nacionalidade - C\xf3digo").alias("nacionalidade_codigo"),
        _int_or_null("Categoria Trabalhador - C\xf3digo").alias("categoria_trabalhador_codigo"),
        _int_or_null("IBGE Subsetor - C\xf3digo").alias("ibge_subsetor_codigo"),
    )
    lf = lf.with_columns(
        _faixa_etaria_expr(),
        pl.col("cnae_classe").replace(CNAE_CLASSE_SECAO, default=None).alias("cnae_secao"),
    )

    # Porte de empresas — metodologia oficial do painel BID/MTE: cruza o agrupamento de
    # subsetor IBGE com o TAMESTAB (ver comentário na definição das tabelas acima).
    grupo_industria = pl.col("ibge_subsetor_codigo").is_in(list(SUBSETOR_INDUSTRIA_CONSTRUCAO))
    grupo_servicos = pl.col("ibge_subsetor_codigo").is_in(list(SUBSETOR_AGRO_COMERCIO_SERVICOS))
    porte_industria = pl.col("tamanho_estabelecimento_codigo").replace(TAMESTAB_PORTE_INDUSTRIA, default=None)
    porte_servicos = pl.col("tamanho_estabelecimento_codigo").replace(TAMESTAB_PORTE_SERVICOS, default=None)
    lf = lf.with_columns(
        pl.when(grupo_industria)
        .then(porte_industria)
        .when(grupo_servicos)
        .then(porte_servicos)
        .otherwise(None)
        .alias("porte_oficial")
    )

    return lf.select(COLUNAS_SAIDA).collect()
