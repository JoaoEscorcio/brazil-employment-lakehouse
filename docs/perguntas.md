# Gold layer design: questions, grain and metrics

The gold layer is organised around the **questions a public manager asks**, not around the sources. This document lists every indicator, the gold table that answers it, the grain of that table and how each metric is computed. It is the task list for phase 11.

- **Starting point:** the 35 endpoints of the original Emprega+ observatory (FastAPI over Postgres), all reproduced here.
- **Inputs:** the validated silver layer (see [`perfilamento.md`](perfilamento.md) for the data decisions behind it).

## Design principles

### 1. The three sources answer different questions and never add up

| Source | Measures | Unit | Can | Cannot |
|--------|----------|------|-----|--------|
| CAGED | **Flow** of formal (CLT) jobs | month | sum hires and balances across months | say how many jobs exist |
| RAIS | **Stock** of formal contracts, including civil servants | year (Dec 31) | count active contracts | show monthly change; be added to CAGED |
| PNAD | **Sample** of households, formal and informal | quarter | estimate rates for the whole metro region | fine cuts by municipality or age; count rows without weights |

The dashboard keeps one page per source for this reason.

### 2. Additive vs non-additive measures

A gold table is filtered by the dashboard in many ways (municipality, age band, sex...). Measures fall into two groups:

- **Additive** (counts, sums): hires, separations, balance, stock, sum of wages. Summing them across any filter is correct. These are stored at a fine grain.
- **Non-additive** (median, Gini, rates, averages): the median of Fortaleza plus the median of Caucaia is not the median of both. These are either:
  - stored as **numerator and denominator** (e.g. `soma_remuneracao` and `n_com_remuneracao`, so the average is `SUM(soma) / SUM(n)` under any filter), or
  - **pre-computed for each cut the dashboard uses** (median, Gini, turnover, PNAD rates).

### 3. Time window and revisions (finding A1)

- CAGED: rolling window of the **12 months up to the latest MOV release**, by `competencia_mov` (event month). Older months that arrive through FOR/EXC files are excluded.
- The **3 most recent months are flagged `preliminar`**: they will still be revised by future FOR/EXC files.

### 4. Other rules

- **Salary is reported by the median**, not the mean (finding A5). This differs from Emprega+ on purpose.
- **Monthly salary plausibility uses the minimum wage of the movement's year** (R$ 1,518 in 2025, R$ 1,621 in 2026).
- **PNAD:** every population figure is a sum of `peso`; only at metro-region level, Fortaleza-only, or large cuts such as sex.
- **RAIS stock** counts only `ativo_31_12`. Public administration (subsector 24) has no company size (finding A7).

## Gold tables

| Table | Grain (one row is...) | Type of measures |
|-------|-----------------------|------------------|
| `caged_fluxo` | month x municipality x age band x sex x race x CNAE section x education x salary band | additive |
| `caged_ocupacoes` | month x municipality x age band x sex x CBO occupation | additive |
| `caged_salario_mediano` | month x municipality x age band x sex, plus "all" rows for each dimension | non-additive, pre-computed |
| `rais_estoque` | municipality x CNAE section x company size x age band x sex x race x education x weekly hours band x income band | additive + numerator/denominator |
| `rais_ocupacoes` | municipality x CBO occupation | additive + numerator/denominator |
| `rais_indicadores_municipio` | municipality (plus one row for the whole metro region) | non-additive, pre-computed |
| `rais_quociente_locacional` | municipality x CNAE section | non-additive, pre-computed |
| `pnad_mercado_trabalho` | quarter x area (Fortaleza / rest of the metro region) x sex x age band x race group | additive weighted components (sums of `peso`) |
| `pnad_indicadores` | quarter x area (metro region / Fortaleza) x sex x public (all / young people 15-29), "all" included | non-additive, pre-computed from the components |
| `pnad_posicao_ocupacao` | quarter x area x position in occupation | additive (weighted) |

## Indicators

### CAGED: formal job flow (monthly)

Filters available on every indicator: period, municipality, age band, sex, CNAE section.

