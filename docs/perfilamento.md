# Data profiling: bronze layer

Before writing any silver rule, the three bronze tables were profiled to find what is wrong, odd or ambiguous in the data as published. Each finding below turns into a silver rule or a gold decision.

- **Notebook with all queries and outputs:** [`src/exploracao/01_perfil_bronze`](../src/exploracao/01_perfil_bronze) (in Portuguese)
- **Tables:** `bronze.caged_movimentacao` (995,781 rows), `bronze.rais_vinculo` (1,931,903), `bronze.pnad_pessoa` (46,644)
- **Scope:** Fortaleza Metropolitan Region (19 municipalities). CAGED 07/2025–06/2026, RAIS 2025, PNAD 2025Q1–2026Q2. Profiled on 2026-10-06.

## Summary

| # | Finding | Evidence | Risk if ignored | Decision |
|---|---------|----------|-----------------|----------|
| A0 | PNAD `ano`/`trimestre` existed both in the file and in the folder path | 46,644 rows (100%) landed in `_rescued_data` | The rescue column is the alarm for schema problems; always firing, it would hide a real one | **Fixed in bronze:** `partitionColumns = ""` for PNAD + full refresh. Now 0 rescued rows |
| A1 | Each monthly CAGED release rewrites past months | FOR files reach back to 07/2024, EXC to 01/2020; 4,133 rows refer to months before the project window | Inflated balance in the release month; isolated old months look like dramatic drops | Aggregate by `competenciamov` (event month), never by release month; silver as materialized view; explicit period filter in gold |
| A2 | Numbers are stored as text, with a different convention per source | CAGED uses decimal comma (`937,00`); RAIS uses decimal point and `.00` for zero; PNAD has leading zeros (`000786.34`, `070`). `CAST` fails; `try_cast` without cleaning nulls 100% of CAGED salaries silently | Pipeline crash, or every salary silently becomes NULL | Source-specific conversion per column, plus an expectation that counts failed conversions |
| A3 | The same concept has different codes in each source | Woman = **3** in CAGED, 2 in RAIS and PNAD. Mixed race (*parda*) = **3** in CAGED, **8** in RAIS, **4** in PNAD (most frequent code in all three) | Joining sources by code makes women disappear from CAGED and turns *pardo* people into *amarelo* in PNAD, with no error raised | Each source maps its codes to shared labels (conformed dimension), keeping the original code; unit test locks `SEXO_CAGED["3"] == "Mulher"` |
| A4 | Some values mean "unknown" or "not applicable" | CAGED `999` = not identified (34 rows); RAIS remuneration `.00` (202,672 rows); 1,374 PNAD rows with null labour-force status, **all** under 14 years old. Education code `80` is valid (postgraduate), not an error | "Unknown" becomes a fake category or drags averages down; turning PNAD nulls into 0 breaks the unemployment rate denominator | "Not identified" codes and RAIS `.00` become NULL; PNAD nulls stay NULL, with the meaning documented in the column comment |
| A5 | The salary unit in CAGED is unreliable | Monthly salaries of R$ 7.37 (= hourly minimum wage: 7.37 × 220 h = 1,621); "hourly" salaries with a median of R$ 1,113; 1,127 zeros; max R$ 1,362,163. Mean R$ 2,040 vs median R$ 1,658 | Mixing hourly and monthly values; averages pulled up by typos | `salario_mensal` only when unit = month **and** value between **0.3 and 30 minimum wages**; original value and unit kept. Gold always uses the **median** |
| A6 | Some questions cannot be answered with public microdata | 99.97% of CAGED hires have admission type 97 ("ignored"); RAIS neighbourhood columns hold a single value; RAIS has 586,019 closed contracts out of 1.93 M; PNAD has only 189–284 unemployed people per quarter in the sample | Promising impossible indicators (first job, by neighbourhood); overstating employment by 44%; unreliable fine-grained estimates | Drop constant RAIS columns; add `ativo_31_12`; employment stock counts active contracts only; PNAD only at metro-region level (or large cuts), always weighted; no "first job" indicator |
| A7 | RAIS IBGE subsector 24 is public administration, which has no company size | 351,914 contracts (18%) with no size; all have public legal nature (1xxx) and CNAE section O. Found by the `tem_porte` expectation in silver | An alarm that always fires hides real gaps; the original Emprega+ comment called code 24 "not in the official table" | Subsector 24 documented in `regras/rais.py`; `tem_porte` only alarms for non-public employers |
| A8 | Missing age fell into the last age band | 574 CAGED movements with no age were labelled "30+"; 64 RAIS contracts with age 0 (= not informed) were labelled "<15". Comparisons with NULL are never true, so the value slipped to the final `otherwise` | Invented ages in a youth dashboard; the same logic existed in Emprega+ | Age band is NULL ("Não informada" in gold) when age is missing or 0, both in `regras/rmf.py` and in `comum/colunas.py` |
| A9 | CBO codes lost their leading zero | 28 military occupation codes (e.g. `010105`) were stored as numbers in the official Excel layout and became `10105` | Those occupations would have no name after the join | Silver `dim_caged_codigo` left-pads CBO codes to 6 digits |
| A10 | Emprega+ counted excluded hires as hires | Gold vs Emprega+ for the 12-month window: same balance (28,810), but 509,288 vs 510,020 hires and 480,478 vs 481,628 separations. The gaps are exactly twice the EXC rows in the window: Emprega+ added +1 for each excluded hire, the gold adds -1 (NT 11/2021) | Hires and separations slightly overstated in the original dashboard | Gold sums `efeito` for both measures; difference documented as a correction, not a regression |
| A11 | Emprega+ counted unreported RAIS wages as R$ 0 in the wage per hour | 143,741 active contracts with average remuneration `.00` (not informed). Emprega+ kept them as 0 in the numerator while counting their hours: R$ 19.38/h vs R$ 21.38/h in the gold. Every other RAIS indicator matched exactly (stock, December wage, education, company size, turnover, Gini, location quotient) | Wage per hour understated by about 9% | `.00` is NULL since silver (A4), so contracts without reported pay leave both numerator and denominator |

