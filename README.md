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
python -m pytest ai_job_agent/tests/test_filter.py ai_job_agent/tests/test_rank.py ai_job_agent/tests/test_skill_extractor.py -v
```

Expected output (60 tests across filter and rank modules):

```
PASSED ai_job_agent/tests/test_filter.py::test_google_is_rejected
PASSED ai_job_agent/tests/test_filter.py::test_amazon_is_rejected
PASSED ai_job_agent/tests/test_filter.py::test_blacklist_is_case_insensitive
PASSED ai_job_agent/tests/test_filter.py::test_non_blacklisted_company_passes
PASSED ai_job_agent/tests/test_filter.py::test_partial_name_match_rejects
PASSED ai_job_agent/tests/test_filter.py::test_iowa_only_toggle_allows_ia
PASSED ai_job_agent/tests/test_filter.py::test_iowa_only_toggle_rejects_ne
PASSED ai_job_agent/tests/test_filter.py::test_mixed_batch_correct_counts
PASSED ai_job_agent/tests/test_filter.py::test_trace_file_is_written
... (21 filter tests)
PASSED ai_job_agent/tests/test_rank.py::test_skill_score_perfect_match
PASSED ai_job_agent/tests/test_rank.py::test_location_score_remote_is_highest
PASSED ai_job_agent/tests/test_rank.py::test_recency_score_recent_beats_stale
PASSED ai_job_agent/tests/test_rank.py::test_explanation_format_matches_demo
PASSED ai_job_agent/tests/test_rank.py::test_composite_weights_applied
PASSED ai_job_agent/tests/test_rank.py::test_results_sorted_descending
... (39 rank tests)
60 passed
```

> **Note:** `test_search.py` tests require the `serpapi` package from `requirements.txt` to be installed in your active environment.

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

---

## Stage 2 — Filter

### How it works

`FilterModule` applies three sequential filters to the structured jobs from Stage 1:

| Filter | Logic | Reason logged |
|---|---|---|
| **FAANG+ blacklist** | Rejects if company name contains any entry from `blacklist_companies` in `filter_config.yaml` | e.g. `"blacklisted company: amazon"` |
| **Startup heuristic** | Rejects if the job description contains startup signal keywords (e.g. `"series a"`, `"seed stage"`) | e.g. `"startup signal: 'series a'"` |
| **Location preference** | Rejects unless the job is in a preferred state, or is remote/hybrid | e.g. `"location not in preferred states; location='San Francisco, CA'"` |

Every job — whether it passes or is rejected — is recorded in a structured trace log with its `decision` and `reason`. This trace is saved to `data/processed/filter_trace_YYYY-MM-DD.json` and forms the **agent trace appendix** required by the assignment report.

### Configuration

**`config/filter_config.yaml`** — edit to customise the blacklist, startup signals, and default toggles:

```yaml
blacklist_companies:
  - google
  - amazon
  - meta
  - microsoft
  # ... (20 companies total)

startup_keywords:
  - "series a"
  - "seed stage"
  - "early stage"

toggles:
  iowa_only: false   # restrict to Iowa jobs only
  remote_only: false # restrict to fully remote jobs only
```

**`config/locations.yaml`** — edit to customise preferred states:

```yaml
preferred_states:           # Tier 1 — location score 80
  - IA  # Iowa
  - NE  # Nebraska
  - MO  # Missouri
  - IL  # Illinois
  # ... (10 states total)

middle_america_states:      # Tier 2 — location score 60
  - ND
  - SD
  - OK
  # ... (16 states total)

remote_acceptable: true
hybrid_acceptable: true
```

### Runtime toggle override

You can flip toggles at runtime without editing YAML by passing them to `FilterModule`:

```python
from ai_job_agent.src.modules.filter_module import FilterModule

# Iowa-only mode (e.g. for the demo filter toggle demonstration)
module = FilterModule(toggles={"iowa_only": True})
filtered_jobs = module.filter(structured_jobs)
```

### Output files

| File | What it contains |
|---|---|
| `data/processed/filtered_jobs_YYYY-MM-DD.json` | Jobs that passed all three filters |
| `data/processed/filter_trace_YYYY-MM-DD.json` | Full per-job decision log (PASS/REJECT + reason) |

---

## Stage 3 — Rank

### How it works

`RankModule` scores every filtered job on three dimensions and returns the **top 10** by composite score.

| Dimension | Weight | Method |
|---|---|---|
| **Skill match** | 50% | Jaccard similarity between job skills (required + preferred) and the user's skill profile |
| **Location** | 30% | Tier-based lookup: Remote=100, Hybrid=90, Preferred state=80, Middle America=60, Other=20 |
| **Recency** | 20% | Exponential decay: `100 × exp(−days_old / 30)`. Fresh postings score near 100; 30-day-old postings score ~37 |

**Composite score formula:**
```
total = 0.5 × skill_score + 0.3 × location_score + 0.2 × recency_score
```

Each ranked job also carries a human-readable **explanation string** required for the demo narration:

```
"72% skill match | preferred state (IA) | posted 3 days ago"
"100% skill match | remote | posted today"
"14% skill match | other | posted 45 days ago"
```

Every scored job is written to a trace log (`rank_trace_YYYY-MM-DD.json`) for the agent trace appendix.

### Configuration

**`config/rank_config.yaml`** — adjust weights and tier scores without touching code:

```yaml
weights:
  skill_match: 0.5   # 50%
  location: 0.3      # 30%
  recency: 0.2       # 20%