| Question | Indicator | Gold table | Computation | Emprega+ endpoint |
|----------|-----------|------------|-------------|-------------------|
| Is formal youth employment growing? | Hires, separations, balance | `caged_fluxo` | `SUM(admissoes)`, `SUM(desligamentos)`, `SUM(saldo)` | `/kpis`, `/evolucao-mensal` |
| What share of hires are young people? | % of hires aged 15-29 | `caged_fluxo` | hires in 15-17, 18-24, 25-29 / all hires | `/kpis` |
| How many hires are apprentices? | % apprentices | `caged_fluxo` | hires with category 103 / all hires | `/kpis` |
| Which sectors hire the most? | Hires and balance by CNAE section | `caged_fluxo` + `dim_caged_codigo` | ranking | `/setores` |
| Which occupations hire the most? | Hires and balance by CBO | `caged_ocupacoes` + `dim_caged_codigo` (domain `cbo2002ocupacao`) | ranking | `/ocupacoes` |
| Who is being hired? | Hires by age band, education, sex, race | `caged_fluxo` | counts | `/perfil` |
| What is the entry salary? | **Median** monthly salary at hiring | `caged_salario_mediano` | `percentile_approx(salario_mensal, 0.5)` over hires | `/kpis` (was the mean) |
| How are entry salaries distributed? | Hires by salary band (minimum wages of the year) | `caged_fluxo` | counts by `faixa_salarial_sm` | `/perfil` |

### RAIS: formal job stock (December 31)

Filter available: municipality.

| Question | Indicator | Gold table | Computation | Emprega+ endpoint |
|----------|-----------|------------|-------------|-------------------|
| How many formal jobs exist? | Active contracts | `rais_estoque` | `SUM(vinculos)` | `/kpis` |
| How educated is the workforce? | % with complete secondary or more; stock by education (and by sex) | `rais_estoque` | counts | `/kpis`, `/escolaridade`, `/escolaridade-sexo` |
| Who holds the jobs? | Stock by age band, sex, race | `rais_estoque` | counts | `/faixa-etaria`, `/estoque-sexo` |
| What are the main occupations? | Stock and average wage by CBO; by CBO major group | `rais_ocupacoes` | counts; `SUM(soma_remuneracao)/SUM(n_com_remuneracao)` | `/ocupacoes`, `/grupamento-ocupacao` |
| Where do people work? | Stock by company size (official BID/MTE size) | `rais_estoque` | counts | `/porte-oficial` |
| How important are micro and small firms? | % of stock in micro/small companies, by sector | `rais_estoque` | counts | `/porte-atividade` |
| How much do jobs pay? | Average wage, by sector, by income band (minimum wages) | `rais_estoque` | numerator/denominator; counts by band | `/kpis`, `/salario-setor`, `/faixa-renda` |
| How many hours? | Stock by weekly hours band | `rais_estoque` | counts | `/faixa-horas` |
| How unequal are wages? | Gini of average wage | `rais_indicadores_municipio` | pre-computed | `/gini` |
| Wage gaps | Women/men, black/white, large/small firm wage ratios | `rais_indicadores_municipio` | pre-computed ratios of averages | `/rendimentos` |
| Wage per hour | Average wage per contracted hour | `rais_indicadores_municipio` | `SUM(wage) / SUM(hours x 4.345)` | `/salario-hora` |
| How long do people stay? | Average tenure (months), overall and by sector | `rais_indicadores_municipio` | pre-computed | `/tempo-emprego` |
| How unstable are jobs? | Turnover rate (DIEESE method) | `rais_indicadores_municipio` | min(hires, separations) / stock, excluding statutory and voluntary/death/retirement/transfer separations | `/rotatividade` |
| What is the region specialised in? | Location quotient by sector, vs the state of Ceará | `rais_quociente_locacional` | (sector share in municipality) / (sector share in Ceará) | `/quociente-locacional` |

### PNAD: labour market context (quarterly)

Filter available: quarter, metro region or Fortaleza only.

