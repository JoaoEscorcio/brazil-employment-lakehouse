"""Extract: baixa e descompacta os arquivos do Novo CAGED do FTP do MTE."""
from __future__ import annotations

import ftplib
import logging
from pathlib import Path

import py7zr

logger = logging.getLogger(__name__)

FTP_HOST = "ftp.mtps.gov.br"
FTP_BASE_PATH = "pdet/microdados/NOVO CAGED"

TIPOS = ("MOV", "FOR", "EXC")


def _pasta_competencia(competencia: int) -> str:
    ano = str(competencia)[:4]
    return f"{FTP_BASE_PATH}/{ano}/{competencia}"


def baixar_7z(competencia: int, tipo: str, destino_dir: Path) -> Path:
    """Baixa CAGED{tipo}{competencia}.7z do FTP. Idempotente: pula se já existir localmente."""
    if tipo not in TIPOS:
        raise ValueError(f"tipo inválido: {tipo!r}, esperado um de {TIPOS}")

    nome_arquivo = f"CAGED{tipo}{competencia}.7z"
    destino_dir.mkdir(parents=True, exist_ok=True)
    destino = destino_dir / nome_arquivo

    if destino.exists():
        logger.info("já baixado, pulando: %s", destino)
        return destino

    with ftplib.FTP(FTP_HOST, timeout=60, encoding="latin-1") as ftp:
        ftp.login()
        ftp.cwd(_pasta_competencia(competencia))
        with open(destino, "wb") as f:
            ftp.retrbinary(f"RETR {nome_arquivo}", f.write)

    logger.info("baixado: %s (%d bytes)", destino, destino.stat().st_size)
    return destino


def extrair_7z(caminho_7z: Path, destino_dir: Path) -> Path:
    """Extrai o .7z e retorna o caminho do .txt extraído. Idempotente."""
    destino_dir.mkdir(parents=True, exist_ok=True)
    nome_txt = caminho_7z.stem + ".txt"
    destino_txt = destino_dir / nome_txt
    if destino_txt.exists():
        return destino_txt

    with py7zr.SevenZipFile(caminho_7z, mode="r") as z:
        z.extractall(path=destino_dir)

    return destino_txt


def obter_txt(competencia: int, tipo: str, base_dir: Path) -> Path:
    """Baixa (se necessário) e extrai o arquivo de uma competência/tipo, retornando o caminho do .txt."""
    zip_path = baixar_7z(competencia, tipo, base_dir / "download")
    return extrair_7z(zip_path, base_dir / "extraido")
