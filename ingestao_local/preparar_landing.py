"""Carga histórica (backfill): recorta CAGED, RAIS e PNAD para a RMF e grava Parquet pro volume landing.raw.

Roda uma vez, na máquina local, a partir dos arquivos já baixados pelo Emprega+ (22 GB).
As competências novas do CAGED chegam depois pela extração mensal dentro do Databricks.

Só recorta os 19 municípios e padroniza nomes de coluna. Valores ficam como texto e
nenhuma regra de negócio é aplicada aqui: isso é trabalho da camada Silver.
"""
from __future__ import annotations

import csv
import json
import re
import shutil
import unicodedata
from pathlib import Path

import openpyxl
import polars as pl
import xlrd

from fontes import extract
from fontes.pnad import extract as pnad_extract, transform as pnad_transform
from fontes.rais import extract as rais_extract, transform as rais_transform
from fontes.transform import RMF_MUNICIPIOS

EMPREGA = Path(r"C:\Projetos\Emprega+")
DADOS = EMPREGA / "_dados"
LAYOUT_CAGED = EMPREGA / "docs_oficiais" / "Layout Nao-identificado Novo Caged Movimentacao.xlsx"
DEFLATOR_PNAD = EMPREGA / "docs_oficiais" / "pnad" / "Deflatores" / "deflator_PNADC_2026_trimestral_040506.xls"
SAIDA = Path(__file__).parent / "landing"

RMF = [str(c) for c in RMF_MUNICIPIOS]
COMPETENCIAS = [202507, 202508, 202509, 202510, 202511, 202512,
                202601, 202602, 202603, 202604, 202605, 202606]
TRIMESTRES_PNAD = [(2025, 1), (2025, 2), (2025, 3), (2025, 4), (2026, 1), (2026, 2)]
# abas do layout oficial que viram dimensões na Silver (decodificação de códigos)
ABAS_LAYOUT_CAGED = ["sexo", "raçacor", "graudeinstrução", "tipomovimentação",
                     "unidadesaláriocódigo", "categoria", "seção", "cbo2002ocupação"]
UF_CEARA = "23"
# trimestres móveis do arquivo de deflatores do IBGE -> trimestre civil
TRIMESTRE_DEFLATOR = {"01-02-03": 1, "04-05-06": 2, "07-08-09": 3, "10-11-12": 4}


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


def rais_ceara(ano: int = 2025) -> None:
    """RAIS do Ceará inteiro, só com as colunas do quociente locacional.

    O QL compara cada município com o Ceará (glossário BID/MTE), e o recorte da RMF não
    basta. Para não subir o Nordeste inteiro, o recorte aqui é por LINHA (UF = 23) e por
    COLUNA (só as 3 necessárias). Nenhuma soma é feita aqui: a agregação fica na silver.
    """
    comt = rais_extract.obter_dados(ano, DADOS / "rais")
    colunas = ["Município - Código", "Ind Vínculo Ativo 31/12 - Código", "CNAE 2.0 Classe - Código"]
    linhas = []
    with open(comt, encoding="latin-1", newline="") as f:
        leitor = csv.reader(f, delimiter=",")
        cabecalho = next(leitor)
        idx = [cabecalho.index(c) for c in colunas]
        for row in leitor:
            if row[idx[0]].strip().startswith(UF_CEARA):
                linhas.append([row[i] for i in idx])
    df = pl.DataFrame(linhas, schema=colunas, orient="row")
    gravar(df, SAIDA / "rais_ceara" / f"ano_base={ano}")


def deflator_pnad() -> None:
    """Deflatores oficiais da PNAD (IBGE), só o Ceará, para o rendimento real."""
    folha = xlrd.open_workbook(DEFLATOR_PNAD).sheet_by_index(0)
    linhas = []
    for i in range(1, folha.nrows):
        ano, trim, uf, habitual, efetivo = folha.row_values(i)[:5]
        if str(uf).strip() == UF_CEARA and trim in TRIMESTRE_DEFLATOR:
            linhas.append([str(ano).strip(), str(TRIMESTRE_DEFLATOR[trim]), str(habitual), str(efetivo)])
    destino = SAIDA / "referencia"
    destino.mkdir(parents=True, exist_ok=True)
    df = pl.DataFrame(linhas, schema=["ano", "trimestre", "deflator_habitual", "deflator_efetivo"], orient="row")
    df.write_csv(destino / "pnad_deflator_ceara.csv")
    print(f"referencia/pnad_deflator_ceara.csv: {df.height} trimestres")


if __name__ == "__main__":
    caged()
    rais()
    pnad()
    referencia()
    rais_ceara()
    deflator_pnad()
