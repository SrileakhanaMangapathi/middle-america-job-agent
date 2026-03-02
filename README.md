# middle-america-job-agent

AI agent that discovers AI Engineer jobs at mid-sized Middle American companies, ranks them, and generates tailored applications.

---

## Quick-start: setup, verification, and running the search

### 1 — Prerequisites

| Requirement | Version |
|---|---|
| Python | 3.10 or newer |
| pip | any recent version |
| SerpAPI account | free tier gives 100 searches/month |

### 2 — Get your SerpAPI key

1. Go to <https://serpapi.com> and create a free account.
2. After signing in, open **Dashboard → API Key**.
3. Copy the key — it looks like a 64-character hex string.

> **Security reminder:** never paste a real key into `.env.example` or any file that is committed to Git. Only put real keys in `.env`, which is listed in `.gitignore` and is never committed.

### 3 — Create your `.env` file

```bash
# from the repository root
cp ai_job_agent/.env.example ai_job_agent/.env
```

Open `ai_job_agent/.env` in any editor and replace the placeholder values:

```dotenv
SERP_API_KEY=paste_your_64_char_serpapi_key_here
ANTHROPIC_API_KEY=your_anthropic_key_here   # optional for Stage 2
CLEARBIT_API_KEY=optional_clearbit_key       # optional
MAX_JOBS_PER_SEARCH=100
LOG_LEVEL=INFO
```

Only `SERP_API_KEY` is required to run the job search.

### 4 — Install dependencies

```bash
pip install -r ai_job_agent/requirements.txt
```

### 5 — Verify the setup

Run the unit tests (no API key required — they use mocks):

```bash
# from the repository root
python -m pytest ai_job_agent/tests/ -v
```

Expected output:

```
PASSED ai_job_agent/tests/test_search.py::test_generate_job_id_is_deterministic
PASSED ai_job_agent/tests/test_search.py::test_generate_job_id_differs_for_different_inputs
PASSED ai_job_agent/tests/test_search.py::test_generate_job_id_case_insensitive
PASSED ai_job_agent/tests/test_search.py::test_job_creation_defaults
PASSED ai_job_agent/tests/test_search.py::test_job_to_dict_serialisation
PASSED ai_job_agent/tests/test_search.py::test_deduplication_removes_duplicates
6 passed
```

### 6 — Run the job search

```bash
# from the repository root
python -m ai_job_agent.scripts.run_search
```

What happens step by step:

1. The script loads your key from `ai_job_agent/.env`.
2. `SearchModule` calls SerpAPI with query `"AI Engineer"` in `"United States"`.
3. Raw results are saved to `ai_job_agent/data/raw/raw_jobs_YYYY-MM-DD.json`.
4. Duplicate jobs are removed (same title + company + location).
5. Structured results are saved to `ai_job_agent/data/processed/structured_jobs_YYYY-MM-DD.json`.
6. All steps are logged to the console **and** to `ai_job_agent/logs/app.log`.
7. The script prints:

```
Jobs retrieved: <number>
```

### 7 — What to check after the run

| File | What it contains |
|---|---|
| `ai_job_agent/data/raw/raw_jobs_YYYY-MM-DD.json` | Raw SerpAPI response (array of job objects) |
| `ai_job_agent/data/processed/structured_jobs_YYYY-MM-DD.json` | Deduplicated, typed `Job` records |
| `ai_job_agent/logs/app.log` | Full timestamped log of the run |

### 8 — Troubleshooting

| Error | Fix |
|---|---|
| `EnvironmentError: SERP_API_KEY environment variable is not set` | Make sure `ai_job_agent/.env` exists and contains a valid `SERP_API_KEY=...` line |
| `ModuleNotFoundError: No module named 'serpapi'` | Run `pip install -r ai_job_agent/requirements.txt` |
| `serpapi.SerpApiClientException: Invalid API key` | Your key is wrong or expired — copy it again from <https://serpapi.com/dashboard> |
| `Jobs retrieved: 0` | SerpAPI returned no results; try broadening the query or check your account's remaining credits |

---

## Project structure

```
ai_job_agent/
├── .env.example          ← copy to .env and fill in your keys
├── requirements.txt
├── config/
│   └── api_config.yaml
├── data/
│   ├── raw/              ← raw SerpAPI responses (auto-created)
│   └── processed/        ← structured Job records (auto-created)
├── logs/                 ← app.log (auto-created)
├── scripts/
│   └── run_search.py     ← entry point
├── src/
│   ├── models/job.py     ← Job dataclass
│   ├── modules/search_module.py
│   └── utils/
│       ├── api_client.py
│       ├── logger.py
│       └── storage.py
└── tests/
    └── test_search.py
```
