# AI Data Analyst — Natural Language to SQL & Business Insights

An agentic analytics assistant that lets you ask business questions in
plain English and get back validated SQL, a business-friendly
explanation, and a chart — over your own PostgreSQL database.

```
User: "Why did revenue fall in August 2025?"
  -> Intent classification
  -> Schema discovery
  -> SQL generation (schema-aware)
  -> SQL safety validation
  -> PostgreSQL execution (read-only role)
  -> Self-repair on failure (bounded retries)
  -> Insight generation (facts vs. hypotheses)
  -> Bounded autonomous investigation (e.g. drill into category/region)
  -> Chart selection + Plotly rendering
  -> Final answer
```

## Architecture

```
Streamlit UI
     |
     v
 LangGraph agent  --------------------->  PostgreSQL (read-only role)
     |
     v
   OpenAI (via langchain-openai)
```

See `src/agent/graph.py` for the exact node graph and
`docs`-style diagram in its module docstring.

## Project layout

```
ai-data-analyst/
├── app.py                   Streamlit UI
├── scripts/
│   ├── init_db.sql          Schema + indexes + read-only role
│   └── seed_database.py     Realistic synthetic data generator
├── src/
│   ├── config.py            Env-driven settings
│   ├── database.py          Engine + guarded read-only execution
│   ├── schema_service.py     Live schema discovery (allowlisted tables)
│   ├── sql_guard.py         Programmatic SQL safety validation
│   ├── models.py            Pydantic structured-output schemas
│   ├── prompts.py           All LLM prompt templates
│   ├── analytics.py         Deterministic numeric calculations
│   ├── charts.py            Plotly chart construction
│   ├── business_metadata.py Metric/dimension semantic layer
│   └── agent/
│       ├── state.py         Shared LangGraph state
│       ├── nodes.py         Every node implementation
│       ├── routing.py       Conditional edge logic
│       └── graph.py         Graph wiring + compiled `graph`
├── tests/                   pytest suite (see "Testing" below)
└── evaluation/questions.json
```

## Setup

### 1. Requirements

- Python 3.11+
- A PostgreSQL 14+ instance (local, Docker, or managed — Neon/Supabase/RDS all work)
- An OpenAI API key

### 2. Install

```bash
python -m venv venv
source venv/bin/activate      # venv\Scripts\activate on Windows
pip install -r requirements.txt
```

### 3. Configure

```bash
cp .env.example .env
```

Fill in `.env`:

```
DATABASE_URL=postgresql+psycopg://ai_readonly:change_me_readonly@localhost:5432/ai_analytics
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini
```

### 4. Create the schema + read-only role

If you're running Postgres yourself (not via the provided
docker-compose):

```bash
psql "postgresql://<admin-user>@localhost:5432/ai_analytics" -f scripts/init_db.sql
```

This creates the tables, indexes, and a restricted `ai_readonly` role
that only has `SELECT`. **Change the password in `init_db.sql` before
using this anywhere but local dev.**

### 5. Seed realistic data

The seed script needs **write** access, so it must NOT use the
read-only role your app uses. Point it at an admin connection via
`SEED_DATABASE_URL`:

```bash
SEED_DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/ai_analytics \
  python scripts/seed_database.py
```

This generates ~2,000 customers, 200 products, and ~15,000 orders with
intentional patterns (a December seasonal lift, and a deliberate
August-2025 Electronics dip) so the agent has something real to find —
see `scripts/seed_database.py` for the exact rules, and adjust
`NUM_CUSTOMERS` / `NUM_ORDERS` if you want a larger dataset.

### 6. Run

```bash
streamlit run app.py
```

Open http://localhost:8501.

## Run with Docker instead

```bash
docker compose up -d postgres
# wait a few seconds for Postgres to initialize, then seed it:
SEED_DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/ai_analytics \
  python scripts/seed_database.py
docker compose up -d app
```

Set `OPENAI_API_KEY` in your shell (or a `.env` next to
`docker-compose.yml`) before the last step.

## Testing

```bash
pytest
```

- `test_sql_guard.py`, `test_analytics.py`, `test_charts.py` run with
  **no external dependencies** — they're pure unit tests.
