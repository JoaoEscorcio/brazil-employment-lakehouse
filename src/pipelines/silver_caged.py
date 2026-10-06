# =============================================================================
# CAMADA SILVER: CAGED
# Uma linha por movimentação (admissão ou desligamento) da RMF, com tipos
# corrigidos, códigos traduzidos e o efeito no saldo calculado.
#
# Cada transformação responde a um achado do perfilamento (docs/perfilamento.md).
# Regra da camada: o valor original fica guardado ao lado do valor tratado,
# para qualquer número poder ser auditado contra a fonte.
# =============================================================================

from pyspark import pipelines as dp
from pyspark.sql import functions as F

from comum.colunas import decimal_virgula, faixa_etaria_col, inteiro, traduzir
from regras.codigos import RACA_CAGED, SEXO_CAGED
from regras.rmf import (
    RMF_MUNICIPIOS,
    SALARIO_MENSAL_MAX_SM,
    SALARIO_MENSAL_MIN_SM,
    SALARIO_MINIMO_POR_ANO,
    UNIDADE_SALARIO_MENSAL,
)


# Ano -> valor (ex.: salário mínimo). Anos fora do dicionário viram NULL.
def traduzir_ano(ano, dicionario: dict):
    expr = None
    for chave, valor in dicionario.items():
        expr = F.when(ano == chave, valor) if expr is None else expr.when(ano == chave, valor)
    return expr


RMF_SQL = ",".join(str(c) for c in RMF_MUNICIPIOS)


# -----------------------------------------------------------------------------
# Tabela silver
#
# Materialized view (A1): cada divulgação mensal reescreve meses passados (FOR
# e EXC). A MV recalcula a partir da bronze inteira, então uma correção que
# chega em janeiro atualiza setembro sozinha. Substitui o
# "descartar_carga_anterior" do Emprega+.
#
# Expectations:
#   expect_or_drop -> a linha corromperia o saldo: sai da tabela.
#   expect         -> só mede (aparece na aba Data quality); a linha fica,
#                     porque continua sendo uma movimentação válida.
# -----------------------------------------------------------------------------
@dp.materialized_view(
    name="brazil_employment.silver.caged_movimentacao",
    comment=(
        "Movimentações do Novo CAGED na RMF (MOV, FOR e EXC). Uma linha por "
        "movimentação; efeito = sinal no saldo (EXC invertido, NT 11/2021); "
        "competencia_mov = mês em que o fato ocorreu."
    ),
)
@dp.expect_or_drop("municipio_na_rmf", f"municipio_codigo IN ({RMF_SQL})")
@dp.expect_or_drop("efeito_valido", "efeito IN (-1, 1)")
@dp.expect("sem_dados_resgatados", "_rescued_data IS NULL")             # A0
@dp.expect("salario_convertido", "salario_informado IS NOT NULL")       # A2
@dp.expect("idade_plausivel", "idade BETWEEN 14 AND 100")
@dp.expect("tem_salario_mensal_plausivel", "salario_mensal IS NOT NULL")  # A5
def caged_silver():
    b = spark.read.table("brazil_employment.bronze.caged_movimentacao")

    idade = inteiro("idade")
    saldo = inteiro("saldomovimentacao")
    salario = decimal_virgula("salario")

    # A1: EXC entra com o sinal invertido no saldo
    efeito = saldo * F.when(F.col("tipo") == "EXC", -1).otherwise(1)

    # A5: salário mensal só quando a unidade é "mês" e o valor é plausível
    # A régua é o salário mínimo do ANO da movimentação (2025 != 2026).
    ano_mov = (inteiro("competenciamov") / 100).cast("int")
    salario_minimo = traduzir_ano(ano_mov, SALARIO_MINIMO_POR_ANO)
    salario_mensal = F.when(
        (F.col("unidadesalariocodigo") == UNIDADE_SALARIO_MENSAL)
        & salario.between(SALARIO_MENSAL_MIN_SM * salario_minimo,
                          SALARIO_MENSAL_MAX_SM * salario_minimo),
        salario,
    )

    return b.select(
        # --- de onde veio (A1) -------------------------------------------------
        F.col("tipo").alias("origem_arquivo"),
        F.col("competencia").alias("competencia_divulgacao"),
        inteiro("competenciamov").alias("competencia_mov"),
        inteiro("competenciadec").alias("competencia_dec"),
        inteiro("competenciaexc").alias("competencia_exc"),

        # --- onde e em que setor ----------------------------------------------
        inteiro("municipio").alias("municipio_codigo"),
        F.col("secao").alias("cnae_secao"),
        F.col("subclasse").alias("cnae_subclasse"),
        F.col("cbo2002ocupacao").alias("cbo_codigo"),

        # --- o fato e o efeito no saldo (A1) -----------------------------------
        saldo.alias("saldo_movimentacao"),
        efeito.alias("efeito"),
        inteiro("tipomovimentacao").alias("tipo_movimentacao"),
        F.col("categoria").alias("categoria_codigo"),

        # --- quem (A3 + A4): código original ao lado do rótulo comum ----------
        F.col("sexo").alias("sexo_codigo"),
        traduzir("sexo", SEXO_CAGED).alias("sexo"),
        F.col("racacor").alias("raca_cor_codigo"),
        traduzir("racacor", RACA_CAGED).alias("raca_cor"),
        inteiro("graudeinstrucao").alias("grau_instrucao_codigo"),
        idade.alias("idade"),
        faixa_etaria_col(idade).alias("faixa_etaria"),

        # --- jornada e salário (A2 + A5) ---------------------------------------
        decimal_virgula("horascontratuais").alias("horas_contratuais"),
        (F.col("indtrabparcial") == "1").alias("tempo_parcial"),
        (F.col("indtrabintermitente") == "1").alias("intermitente"),
        salario.alias("salario_informado"),
        F.col("unidadesalariocodigo").alias("unidade_salario_codigo"),
        salario_mensal.alias("salario_mensal"),

        # --- auditoria ----------------------------------------------------------
        "_rescued_data",
        "_arquivo_origem",
    )
