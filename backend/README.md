# Regex Pattern Matching Backend

Django + Celery + Redis + PostgreSQL + PySpark backend for natural-language regex generation and large-scale CSV/Excel replacement.

> **Monorepo note:** For full-stack Docker setup (UI + API + worker), use the root [`../README.md`](../README.md) and `docker compose up --build` from the repo root.

Dependencies are managed with **[uv](https://docs.astral.sh/uv/)** via `pyproject.toml` and `uv.lock`.

## Architecture

```text
Client ──► Django (Gunicorn) ──► PostgreSQL
              │                      ▲
              ├── Redis DB 1 (cache) │
              ├── Redis DB 0 (broker)│
              └── Celery worker ─────┘
                     ├── OpenAI (regex generation)
                     └── PySpark (CSV/XLSX → Parquet transform)
```

| Layer | Responsibility |
|---|---|
| `uploads/` | Upload API, column extraction, paginated result reads |
| `llmtoregex/` | Invoke/cancel/status API, LLM + Spark Celery tasks |
| `nltoregex/cache_utils.py` | Redis caching helpers |

## Redis configuration

| Redis DB | Purpose |
|---|---|
| `0` | Celery broker + result backend |
| `1` | Django cache (LLM regex, file columns, result pages, job status) |

Environment variables: `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND`, `REDIS_CACHE_URL`.

## Spark partitioning

`spark.sql.shuffle.partitions = 8` because jobs run in Spark **local** mode on a single worker with ~2 GB driver memory. For assessment-sized CSV/XLSX files this balances shuffle overhead against parallelism without producing many tiny Parquet files. Results are read back through PyArrow pagination.

## Quick start (Docker)

Use the **root** `docker-compose.yml` (includes frontend, worker, Flower):

```bash
cd ..   # repo root
cp .env.example .env
docker compose up --build
```

Services:

| Service | URL |
|---|---|
| Web app (UI) | http://localhost:3000 |
| API | http://localhost:8000 |
| Health | http://localhost:8000/api/health |
| Flower | http://localhost:5555 |

## Local development (uv)

```bash
cp .env.example .env
uv sync
export DJANGO_SETTINGS_MODULE=nltoregex.settings.local
uv run manage.py migrate
uv run manage.py runserver
# separate terminal
uv run celery -A nltoregex worker -l info --pool=solo
```

Requires PostgreSQL, Redis, Java 17+, and network access for Spark Excel JAR download on first run.

After changing dependencies:

```bash
uv lock
uv sync
```

## API endpoints

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/upload` | POST | Upload CSV or XLSX |
| `/api/uploads/<id>/status` | GET | Column list when ready |
| `/llm/invoke` | POST | Queue async job (`QUEUED` → worker) |
| `/llm/check_status_view/<job_id>` | GET | Poll status, progress, row counts |
| `/api/jobs/<job_id>/results?page=1` | GET | Paginated processed rows |
| `/llm/jobs/<job_id>/cancel` | POST | Cancel running job |
| `/api/health` | GET | DB + Redis health |
| `/api/metrics` | GET | Job counts + Celery task counters |

### Invoke body

```json
{
  "uploaded_file_id": "uuid",
  "natural_language_prompt": "find email addresses",
  "replacement_value": "REDACTED",
  "target_columns": ["Email"]
}
```

## Large dataset note

The pipeline uses PySpark vectorised transforms rather than row-by-row Python loops, so runtime scales with partitions rather than interpreter overhead. For assessment evidence, run a generated CSV with 100k–1M rows locally or via Docker and capture job timing from Flower or Celery logs.

```bash
uv run python scripts/generate_large_csv.py --rows 100000 --output large_test.csv
```

## Tests

```bash
DJANGO_SETTINGS_MODULE=nltoregex.settings.test uv run manage.py test uploads llmtoregex llmtoregex.test_task_progress uploads.test_metrics
```

Spark integration tests (require Java, default 5,000 rows):

```bash
DJANGO_SETTINGS_MODULE=nltoregex.settings.test INTEGRATION_TEST_ROWS=5000 uv run manage.py test llmtoregex.tests_integration
```

Generate a larger CSV for manual smoke testing:

```bash
uv run python scripts/generate_large_csv.py --rows 100000 --output large_test.csv
```

## Observability

| Tool | URL / endpoint |
|---|---|
| Flower | http://localhost:5555 (docker-compose) |
| Metrics API | http://localhost:8000/api/metrics |
| Health | http://localhost:8000/api/health |

Celery tasks publish `PROGRESS` state (visible in Flower/Redis) whenever job progress updates. The status API merges live Celery meta with persisted job rows.

Task counters (`tasks_started`, `tasks_succeeded`, `tasks_failed`, `tasks_total_runtime_ms`) are stored in Redis and exposed via `/api/metrics`.

## Trade-offs

- Uploads stream to a temp file in the web process (not fully in RAM), then move to storage in a background thread.
- Column validation reads header rows only (CSV/`openpyxl`); all row processing uses PySpark in Celery.
- Legacy `.xls` is rejected — use `.xlsx` or `.csv`.
- Progress uses row counts from Spark (`df.count()`) and updates after each target column transform.
- Regex validation blocks nested quantifiers and unsupported lookarounds; it is not a full ReDoS proof.