- `test_database.py`, `test_schema.py`, `test_agent.py` are
  integration tests that auto-skip unless `DATABASE_URL` (and, for
  `test_agent.py`, `OPENAI_API_KEY`) are set. Run them against your
  seeded database once it's up.

`evaluation/questions.json` is a small evaluation set you can script
against the compiled `graph` to track SQL execution success rate,
unsafe-query rejection rate, and retry counts over time (see project
blueprint section 65 for the metrics to track — measure these
yourself; don't put invented numbers on a resume).

## Security model (defense in depth)

1. **Prompt-level instructions** tell the model to generate read-only
   SQL only. This is the weakest layer — never rely on it alone.
2. **`src/sql_guard.py`** parses every generated query with `sqlglot`
   and rejects anything that isn't a single `SELECT`/`WITH...SELECT`,
   plus a keyword blocklist (`DELETE`, `DROP`, `ALTER`, etc.) as a
   fast first pass.
3. **The database connection itself** uses the `ai_readonly` role
   (`SELECT`-only grants) and each query additionally runs inside a
   `SET TRANSACTION READ ONLY` block with a statement timeout and a
   hard row cap (`MAX_QUERY_ROWS`). Even if layers 1–2 were somehow
   bypassed, Postgres itself refuses to execute a write.

Known trade-off: the keyword blocklist in `sql_guard.py` is
intentionally blunt — it will also reject a legitimate query that
merely *mentions* a blocked word inside a string literal (e.g.
filtering on a customer name containing "drop"). That's a rare false
positive we accept in exchange for a simple, auditable safety check.

Schema discovery is also allowlisted (`schema_service.ALLOWED_TABLES`)
so the model never learns that other tables (or a future
`agent_query_logs` audit table) even exist.

## Notes on the agent graph

- Each node is a plain function returning a partial state update —
  see `src/agent/nodes.py`. Nothing hidden in classes or callbacks.
- SQL repair is bounded by `MAX_SQL_RETRIES` (default 2) to avoid an
  infinite fix-and-fail loop.
- The "why did X happen" investigation loop (`investigation_node`) is
  bounded by `MAX_INVESTIGATION_STEPS` (default 2) for the same reason.
- Conversation memory uses LangGraph's `InMemorySaver` keyed by
  `thread_id`, generated per Streamlit session and reset by the "New
  Conversation" button. Swap in
  `langgraph-checkpoint-postgres` before deploying multiple app
  instances, since in-memory state won't survive a restart or be
  shared across processes.
- Numeric calculations (percent change, rankings, summary stats) are
  computed in `src/analytics.py` with pandas, never by the LLM — the
  LLM only explains numbers that were already computed deterministically.

## What's implemented vs. left as an extension

Implemented: schema-aware NL→SQL, SQL validation + read-only DB role,
execution, self-repair, deterministic analytics, insight generation
with fact/hypothesis separation, bounded autonomous investigation,
automatic chart selection, multi-turn memory, Streamlit UI with SQL
explanation/download/new-conversation, Docker Compose, pytest suite,
evaluation dataset.

Deliberately left out (see project blueprint section 93 "future
enterprise features") since they're not needed to demonstrate the
core agentic pattern: FastAPI service layer, auth/RBAC, query audit
log *writes* (the table exists in `init_db.sql`; nothing writes to it
yet), LangSmith tracing, multi-database support, scheduled reports.
Each is a reasonably contained addition on top of this graph if you
want to extend it.

## Talking about this project (interview-style summary)

This is an agentic AI analytics assistant that converts natural
language into validated PostgreSQL, executes it under a read-only
role, and turns the result into a business explanation with a chart.
The agentic part isn't a single prompt→SQL→answer call — it's a
LangGraph state machine that validates its own output, repairs failed
SQL by feeding the database error back into a correction prompt (up
to a retry limit), and can decide mid-analysis that it needs to run
one more query before it can responsibly answer a "why" question.
Numeric calculations happen in pandas, not the LLM, to keep the
reported numbers trustworthy; the insight-generation step is
explicitly prompted to separate observed facts from hypotheses so it
doesn't state a guessed cause as if it were confirmed.