| Question | Indicator | Gold table | Computation (all weighted by `peso`) | Emprega+ endpoint |
|----------|-----------|------------|--------------------------------------|-------------------|
| How many people can and want to work? | Working-age population (14+), labour force, % women in labour force | `pnad_indicadores` | sums of weights | `/kpis`, `/populacao` |
| How many are unemployed, and how many young people? | Unemployment rate (all and 15-29), and its evolution | `pnad_indicadores` | unemployed / labour force | `/kpis`, `/evolucao` |
| How much work is informal? | Informality rate, among all and among women | `pnad_indicadores` | informal / employed (BID/MTE definition) | `/informalidade`, `/informalidade-conta-propria` |
| How many work on their own? | % self-employed | `pnad_indicadores` | self-employed / employed | `/informalidade-conta-propria` |
| How many contribute to social security? | % contributing | `pnad_indicadores` | contributors / employed | `/contribuicao-previdenciaria` |
| How much labour is underused? | Underemployment, discouragement, underutilisation rates | `pnad_indicadores` | official BID/MTE formulas | `/subocupacao-desalento` |
| How much do workers earn? | Usual income; women/men, black/white, informal/formal ratios | `pnad_indicadores` | weighted averages and ratios | `/rendimentos` |
| Is income growing in real terms? | Nominal vs real usual income | `pnad_indicadores` + `dim_pnad_deflator` | income x IBGE deflator for Ceará | `/evolucao-rendimento` |
| What kind of jobs? | Employed by position in occupation | `pnad_posicao_ocupacao` | sums of weights | `/categoria-ocupacao` |

### Implementation note: PNAD

Rates do not add up, but sums of weights do: unemployed people in Fortaleza plus unemployed people in the rest of the metro region are the unemployed of the metro region. So the PNAD gold has a base table of **weighted components** (`pnad_mercado_trabalho`) and a table of **ready rates** (`pnad_indicadores`) computed from it for the cuts the dashboard uses. Any other cut is `SUM(component) / SUM(component)` over the base table. Both tables carry the number of people actually interviewed, and `amostra_suficiente` is false when fewer than 30 unemployed people were interviewed in that cut.

Reconciled with Emprega+ for 2026 Q2 (metro region and Fortaleza): labour force, employed, unemployed, unemployment, informality, self-employment, social security, underemployment, discouragement, underutilisation, average income and the three income ratios are all identical.

## Questions the data cannot answer

| Question | Why not | Finding |
|----------|---------|---------|
| How many young people got their **first job**? | 99.97% of CAGED hires have admission type "ignored" | A6 |
| Employment **by neighbourhood** of Fortaleza | RAIS neighbourhood columns are not filled in the public microdata | A6 |
| Unemployment **by municipality** or fine age bands | PNAD sample has ~250 unemployed people per quarter in the metro region | A6 |
| Total employment = CAGED + RAIS | Flow and stock measure different things | principle 1 |

## Reference data added for the gold layer

| Data | Official source | Silver table |
|------|-----------------|--------------|
| CBO occupation names (2,778 codes) | `cbo2002ocupação` sheet of the CAGED layout (MTE) | `dim_caged_codigo` (domain `cbo2002ocupacao`) |
| PNAD deflators for Ceará (58 quarters) | IBGE deflator file `deflator_PNADC_2026_trimestral` | `dim_pnad_deflator` |
| RAIS for the whole state of Ceará (municipality, active flag, CNAE class) | `RAIS_VINC_PUB_NORDESTE` (MTE), filtered to UF 23 | `bronze.rais_ceara_vinculo` -> `rais_estoque_ceara_secao` |

Validation against Emprega+: deflators identical; Ceará stock 2,068,766 vs 2,068,762 in Emprega+. The 4 extra contracts have CNAE class `99999` ("ignored"), which Emprega+ dropped; here they are kept with a NULL section and measured by the `tem_secao_cnae` expectation.

## Open points

- Port the exact DIEESE turnover exclusions from the Emprega+ materialised view before building `rais_indicadores_municipio`.
- Decide whether the location quotient compares against Ceará (as in Emprega+, following the BID/MTE glossary) or also against the metro region.