## Details

### A5: salary plausibility rule

The minimum wage is the natural yardstick: R$ 1,621.00 is the most frequent salary in January 2026 (21,986 hires, 27% of the month).

Monthly-coded salaries (unit 5) by band of minimum wages (MW):

| Band | Hires | Avg. weekly hours | Part-time |
|------|------:|------------------:|----------:|
| zero | 184 | 36.4 | 44 |
| below 0.1 MW | 736 | 32.2 | 381 |
| 0.1 to 0.3 MW | 37 | 26.1 | 15 |
| 0.3 to 0.5 MW | 723 | 21.5 | 306 |
| 0.5 to 30 MW | 74,050 | 42.7 | 1,525 |
| above 30 MW | 30 | 44.0 | 0 |

- **Below 0.1 MW:** hourly values reported with the monthly unit.
- **0.3 to 0.5 MW:** legitimate part-time contracts (21.5 h/week on average). A cut at 1 MW would drop real workers.
- **Effect of the rule:** it keeps 74,773 of 75,576 monthly hires (98.9%); the median stays at R$ 1,658 and the mean moves from R$ 2,045 to R$ 2,010.
- **Rejected alternative:** converting hourly values to monthly (× 220). It would require guessing each person's working hours, for about 1% of hires.

### A7: found in silver, not in bronze

Not every finding shows up during profiling. This one came from a silver expectation (`tem_porte`) that failed on 351,914 RAIS contracts. All of them belong to IBGE subsector 24, *Administração pública direta e autárquica*: legal nature starting with 1 (public bodies) and CNAE section O (84116 general public administration, 84124 health and education regulation). Company size (micro to large) only applies to companies, so a NULL size is correct for the public sector. The expectation was refined, not the data.

### A8 to A10: found while building silver fixes and gold

Reconciliation is not only a way to confirm results: comparing the gold layer with Emprega+ (A10) exposed a small error in the original dashboard, and checking the gold joins exposed two data issues (A8, A9) that had been in place since the original project.

## Open points

- Confirm the official 2026 minimum wage before hard-coding it (R$ 1,621 was inferred from the data).
- Review the 0.3 / 30 MW thresholds once the silver layer exists, using all twelve months instead of January only.
