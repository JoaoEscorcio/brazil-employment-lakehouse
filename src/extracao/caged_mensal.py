# Databricks notebook source
# MAGIC %md
# MAGIC # Extração mensal do Novo CAGED
# MAGIC
# MAGIC Traz para o volume `landing.raw` as competências do CAGED que ainda não estão lá.
# MAGIC Substitui, dentro do Databricks, o que o `ingestao_local/preparar_landing.py` fazia
# MAGIC na máquina local para a carga histórica.
# MAGIC
# MAGIC ```
# MAGIC FTP do MTE ──► .7z do mês ──► .txt nacional (volume de trabalho)
# MAGIC      ──► Spark filtra os 19 municípios da RMF
# MAGIC      ──► landing/raw/caged/tipo=MOV|FOR|EXC/competencia=AAAAMM/part-0.parquet
# MAGIC ```
# MAGIC
# MAGIC **Mesmo formato da carga histórica**: as colunas ficam como texto, com nomes em snake_case,
# MAGIC e nenhuma regra de negócio é aplicada aqui (isso é trabalho da silver). Por isso a bronze
# MAGIC e a silver não precisam saber de onde veio cada arquivo.
# MAGIC
# MAGIC **Idempotente**: uma competência que já está na landing é pulada. Rodar duas vezes não
# MAGIC duplica dados, e o Auto Loader da bronze só lê arquivos novos.
# MAGIC
# MAGIC Parâmetros:
# MAGIC - `competencia`: vazio = automático (todas as competências publicadas depois da última
# MAGIC   que está na landing); `AAAAMM` = só aquele mês.
# MAGIC - `destino`: pasta de saída. Só muda para testes.

# COMMAND ----------

# MAGIC %pip install py7zr==0.22.0

# COMMAND ----------

import ftplib
import json
import os
import re
import shutil
import sys
import tempfile
import unicodedata
from datetime import date

import py7zr
from pyspark.sql import functions as F

# Regras de negócio compartilhadas com o pipeline (src/regras), fonte única da lista da RMF.
sys.path.append(os.path.abspath(".."))
from regras.rmf import RMF_MUNICIPIOS  # noqa: E402

dbutils.widgets.text("competencia", "", "Competência AAAAMM (vazio = automático)")
dbutils.widgets.text("destino", "/Volumes/brazil_employment/landing/raw/caged", "Pasta de destino")
COMPETENCIA = dbutils.widgets.get("competencia").strip()
DESTINO = dbutils.widgets.get("destino").rstrip("/")

FTP_HOST = "ftp.mtps.gov.br"
FTP_BASE = "pdet/microdados/NOVO CAGED"
TIPOS = ("MOV", "FOR", "EXC")
RMF = [str(c) for c in RMF_MUNICIPIOS]

# Área de trabalho separada da landing: o Auto Loader nunca vê arquivo pela metade.
spark.sql("""
    CREATE VOLUME IF NOT EXISTS brazil_employment.landing.trabalho
    COMMENT 'Área temporária das extrações (arquivos baixados e descompactados). Pode ser apagada.'
""")
TRABALHO = "/Volumes/brazil_employment/landing/trabalho/caged"

# COMMAND ----------

# MAGIC %md
# MAGIC ## Funções

# COMMAND ----------

def snake(nome: str) -> str:
    """'Município - Código' -> 'municipio_codigo'. Mesma regra da carga histórica."""
    sem_acento = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode()
    return re.sub(r"[^0-9a-zA-Z]+", "_", sem_acento).strip("_").lower()


def conectar() -> ftplib.FTP:
    ftp = ftplib.FTP(FTP_HOST, timeout=120, encoding="latin-1")
    ftp.login()
    return ftp


def competencias_na_landing() -> list[int]:
    """Competências que já têm o arquivo MOV na landing."""
    pasta = f"{DESTINO}/tipo=MOV"
    if not os.path.exists(pasta):
        return []
    return sorted(int(n.split("=")[1]) for n in os.listdir(pasta) if n.startswith("competencia="))


