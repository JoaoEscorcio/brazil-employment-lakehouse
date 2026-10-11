# Genie space: Observatório do Emprego Jovem · RMF

Natural-language questions (in Portuguese) over the gold layer, linked to the
dashboard through the "Ask Genie" button (`uiSettings.genieSpace` in
`dashboards/observatorio.lvdash.json`).

## What the space contains

`observatorio_space.json` is the full configuration exported with the Genie API:

| Part | Purpose |
|---|---|
| `data_sources.tables` | The 10 gold tables. Genie also reads the column `COMMENT`s defined in `src/pipelines/gold_*.sql` (units, how to aggregate, what `'Todos'` means). |
| `instructions.text_instructions` | The analyst's "manual": sources (CAGED = flow, RAIS = stock, PNAD = sample), definitions (youth = 15 to 29), calculation rules (median, never average; never sum rates), period rules, and what the data cannot answer. |
| `instructions.example_question_sqls` | 8 questions with the correct SQL. Genie uses them as templates for similar questions. |

Design principle: when Genie answers wrong because a dimension is missing,
fix the gold model, not the prompt (e.g. the median salary by sector was
added to `caged_salario_mediano` instead of instructing Genie to apologise).

## Export (workspace → repo)

```bash
databricks api get "/api/2.0/genie/spaces/<space_id>?include_serialized_space=true"
```

Keep `title`, `description` and `serialized_space` (parsed) in `observatorio_space.json`.

## Apply (repo → workspace)

Create a new space (another workspace) or update an existing one. The API
expects `serialized_space` as a JSON **string**:

```python
import json, subprocess
cfg = json.load(open("genie/observatorio_space.json", encoding="utf-8"))
body = {"title": cfg["title"], "description": cfg["description"],
        "warehouse_id": "<warehouse_id>",
        "serialized_space": json.dumps(cfg["serialized_space"], ensure_ascii=False)}
json.dump(body, open("body.json", "w", encoding="utf-8"), ensure_ascii=False)
# new space:      databricks api post  /api/2.0/genie/spaces --json @body.json
# update a space: databricks api patch /api/2.0/genie/spaces/<space_id> --json @body.json
```

After creating a space in a new workspace, put its id in the dashboard's
`uiSettings.genieSpace.overrideId`.