location_scores:
  remote: 100
  hybrid: 90
  preferred_state: 80
  middle_america: 60
  other: 20

recency_decay_days: 30   # half-life for exponential decay

top_n: 10          # jobs returned by rank()
top_n_tailor: 3    # top jobs passed to tailoring stage
```

### Usage

```python
from ai_job_agent.src.modules.rank_module import RankModule

user_skills = ["python", "tensorflow", "mlflow", "aws", "docker", "sql"]
module = RankModule(user_skills=user_skills)
ranked_jobs = module.rank(filtered_jobs)   # returns list of RankedJob (top 10)

# Each RankedJob exposes:
print(ranked_jobs[0].total_score)    # e.g. 78.5
print(ranked_jobs[0].explanation)    # e.g. "72% skill match | preferred state (IA) | posted 3 days ago"
print(ranked_jobs[0].job.title)      # underlying Job object
```

### Output files

| File | What it contains |
|---|---|
| `data/processed/ranked_jobs_YYYY-MM-DD.json` | Top-10 `RankedJob` records with scores and explanation |
| `data/processed/rank_trace_YYYY-MM-DD.json` | Full per-job score breakdown for all filtered jobs |

### Sample ranked output (JSON)

```json
{
  "title": "AI Engineer",
  "company_name": "Acme Analytics",
  "location": "Des Moines, IA",
  "total_score": 78.5,
  "skill_score": 83.33,
  "location_score": 80.0,
  "recency_score": 71.65,
  "explanation": "83% skill match | preferred state (IA) | posted 5 days ago"
}
```

---

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
├── .env.example               ← copy to .env and fill in your keys
├── requirements.txt
│
├── config/
│   ├── api_config.yaml        ← SerpAPI settings and retry config
│   ├── filter_config.yaml     ← FAANG+ blacklist, startup keywords, toggles
│   ├── locations.yaml         ← preferred states (Tier 1) and Middle America (Tier 2)
│   └── rank_config.yaml       ← scoring weights, location tier scores, top_n
│
├── data/
│   ├── raw/                   ← raw SerpAPI responses       (auto-created)
│   └── processed/             ← all pipeline output files   (auto-created)
│       ├── structured_jobs_YYYY-MM-DD.json   ← Stage 1: search output
│       ├── filtered_jobs_YYYY-MM-DD.json     ← Stage 2: filter output
│       ├── filter_trace_YYYY-MM-DD.json      ← Stage 2: per-job decision log
│       ├── ranked_jobs_YYYY-MM-DD.json       ← Stage 3: top-10 ranked output
│       └── rank_trace_YYYY-MM-DD.json        ← Stage 3: full score breakdown
│
├── logs/
│   └── app.log                ← timestamped log of all pipeline runs (auto-created)
│
├── scripts/
│   └── run_search.py          ← Stage 1 entry point
│
├── src/
│   ├── models/
│   │   ├── job.py             ← Job dataclass (all pipeline stages)
│   │   └── ranked_job.py      ← RankedJob dataclass (score + explanation)
│   ├── modules/
│   │   ├── search_module.py   ← Stage 1: SerpAPI search + skill extraction
│   │   ├── filter_module.py   ← Stage 2: FAANG+/startup/location filtering
│   │   └── rank_module.py     ← Stage 3: skill/location/recency scoring
│   └── utils/
│       ├── api_client.py      ← SerpAPIClient with retry logic
│       ├── logger.py          ← shared logger (console + file)
│       ├── skill_extractor.py ← NLP-based skill extraction
│       └── storage.py         ← save_json / load_json helpers
│
└── tests/
    ├── test_search.py         ← Stage 1 unit tests
    ├── test_skill_extractor.py
    ├── test_filter.py         ← Stage 2 unit tests (21 tests)
    └── test_rank.py           ← Stage 3 unit tests (39 tests)
```
