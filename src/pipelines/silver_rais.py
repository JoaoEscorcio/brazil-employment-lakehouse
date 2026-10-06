# =============================================================================
# CAMADA SILVER: RAIS
# Uma linha por vínculo de trabalho que existiu na RMF no ano-base (ativos em
# 31/12 e encerrados durante o ano). Tipos corrigidos, códigos traduzidos,
# seção CNAE e porte de empresa anexados por join.
#
# Decisões do perfilamento (docs/perfilamento.md):
#   A2: ponto decimal e espaços à esquerda -> decimal_ponto / inteiro (com trim)
#   A3: sexo e raça com rótulos comuns (mulher = 2 na RAIS)
#   A4: remuneração ".00" -> NULL (vínculo sem remuneração informada)
#   A6: colunas constantes (bairros, distritos, ano de chegada...) não entram;
#       ativo_31_12 vira booleano, e o filtro de estoque fica para a gold
# =============================================================================

from pyspark import pipelines as dp
from pyspark.sql import functions as F

from comum.colunas import decimal_ponto, faixa_etaria_col, inteiro, traduzir
from regras.codigos import RACA_RAIS, SEXO_RAIS
from regras.rais import SUBSETOR_ADMINISTRACAO_PUBLICA
from regras.rmf import RMF_MUNICIPIOS

RMF_SQL = ",".join(str(c) for c in RMF_MUNICIPIOS)


# A4: remuneração zero ".00" significa "não informada", não "ganhou zero".
def remuneracao(coluna: str):
    valor = decimal_ponto(coluna)
    return F.when(valor > 0, valor)


@dp.materialized_view(
    name="brazil_employment.silver.rais_vinculo",
    comment=(
        "Vínculos da RAIS na RMF (ano-base). Inclui encerrados no ano: para "
        "estoque de emprego, filtrar ativo_31_12 = true. Inclui servidores "
        "estatutários (o CAGED não)."
    ),
)
@dp.expect_or_drop("municipio_na_rmf", f"municipio_codigo IN ({RMF_SQL})")
@dp.expect("sem_dados_resgatados", "_rescued_data IS NULL")
@dp.expect("tem_secao_cnae", "cnae_secao IS NOT NULL")
# Setor público (subsetor 24) não tem porte por definição: só alarma se uma
# EMPRESA ficar sem porte.
@dp.expect("tem_porte", f"porte IS NOT NULL OR ibge_subsetor_codigo = {SUBSETOR_ADMINISTRACAO_PUBLICA}")
@dp.expect("idade_plausivel", "idade BETWEEN 14 AND 100")
def rais_silver():
    b = spark.read.table("brazil_employment.bronze.rais_vinculo")
    idade = inteiro("idade")

    vinculo = b.select(
        F.col("ano_base"),
        inteiro("municipio_codigo").alias("municipio_codigo"),

        # --- o vínculo ----------------------------------------------------------
        (inteiro("ind_vinculo_ativo_31_12_codigo") == 1).alias("ativo_31_12"),
        inteiro("tipo_vinculo_codigo").alias("tipo_vinculo_codigo"),
        inteiro("tipo_admissao_trabalhador_codigo").alias("tipo_admissao_codigo"),
        inteiro("mes_admissao_codigo").alias("mes_admissao"),
        inteiro("mes_desligamento_codigo").alias("mes_desligamento"),
        inteiro("motivo_desligamento_codigo").alias("motivo_desligamento_codigo"),
        inteiro("categoria_trabalhador_codigo").alias("categoria_trabalhador_codigo"),

        # --- o empregador -------------------------------------------------------
        inteiro("cnae_2_0_classe_codigo").alias("cnae_classe"),
        inteiro("cnae_2_0_subclasse_codigo").alias("cnae_subclasse"),
        inteiro("natureza_juridica_codigo").alias("natureza_juridica_codigo"),
        inteiro("ibge_subsetor_codigo").alias("ibge_subsetor_codigo"),
        inteiro("tamanho_estabelecimento_codigo").alias("tamanho_estabelecimento_codigo"),
        (inteiro("ind_estabelecimento_participante_simples_codigo") == 1).alias("optante_simples"),

        # --- o trabalhador (A3 + A4) -------------------------------------------
        F.trim("cbo_2002_ocupacao_codigo").alias("cbo_codigo"),
        F.col("sexo_codigo").alias("sexo_codigo"),
        traduzir("sexo_codigo", SEXO_RAIS).alias("sexo"),
        F.col("raca_cor_codigo").alias("raca_cor_codigo"),
        traduzir("raca_cor_codigo", RACA_RAIS).alias("raca_cor"),
        inteiro("escolaridade_apos_2005_codigo").alias("grau_instrucao_codigo"),
        idade.alias("idade"),
        faixa_etaria_col(idade).alias("faixa_etaria"),
        (inteiro("ind_portador_defic_codigo") == 1).alias("pcd"),

        # --- jornada e remuneração (A2 + A4) -----------------------------------
        inteiro("qtd_hora_contr").alias("horas_contratuais"),
        decimal_ponto("tempo_emprego").alias("tempo_emprego_meses"),
        remuneracao("vl_rem_media_nom").alias("remuneracao_media_nominal"),
        remuneracao("vl_rem_dezembro_nom").alias("remuneracao_dezembro_nominal"),

        # --- auditoria ----------------------------------------------------------
        "_rescued_data",
        "_arquivo_origem",
    )

    cnae = spark.read.table("brazil_employment.silver.dim_cnae_classe")
    porte = spark.read.table("brazil_employment.silver.dim_porte")

    return (
        vinculo
        .join(cnae, "cnae_classe", "left")
        .join(porte, ["ibge_subsetor_codigo", "tamanho_estabelecimento_codigo"], "left")
    )
