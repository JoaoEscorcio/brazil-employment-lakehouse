# Genie space: Observatório do Emprego Jovem · RMF

Natural-language questions (in Portuguese) over the gold layer, linked to the
dashboard through the "Ask Genie" button (`uiSettings.genieSpace` in
`dashboards/observatorio.lvdash.json`).

The space is deployed by the Asset Bundle: its full definition lives in
[`resources/genie.yml`](../resources/genie.yml).

## What the space contains

| Part | Purpose |
|---|---|
| `data_sources.tables` | The 10 gold tables, as `${var.catalogo}.gold.<table>`: each target (dev, prod) queries its own catalog. Genie also reads the column `COMMENT`s defined in `src/pipelines/gold_*.sql` (units, how to aggregate, what `'Todos'` means). |
| `instructions.text_instructions` | The analyst's "manual": sources (CAGED = flow, RAIS = stock, PNAD = sample), definitions (youth = 15 to 29), calculation rules (median, never average; never sum rates), period rules, and what the data cannot answer. |
| `instructions.example_question_sqls` | 8 questions with the correct SQL. Genie uses them as templates for similar questions. |

Design principle: when Genie answers wrong because a dimension is missing,
fix the gold model, not the prompt (e.g. the median salary by sector was
added to `caged_salario_mediano` instead of instructing Genie to apologise).

## Editing

Edit `resources/genie.yml` and deploy (`databricks bundle deploy -t <target>`).

If the space was edited in the UI, bring the changes back before the next
deploy, otherwise the deploy overwrites them:

```bash
databricks bundle generate genie-space --existing-id <space_id> --key observatorio_genie
```

Then put `${var.catalogo}` back in place of the catalog name in the generated
table identifiers and SQL examples.

## Known limitation

The dashboard's "Ask Genie" button stores the space id inside the dashboard
file, which the bundle does not template. The prod dashboard points to the
prod space; the dev dashboard points to the prod space too.
