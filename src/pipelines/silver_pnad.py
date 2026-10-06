# =============================================================================
# CAMADA SILVER: PNAD CONTÍNUA
# Uma linha por pessoa entrevistada na RM de Fortaleza, por trimestre.
# É uma AMOSTRA: qualquer número da população se calcula somando "peso",
# nunca contando linhas (cada pessoa representa ~500 moradores).
#
# Decisões do perfilamento (docs/perfilamento.md):
#   A2: zeros à esquerda ("045", "000411.81") -> inteiro / decimal_ponto
#   A3: sexo e raça com rótulos comuns (parda = 4 na PNAD)
#   A4: NULL significa "não se aplica" (ex.: menores de 14 anos não têm
#       condição na força de trabalho) e CONTINUA NULL. Virar 0 erraria
#       o denominador da taxa de desocupação.
# =============================================================================

from pyspark import pipelines as dp
from pyspark.sql import functions as F

from comum.colunas import decimal_ponto, faixa_etaria_col, inteiro, traduzir
from regras.codigos import RACA_PNAD, SEXO_PNAD
from regras.pnad import (
    NEGOCIO_SEM_CNPJ,
    POSICAO_DEPENDE_DE_CNPJ,
    POSICAO_FAMILIAR_AUXILIAR,
    POSICAO_SEM_CARTEIRA,
)


def em(coluna, codigos: set):
    return coluna.isin(sorted(codigos))


@dp.materialized_view(
    name="brazil_employment.silver.pnad_pessoa",
    comment=(
        "Pessoas entrevistadas pela PNAD Contínua na RM de Fortaleza. Amostra: "
        "somar 'peso' para estimar a população. NULL nas variáveis de trabalho "
        "significa 'não se aplica' (ex.: menores de 14 anos, não ocupados)."
    ),
)
@dp.expect_or_drop("peso_positivo", "peso > 0")
@dp.expect("sem_dados_resgatados", "_rescued_data IS NULL")
@dp.expect("idade_plausivel", "idade BETWEEN 0 AND 130")
def pnad_silver():
    b = spark.read.table("brazil_employment.bronze.pnad_pessoa")

    idade = inteiro("idade")
    posicao = inteiro("posicao_categoria")
    cnpj = inteiro("negocio_cnpj")

    # Informalidade (definição BID/MTE, regras/pnad.py). Só existe para quem
    # está ocupado: sem posição na ocupação, fica NULL ("não se aplica").
    informal = F.when(
        posicao.isNotNull(),
        em(posicao, POSICAO_SEM_CARTEIRA)
        | (em(posicao, POSICAO_DEPENDE_DE_CNPJ) & (cnpj == NEGOCIO_SEM_CNPJ))
        | em(posicao, POSICAO_FAMILIAR_AUXILIAR),
    )

    return b.select(
        inteiro("ano").alias("ano"),
        inteiro("trimestre").alias("trimestre"),
        (F.col("capital") == "23").alias("mora_em_fortaleza"),
        decimal_ponto("peso").alias("peso"),

        # --- quem (A3) -----------------------------------------------------------
        F.col("sexo").alias("sexo_codigo"),
        traduzir("sexo", SEXO_PNAD).alias("sexo"),
        F.col("cor_raca").alias("raca_cor_codigo"),
        traduzir("cor_raca", RACA_PNAD).alias("raca_cor"),
        idade.alias("idade"),
        faixa_etaria_col(idade).alias("faixa_etaria"),
        inteiro("nivel_instrucao").alias("nivel_instrucao_codigo"),

        # --- situação no mercado de trabalho (A4: NULL = não se aplica) --------
        inteiro("condicao_forca_trabalho").alias("condicao_forca_trabalho"),  # 1 na força, 2 fora
        inteiro("condicao_ocupacao").alias("condicao_ocupacao"),              # 1 ocupada, 2 desocupada
        inteiro("forca_trabalho_potencial").alias("forca_trabalho_potencial"),
        (inteiro("subocupacao") == 1).alias("subocupado"),
        (inteiro("desalento") == 1).alias("desalentado"),

        # --- a ocupação --------------------------------------------------------
        posicao.alias("posicao_ocupacao_codigo"),
        inteiro("grupamento_atividade").alias("grupamento_atividade_codigo"),
        inteiro("grupamento_ocupacional").alias("grupamento_ocupacional_codigo"),
        (inteiro("contribuicao_previdenciaria") == 1).alias("contribui_previdencia"),
        cnpj.alias("negocio_cnpj_codigo"),
        informal.alias("informal"),
        decimal_ponto("rendimento_habitual").alias("rendimento_habitual"),
        decimal_ponto("rendimento_efetivo").alias("rendimento_efetivo"),

        # --- auditoria ----------------------------------------------------------
        "_rescued_data",
        "_arquivo_origem",
    )
