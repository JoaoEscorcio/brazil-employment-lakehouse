"""Extract: baixa e descompacta os microdados trimestrais da PNAD Contínua do FTP do IBGE."""
from __future__ import annotations

import logging
import urllib.request
import zipfile
from pathlib import Path

logger = logging.getLogger(__name__)

BASE_URL = "https://ftp.ibge.gov.br/Trabalho_e_Rendimento/Pesquisa_Nacional_por_Amostra_de_Domicilios_continua/Trimestral/Microdados"


def _nome_arquivo(ano: int, trimestre: int) -> str:
    return f"PNADC_0{trimestre}{ano}"


def baixar_zip(ano: int, trimestre: int, destino_dir: Path) -> Path:
    """Baixa PNADC_0<trimestre><ano>.zip do FTP do IBGE. Idempotente."""
    nome = _nome_arquivo(ano, trimestre)
    destino_dir.mkdir(parents=True, exist_ok=True)
    destino = destino_dir / f"{nome}.zip"

    if destino.exists():
        logger.info("já baixado, pulando: %s", destino)
        return destino

    url = f"{BASE_URL}/{ano}/{nome}.zip"
    logger.info("baixando %s", url)
    urllib.request.urlretrieve(url, destino)
    logger.info("baixado: %s (%d bytes)", destino, destino.stat().st_size)
    return destino


def extrair_zip(caminho_zip: Path, destino_dir: Path) -> Path:
    """Extrai o .zip e retorna o caminho do .txt extraído. Idempotente."""
    destino_dir.mkdir(parents=True, exist_ok=True)
    nome_txt = caminho_zip.stem + ".txt"
    destino_txt = destino_dir / nome_txt
    if destino_txt.exists():
        return destino_txt

    with zipfile.ZipFile(caminho_zip, "r") as z:
        z.extractall(path=destino_dir)

    return destino_txt


def obter_dados(ano: int, trimestre: int, base_dir: Path) -> Path:
    """Baixa (se necessário) e extrai o trimestre, retornando o caminho do .txt de largura fixa."""
    zip_path = baixar_zip(ano, trimestre, base_dir / "download")
    return extrair_zip(zip_path, base_dir)
