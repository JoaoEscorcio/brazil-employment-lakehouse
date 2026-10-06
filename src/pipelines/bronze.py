# =============================================================================
# CAMADA BRONZE
# Transforma os arquivos Parquet do volume landing.raw em tabelas Delta.
#
# Regra da camada: NÃO alterar nenhum valor. Todas as colunas continuam como
# texto, do jeito que a fonte publicou. A bronze só ACRESCENTA colunas:
#   - de partição (tiradas do nome das pastas: tipo, competencia, ano...)
#   - de auditoria (_arquivo_origem e _ingerido_em)
# Conversão de tipos, limpeza e regras de negócio ficam para a silver.
# =============================================================================

from pyspark import pipelines as dp
from pyspark.sql import functions as F

# Pasta de entrada: onde chegam os arquivos da carga histórica (máquina local)
# e da carga mensal (Job). A bronze não sabe nem precisa saber de onde cada
# arquivo veio: os dois caminhos gravam no mesmo lugar e no mesmo formato.
LANDING = "/Volumes/brazil_employment/landing/raw"


# -----------------------------------------------------------------------------
# Leitura com Auto Loader (função de apoio, usada pelas três tabelas)
#
# O Auto Loader (cloudFiles) guarda num checkpoint quais arquivos já leu.
# Cada execução processa só os arquivos NOVOS, então a ingestão é:
#   - incremental: o mês novo não obriga a reler o histórico inteiro
#   - idempotente: rodar duas vezes não duplica linhas
# O local do checkpoint é gerenciado pelo pipeline; não se configura aqui.
# -----------------------------------------------------------------------------
def _auto_loader(pasta: str, particoes: str):
    return (
        spark.readStream
        .format("cloudFiles")
        .option("cloudFiles.format", "parquet")
        # Pastas no padrão chave=valor (ex.: tipo=MOV/competencia=202601)
        # viram colunas. Essa informação está no CAMINHO, não dentro do arquivo.
        .option("cloudFiles.partitionColumns", particoes)
        .load(f"{LANDING}/{pasta}")
        # Auditoria: de qual arquivo veio cada linha e quando ela entrou.
        # Permite rastrear um número estranho da gold até o arquivo de origem.
        .withColumn("_arquivo_origem", F.col("_metadata.file_path"))
        .withColumn("_ingerido_em", F.current_timestamp())
    )


# -----------------------------------------------------------------------------
# Tabelas bronze: uma por fonte
#
# Os nomes são completos (catálogo.schema.tabela) porque o mesmo pipeline vai
# gravar também em silver e gold. O comment aparece no catálogo e é lido pelo
# Genie.
# -----------------------------------------------------------------------------

# CAGED: movimentações mensais de emprego formal (admissões e desligamentos).
# Junta os três tipos de arquivo; a coluna "tipo" diz de qual veio cada linha,
# e isso decide o sinal do saldo na silver (EXC entra invertido).
# Os arquivos EXC têm 2 colunas a mais (competenciaexc, indicadordeexclusao),
# que ficam NULL nas linhas de MOV e FOR.
@dp.table(
    name="brazil_employment.bronze.caged_movimentacao",
    comment="Novo CAGED (MOV/FOR/EXC) recortado para a RMF, como veio da fonte",
)
def caged_bronze():
    return _auto_loader("caged", "tipo,competencia")


# RAIS: estoque anual de vínculos formais (inclui servidores públicos).
@dp.table(
    name="brazil_employment.bronze.rais_vinculo",
    comment="RAIS Vínculos públicos recortada para a RMF, como veio da fonte",
)
def rais_bronze():
    return _auto_loader("rais", "ano_base")


# PNAD Contínua: amostra de domicílios, inclui informais e desocupados.
@dp.table(
    name="brazil_employment.bronze.pnad_pessoa",
    comment="PNAD Contínua, pessoas da RM de Fortaleza (RM_RIDE=23), como veio da fonte",
)

def pnad_bronze():
    # "" = ignorar as colunas do caminho: ano e trimestre já existem DENTRO do
    # arquivo. Declarar as duas duplicava a informação e enchia o _rescued_data.
    return _auto_loader("pnad", "")


# RAIS do Ceará inteiro, só 3 colunas (município, vínculo ativo, classe CNAE).
# Existe para o quociente locacional, que compara cada município com o estado.
@dp.table(
    name="brazil_employment.bronze.rais_ceara_vinculo",
    comment="RAIS Vínculos do Ceará inteiro (UF 23), só as colunas do quociente locacional, como veio da fonte",
)
def rais_ceara_bronze():
    return _auto_loader("rais_ceara", "ano_base")
