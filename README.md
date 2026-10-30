# IPL Text-to-SQL

Ask questions about IPL cricket (2008-2017) in plain English. An LLM writes the SQL,
guardrails validate it, and it runs read-only against a local SQLite database.

## Setup

```
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python scripts/load_db.py        # builds data/ipl.db from the CSVs in data/
```

Copy `.env.example` to `.env` and add your keys (`.env` is git-ignored):

```
LLM_PROVIDER=gemini              # default; or openai (paid)
GEMINI_API_KEY=...
GEMINI_MODEL=gemini-3.5-flash-lite
OPENAI_API_KEY=...               # only needed if LLM_PROVIDER=openai
OPENAI_MODEL=gpt-6-luna
```

## Run

```
streamlit run app.py                                  # web UI
python -m src.llm "Which team won the most matches?"  # question -> SQL only
python -m src.db "SELECT COUNT(*) FROM matches"       # run SQL through the guardrails
python -m src.schema                                  # print the schema the LLM sees
```

## How it works

```
question -> src/llm.py (prompt + schema) -> SQL
         -> src/guardrails.py (single SELECT, known tables only, LIMIT added)
         -> src/db.py (read-only connection, 10s timeout, 1000-row cap)
         -> table in the UI
```

| File | Purpose |
|---|---|
| `scripts/load_db.py` | Loads `matches.csv` and `deliveries.csv` into SQLite with indexes |
| `src/schema.py` | Reads the live schema and adds column notes and data quirks |
| `src/llm.py` | Calls OpenAI or Gemini, chosen by `LLM_PROVIDER` |
| `src/guardrails.py` | Validates SQL with sqlglot before it runs |
| `src/db.py` | Executes validated SQL on a read-only connection |
| `app.py` | Streamlit UI |
| `tests/` | Golden set of 20 questions with reference SQL and answers |

## Golden test set

20 questions (7 simple, 7 moderate, 6 hard). A result passes when it contains every
column of the reference answer with the same values and row order (numbers rounded
to 2 decimals).

```
python -m tests.run_golden                    # all 20
python -m tests.run_golden --id 18            # one question
python -m tests.run_golden --difficulty hard
python -m tests.run_golden --build            # regenerate reference answers
```

### Results (one run each unless noted)

| Model | Simple | Moderate | Hard | Total | Failed |
|---|---|---|---|---|---|
| gpt-4.1-mini (run 1) | 7/7 | 7/7 | 3/6 | 17/20 | 18, 19, 20 |
| gpt-4.1-mini (run 2) | 7/7 | 6/7 | 4/6 | 17/20 | 9, 18, 20 |
| gpt-6-luna | 7/7 | 7/7 | 5/6 | 19/20 | 18 |
| gpt-5.6-luna | 7/7 | 7/7 | 5/6 | 19/20 | 18 |
| gpt-5.4-mini | 7/7 | 7/7 | 4/6 | 18/20 | 18, 19 |
| gemini-3.5-flash-lite | 7/7 | 7/7 | 5/6 | 19/20 | 18 |

Notes:
- Q18 (best economy rate) failed on every model. They drop wide and no-ball runs
  from "runs conceded", giving 6.20 instead of 6.33.
- `gpt-4.1-mini` sometimes writes `NOT IN (..., NULL)`, which returns no rows
  (Q9, Q20). The newer models did not.
- Q19 passes using `matches.team1` as the team that batted first. That holds for
  all 636 matches in this dataset.
- Single runs are noisy; repeat runs before drawing firm conclusions.

## Known gaps and ideas

- Add a rule to the system prompt against `NULL` inside `NOT IN`, and a short
  example for rate statistics such as economy (different filters for numerator and
  denominator). Write new examples rather than copying the golden questions.
- Retry once on a SQL error (skipped deliberately; add if the test set shows
  frequent runtime errors).
- The UI shows no history and has not been checked in a browser.