def competencias_publicadas(depois_de: int) -> list[int]:
    """Competências posteriores a `depois_de` cujo MOV já está no FTP."""
    publicadas = []
    with conectar() as ftp:
        for ano in range(depois_de // 100, date.today().year + 1):
            try:
                ftp.cwd(f"/{FTP_BASE}/{ano}")
            except ftplib.error_perm:
                continue  # ano ainda sem pasta
            for mes in sorted(n.rsplit("/", 1)[-1] for n in ftp.nlst()):
                if re.fullmatch(r"\d{6}", mes) and int(mes) > depois_de:
                    arquivos = [n.rsplit("/", 1)[-1] for n in ftp.nlst(mes)]
                    if f"CAGEDMOV{mes}.7z" in arquivos:
                        publicadas.append(int(mes))
    return publicadas


def baixar_txt(competencia: int, tipo: str) -> str:
    """Baixa e descompacta CAGED{tipo}{competencia}.7z; devolve o .txt no volume de trabalho.

    O download e a descompactação usam o disco local (mais rápido e sem escrita parcial no
    volume); só o .txt final é copiado para o volume, onde o Spark consegue ler.
    """
    nome = f"CAGED{tipo}{competencia}"
    destino = f"{TRABALHO}/{competencia}/{nome}.txt"
    os.makedirs(os.path.dirname(destino), exist_ok=True)
    with tempfile.TemporaryDirectory() as local:
        arquivo_7z = os.path.join(local, f"{nome}.7z")
        with conectar() as ftp, open(arquivo_7z, "wb") as f:
            ftp.cwd(f"/{FTP_BASE}/{str(competencia)[:4]}/{competencia}")
            ftp.retrbinary(f"RETR {nome}.7z", f.write)
        with py7zr.SevenZipFile(arquivo_7z, mode="r") as z:
            z.extractall(path=local)
        shutil.copyfile(os.path.join(local, f"{nome}.txt"), destino)
    return destino


def recortar_rmf(txt: str, competencia: int, tipo: str) -> int:
    """Lê o .txt nacional, mantém só a RMF e grava um Parquet na landing. Devolve as linhas."""
    df = (
        spark.read
        .option("header", True)
        .option("sep", ";")
        .option("encoding", "UTF-8")
        .csv(txt)                                   # sem inferSchema: tudo como texto
        .filter(F.col("município").isin(RMF))
    )
    df = df.toDF(*[snake(c) for c in df.columns])

    # O Spark grava uma pasta com part-*.parquet e arquivos de controle (_SUCCESS...).
    # Gravamos na área de trabalho e copiamos só o Parquet, com o mesmo nome da carga histórica.
    temporario = f"{TRABALHO}/{competencia}/parquet_{tipo}"
    df.coalesce(1).write.mode("overwrite").parquet(temporario)
    parte = next(f.path for f in dbutils.fs.ls(temporario) if f.name.endswith(".parquet"))
    final = f"{DESTINO}/tipo={tipo}/competencia={competencia}/part-0.parquet"
    dbutils.fs.cp(parte, final)
    return spark.read.parquet(final).count()

# COMMAND ----------

# MAGIC %md
# MAGIC ## Quais competências buscar

# COMMAND ----------

if COMPETENCIA:
    alvo = [int(COMPETENCIA)]
else:
    na_landing = competencias_na_landing()
    ultima = max(na_landing) if na_landing else 202412
    alvo = competencias_publicadas(depois_de=ultima)
    print(f"Última competência na landing: {ultima}")
print(f"Competências a processar: {alvo or 'nenhuma (já está tudo carregado)'}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Extração
# MAGIC Para cada competência, os três arquivos: MOV (movimentações do mês), FOR (declaradas fora
# MAGIC do prazo, de meses anteriores) e EXC (exclusões, que corrigem meses anteriores).
# MAGIC Se um arquivo do mês faltar no FTP, o notebook falha de propósito: o Job avisa por e-mail
# MAGIC e nada fica pela metade na landing (o MOV é gravado por último).

# COMMAND ----------

resumo = []
for competencia in alvo:
    for tipo in ("FOR", "EXC", "MOV"):   # MOV por último: é ele que marca a competência como carregada
        pasta = f"{DESTINO}/tipo={tipo}/competencia={competencia}"
        if os.path.exists(pasta):
            resumo.append({"competencia": competencia, "tipo": tipo, "linhas_rmf": None, "situacao": "já existia"})
            continue
        txt = baixar_txt(competencia, tipo)
        linhas = recortar_rmf(txt, competencia, tipo)
        resumo.append({"competencia": competencia, "tipo": tipo, "linhas_rmf": linhas, "situacao": "carregado"})
        print(f"{competencia} {tipo}: {linhas:,} linhas da RMF")
    dbutils.fs.rm(f"{TRABALHO}/{competencia}", recurse=True)   # limpa a área de trabalho

display(spark.createDataFrame(resumo, "competencia INT, tipo STRING, linhas_rmf LONG, situacao STRING")) if resumo else None

# COMMAND ----------

# MAGIC %md
# MAGIC ## Saída para o Job
# MAGIC `novas_competencias` vai para a próxima tarefa do Job, que só atualiza o pipeline se
# MAGIC chegou dado novo.

# COMMAND ----------

novas = sorted({r["competencia"] for r in resumo if r["situacao"] == "carregado"})
try:
    dbutils.jobs.taskValues.set(key="novas_competencias", value=len(novas))
except Exception:
    pass  # execução interativa, fora de um Job
dbutils.notebook.exit(json.dumps({"novas_competencias": novas}))
