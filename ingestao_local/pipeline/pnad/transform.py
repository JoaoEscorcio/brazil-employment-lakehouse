"""Transform: filtra PNAD Contínua para a RMF e prepara as colunas pro load.

Arquivo de largura fixa, sem delimitador — posições confirmadas contra o layout oficial
(docs_oficiais/pnad/input_PNADC_trimestral.sas) E contra os bytes reais do arquivo baixado
(2º tri/2026), não presumidas. Peso (V1028) já vem com ponto decimal literal no texto.

RM_RIDE = '23' é a Região Metropolitana de Fortaleza — mesmo domínio oficial de estimação
da pesquisa (estratificação por RM, confirmado nas Notas Metodológicas do IBGE).
"""
from __future__ import annotations

import csv
from pathlib import Path

import polars as pl

RM_RIDE_FORTALEZA = "23"

# posições 0-indexed [inicio:fim) — confirmadas contra o .sas oficial e os bytes reais do arquivo
CAMPOS = {
    "ano": (0, 4),
    "trimestre": (4, 5),
    "uf": (5, 7),
    "capital": (7, 9),
    "rm_ride": (9, 11),
    "peso": (49, 64),  # V1028, peso com calibração
    "sexo": (94, 95),  # V2007
    "cor_raca": (106, 107),  # V2010
    "idade": (103, 106),  # V2009
    "nivel_instrucao": (404, 405),  # VD3004
    "condicao_forca_trabalho": (408, 409),  # VD4001
    "condicao_ocupacao": (409, 410),  # VD4002
    "forca_trabalho_potencial": (410, 411),  # VD4003
    "subocupacao": (412, 413),  # VD4004A
    "desalento": (413, 414),  # VD4005
    "posicao_categoria": (416, 418),  # VD4009
    "grupamento_atividade": (418, 420),  # VD4010
    "grupamento_ocupacional": (420, 422),  # VD4011
    "contribuicao_previdenciaria": (422, 423),  # VD4012
    "rendimento_habitual": (443, 451),  # VD4019
    "rendimento_efetivo": (451, 459),  # VD4020
    "negocio_cnpj": (185, 186),  # V4019 — "esse negócio/empresa era registrado no CNPJ?"
}

CAMPOS_ORDEM = list(CAMPOS.keys())


def filtrar_rmf(caminho_txt: Path, destino_csv: Path) -> Path:
    """Filtra o arquivo bruto (nacional, largura fixa) pra RMF e grava como CSV. Idempotente."""
    if destino_csv.exists():
        return destino_csv

    destino_csv.parent.mkdir(parents=True, exist_ok=True)

    with open(caminho_txt, encoding="latin-1") as fin, open(
        destino_csv, "w", encoding="utf-8", newline=""
    ) as fout:
        writer = csv.writer(fout)
        writer.writerow(CAMPOS_ORDEM)
        ini_rm, fim_rm = CAMPOS["rm_ride"]
        for line in fin:
            if line[ini_rm:fim_rm] == RM_RIDE_FORTALEZA:
                writer.writerow([line[ini:fim].strip() for ini, fim in CAMPOS.values()])

    return destino_csv


def carregar_rmf(caminho_rmf_csv: Path) -> pl.DataFrame:
    """Lê o CSV já filtrado (RMF) e devolve as colunas tipadas prontas pro load."""
    df = pl.read_csv(
        caminho_rmf_csv,
        schema_overrides={
            "ano": pl.Int32,
            "trimestre": pl.Int8,
            "uf": pl.Utf8,
            "capital": pl.Utf8,
            "rm_ride": pl.Utf8,
            "peso": pl.Float64,
            "sexo": pl.Int8,
            "cor_raca": pl.Utf8,
            "idade": pl.Int16,
            "nivel_instrucao": pl.Utf8,
            "condicao_forca_trabalho": pl.Utf8,
            "condicao_ocupacao": pl.Utf8,
            "forca_trabalho_potencial": pl.Utf8,
            "subocupacao": pl.Utf8,
            "desalento": pl.Utf8,
            "posicao_categoria": pl.Utf8,
            "grupamento_atividade": pl.Utf8,
            "grupamento_ocupacional": pl.Utf8,
            "contribuicao_previdenciaria": pl.Utf8,
            "rendimento_habitual": pl.Utf8,
            "rendimento_efetivo": pl.Utf8,
            "negocio_cnpj": pl.Utf8,
        },
        null_values=[""],
    )

    df = df.with_columns(
        (pl.col("capital") == "23").fill_null(False).alias("municipio_fortaleza"),
        pl.col("cor_raca").cast(pl.Int8, strict=False),
        pl.col("nivel_instrucao").cast(pl.Int8, strict=False),
        pl.col("condicao_forca_trabalho").cast(pl.Int8, strict=False),
        pl.col("condicao_ocupacao").cast(pl.Int8, strict=False),
        pl.col("forca_trabalho_potencial").cast(pl.Int8, strict=False),
        pl.col("subocupacao").cast(pl.Int8, strict=False),
        pl.col("desalento").cast(pl.Int8, strict=False),
        pl.col("posicao_categoria").cast(pl.Int8, strict=False),
        pl.col("grupamento_atividade").cast(pl.Int8, strict=False),
        pl.col("grupamento_ocupacional").cast(pl.Int8, strict=False),
        pl.col("contribuicao_previdenciaria").cast(pl.Int8, strict=False),
        pl.col("rendimento_habitual").cast(pl.Float64, strict=False),
        pl.col("rendimento_efetivo").cast(pl.Float64, strict=False),
        pl.col("negocio_cnpj").cast(pl.Int8, strict=False),
    )

    # Definição oficial de informalidade (Glossário de Indicadores, Painel de Indicadores da
    # Rede de Observatórios do Trabalho, BID/MTE/MacroPlan) — união de 4 conjuntos:
    # empregado sem carteira (privado ou doméstico, NÃO inclui público sem carteira aqui),
    # empregador sem CNPJ, conta-própria sem CNPJ, trabalhador familiar auxiliar.
    informal = (
        pl.col("posicao_categoria").is_in([2, 4])
        | ((pl.col("posicao_categoria") == 8) & (pl.col("negocio_cnpj") == 2))
        | ((pl.col("posicao_categoria") == 9) & (pl.col("negocio_cnpj") == 2))
        | (pl.col("posicao_categoria") == 10)
    )
    return df.with_columns(informal.alias("informal"))
