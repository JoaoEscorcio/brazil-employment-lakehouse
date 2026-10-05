"""Carga histórica (backfill): recorta CAGED, RAIS e PNAD para a RMF e grava Parquet pro volume landing.raw.

Roda uma vez, na máquina local, a partir dos arquivos já baixados pelo Emprega+ (22 GB).
As competências novas do CAGED chegam depois pela extração mensal dentro do Databricks.

Só recorta os 19 municípios e padroniza nomes de coluna. Valores ficam como texto e
nenhuma regra de negócio é aplicada aqui: isso é trabalho da camada Silver.
"""
from __future__ import annotations

import json
import re
import shutil
import unicodedata
from pathlib import Path

import openpyxl
import polars as pl

from pipeline import extract
from pipeline.pnad import extract as pnad_extract, transform as pnad_transform
from pipeline.rais import extract as rais_extract, transform as rais_transform
from pipeline.transform import RMF_MUNICIPIOS

EMPREGA = Path(r"C:\Projetos\Emprega+")
DADOS = EMPREGA / "_dados"
LAYOUT_CAGED = EMPREGA / "docs_oficiais" / "Layout Nao-identificado Novo Caged Movimentacao.xlsx"
SAIDA = Path(__file__).parent / "landing"

RMF = [str(c) for c in RMF_MUNICIPIOS]
COMPETENCIAS = [202507, 202508, 202509, 202510, 202511, 202512,
                202601, 202602, 202603, 202604, 202605, 202606]
TRIMESTRES_PNAD = [(2025, 1), (2025, 2), (2025, 3), (2025, 4), (2026, 1), (2026, 2)]
# abas do layout oficial que viram dimensões na Silver (decodificação de códigos)
ABAS_LAYOUT_CAGED = ["sexo", "raçacor", "graudeinstrução", "tipomovimentação",
                     "unidadesaláriocódigo", "categoria", "seção"]


def snake(nome: str) -> str:
    """'Município - Código' -> 'municipio_codigo'. O Delta não aceita espaço em nome de coluna."""
    sem_acento = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode()
    return re.sub(r"[^0-9a-zA-Z]+", "_", sem_acento).strip("_").lower()


def gravar(df: pl.DataFrame, destino: Path) -> None:
    destino.mkdir(parents=True, exist_ok=True)
    df.rename({c: snake(c) for c in df.columns}).write_parquet(destino / "part-0.parquet")
    print(f"{destino.relative_to(SAIDA)}: {df.height:,} linhas")


def caged() -> None:
    for comp in COMPETENCIAS:
        for tipo in ("MOV", "FOR", "EXC"):
            txt = extract.obter_txt(comp, tipo, DADOS)
            df = (
                pl.scan_csv(txt, separator=";", encoding="utf8", infer_schema_length=0)  # tudo como texto
                .filter(pl.col("município").is_in(RMF))
                .collect()
            )
            gravar(df, SAIDA / "caged" / f"tipo={tipo}" / f"competencia={comp}")


def rais(ano: int = 2025) -> None:
    comt = rais_extract.obter_dados(ano, DADOS / "rais")
    csv_rmf = rais_transform.filtrar_rmf(comt, DADOS / "rais" / "extraido" / f"RAIS_RMF_{ano}.csv")
    gravar(pl.read_csv(csv_rmf, infer_schema_length=0), SAIDA / "rais" / f"ano_base={ano}")


def pnad() -> None:
    for ano, tri in TRIMESTRES_PNAD:
        txt = pnad_extract.obter_dados(ano, tri, DADOS / "pnad")
        csv_rmf = pnad_transform.filtrar_rmf(txt, DADOS / "pnad" / f"PNADC_RMF_0{tri}{ano}.csv")
        gravar(pl.read_csv(csv_rmf, infer_schema_length=0), SAIDA / "pnad" / f"ano={ano}" / f"trimestre={tri}")


def referencia() -> None:
    """Dicionários oficiais como dados: a decodificação vira join rastreável na Silver."""
    destino = SAIDA / "referencia"
    destino.mkdir(parents=True, exist_ok=True)

    wb = openpyxl.load_workbook(LAYOUT_CAGED, read_only=True)
    for aba in ABAS_LAYOUT_CAGED:
        linhas = [r for r in wb[aba].iter_rows(values_only=True) if r and r[0] is not None]
        cabecalho, corpo = linhas[0], linhas[1:]
        df = pl.DataFrame([[str(v) for v in r[:2]] for r in corpo], schema=["codigo", "descricao"], orient="row")
        df.write_csv(destino / f"caged_{snake(aba)}.csv")
        print(f"referencia/caged_{snake(aba)}.csv: {df.height} códigos ({cabecalho[1]})")

    cnae = Path(rais_transform.__file__).parent / "cnae_classe_secao.json"
    shutil.copy(cnae, destino / "cnae_classe_secao.json")
    print(f"referencia/cnae_classe_secao.json: {len(json.loads(cnae.read_text(encoding='utf-8')))} classes")


if __name__ == "__main__":
    caged()
    rais()
    pnad()
    referencia()
