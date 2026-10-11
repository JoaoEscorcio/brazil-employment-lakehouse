# Manutenção do Observatório

O que roda sozinho, o que precisa de alguém e onde mexer em cada caso.

## Automático (Job `observatorio-mensal`)

| Quando | O que acontece |
|---|---|
| Toda segunda, 07:00 (America/Fortaleza) | `src/extracao/caged_mensal` procura competências novas do CAGED no FTP do MTE e grava na landing as que faltam. |
| Se chegou competência nova | O pipeline `observatorio-lakehouse` atualiza bronze, silver e gold. A janela de 12 meses anda sozinha, e o dashboard mostra o período no indicador "Dados do CAGED". |
| Se nada chegou | O Job termina em poucos minutos sem rodar o pipeline. |
| Se algo falhar | E-mail de falha para o responsável. |

O código do Job vem do GitHub (branch `main`): mudanças só valem depois do commit.

## Manual

| Quando | O que fazer | Onde |
|---|---|---|
| **Janeiro, todo ano** | Incluir o salário mínimo oficial do ano em `SALARIO_MINIMO_POR_ANO`. O teste `test_salario_minimo_do_ano_corrente_esta_cadastrado` falha até isso ser feito. Atualizar também os valores citados nas descrições do dashboard (gráficos de salário). | `src/regras/rmf.py`, `dashboards/observatorio.lvdash.json` |
| **A cada trimestre** (PNAD Contínua, ~45 dias após o fim do trimestre) | Carregar o trimestre novo na landing e rodar o pipeline. | `ingestao_local/preparar_landing.py` (`pnad()`, `deflator_pnad()`) |
| **Uma vez por ano** (RAIS, normalmente no segundo semestre) | Carregar o ano novo da RAIS RMF e do Ceará e revisar os textos da página RAIS, que citam o ano-base. | `preparar_landing.py` (`rais()`, `rais_ceara()`), página RAIS do dashboard |
| Depois de mudar o dashboard pela interface | Exportar para o repositório e publicar de novo. | `dashboards/` |
| Depois de mudar o Genie pela interface | Exportar a configuração. | `genie/README.md` |

## Antes de cada commit

```bash
pip install -r requirements-dev.txt
pytest
```

Sem Java/PySpark na máquina, os testes de `src/comum` são pulados; os de `src/regras` sempre rodam.
