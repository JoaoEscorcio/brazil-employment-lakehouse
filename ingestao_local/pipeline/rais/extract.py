"""Extract: baixa e descompacta os vínculos da RAIS (Nordeste) do FTP do MTE."""
from __future__ import annotations

import ftplib
import logging
from pathlib import Path

import py7zr

logger = logging.getLogger(__name__)

FTP_HOST = "ftp.mtps.gov.br"
FTP_BASE_PATH = "pdet/microdados/RAIS"

NOME_ARQUIVO = "RAIS_VINC_PUB_NORDESTE.7z"


def _pasta_ano(ano: int) -> str:
    return f"{FTP_BASE_PATH}/{ano}"


def baixar_7z(ano: int, destino_dir: Path) -> Path:
    """Baixa RAIS_VINC_PUB_NORDESTE.7z do FTP para o ano-base informado. Idempotente."""
    destino_dir.mkdir(parents=True, exist_ok=True)
    destino = destino_dir / NOME_ARQUIVO

    if destino.exists():
        logger.info("já baixado, pulando: %s", destino)
        return destino

    with ftplib.FTP(FTP_HOST, timeout=60, encoding="latin-1") as ftp:
        ftp.login()
        ftp.cwd(_pasta_ano(ano))
        with open(destino, "wb") as f:
            ftp.retrbinary(f"RETR {NOME_ARQUIVO}", f.write)

    logger.info("baixado: %s (%d bytes)", destino, destino.stat().st_size)
    return destino


def extrair_7z(caminho_7z: Path, destino_dir: Path) -> Path:
    """Extrai o .7z e retorna o caminho do arquivo de dados extraído. Idempotente.

    O arquivo interno do RAIS_VINC_PUB vem com extensão .COMT (não .txt), confirmado
    empiricamente na extração real — não é um .txt como no Novo CAGED.
    """
    destino_dir.mkdir(parents=True, exist_ok=True)
    nome_comt = caminho_7z.stem + ".COMT"
    destino_comt = destino_dir / nome_comt
    if destino_comt.exists():
        return destino_comt

    with py7zr.SevenZipFile(caminho_7z, mode="r") as z:
        z.extractall(path=destino_dir)

    return destino_comt


def obter_dados(ano: int, base_dir: Path) -> Path:
    """Baixa (se necessário) e extrai os vínculos da RAIS Nordeste do ano-base, retornando o caminho do arquivo."""
    zip_path = baixar_7z(ano, base_dir / "download")
    return extrair_7z(zip_path, base_dir / "extraido")
