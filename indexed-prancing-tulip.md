# AI Job Application Agent - Architecture & Implementation Plan

## Context

This project builds an autonomous AI agent that searches for AI Engineer jobs at mid-sized Middle American companies, filters and ranks them by fit, and generates personalized resumes and cover letters. The goal is to automate the job application workflow while maintaining high quality and relevance, with built-in evaluation to measure effectiveness against human baselines.

**Why this is needed:** Job searching is time-consuming and repetitive. This agent will intelligently filter out unsuitable positions (FAANG+, startups), focus on mid-sized companies in preferred locations, and generate tailored applications that match the user's profile.

**Expected outcome:** A production-ready pipeline that takes job search queries and produces ranked job lists plus 3 tailored applications, with evaluation metrics (precision@10, interview yield) to validate quality.

---

## System Architecture Overview

```
[Requirements] → [Search] → [Filter] → [Rank] → [Tailor] → [Evaluate]
     ↓              ↓          ↓         ↓         ↓           ↓
  Templates    SerpAPI    FAANG+     Top 10    Claude    Metrics
  Resume        Jobs     Blacklist   Scored     API      Reports
  Config                 Startups    Jobs       Gen
```

**Data Flow:**
1. Load user requirements (resume, constraints, preferences)
2. Search jobs via SerpAPI → extract structured data
3. Filter out FAANG+, startups, non-Middle America
4. Rank remaining jobs by skill match, location, recency → top 10
5. Generate tailored resumes/cover letters for top 3 jobs
6. Evaluate against benchmark dataset (precision@10, interview yield)

---

## Implementation Stages

### Stage 1: Requirements Module
**Purpose:** Load and manage user data, constraints, and preferences

**Key Components:**
- Parse user's PDF/DOCX resume into structured format
- Load configuration files (filter rules, ranking weights, location preferences)
- Extract user's skill profile from resume
- Define constraints (company size, geography, exclusions)

**Critical File:** `src/modules/requirements_module.py`

**Data Models:**
```python
@dataclass
class SkillProfile:
    required_skills: List[str]      # Core competencies
    preferred_skills: List[str]     # Nice-to-have skills
    years_experience: dict          # {"Python": 5, "ML": 3}

@dataclass
class FilterConstraints:
    blacklist_companies: List[str]  # FAANG+ list
    min_company_size: int = 50      # Exclude startups
    max_company_size: int = 5000    # Exclude mega-corps
    preferred_states: List[str]     # User-configurable
    remote_acceptable: bool = True
```

**Dependencies:** PyPDF2/pdfplumber for PDF parsing, python-docx for Word docs

---

### Stage 2: Search Module
**Purpose:** Fetch job listings from SerpAPI and extract structured data

**Key Components:**
- SerpAPI client with rate limiting (100 calls/hour)
- Job data extraction: title, company, location, skills, salary, URL
- Skill extraction from job descriptions (NLP-based)
- Deduplication logic
- Store raw results as JSON

**Critical File:** `src/modules/search_module.py`

**Data Extraction Fields:**
```python
@dataclass
class Job:
    job_id: str                     # Unique identifier
    title: str                      # "Senior ML Engineer"
    company_name: str               # Company name
    location: str                   # "Des Moines, IA"
    required_skills: List[str]      # ["Python", "TensorFlow"]
    preferred_skills: List[str]     # ["AWS", "Docker"]
    salary_range: Optional[dict]    # {"min": 100k, "max": 150k}
    job_url: str                    # Application link
    description: str                # Full text
    posted_date: Optional[datetime]
    company_size: Optional[str]     # "51-200", "201-500"
    source: str = "SerpAPI"
    scraped_at: datetime
```

**API Integration:**
- Use `google-search-results` library (SerpAPI Python client)
- Query: "AI Engineer" + location modifiers
- Extract from `jobs_results` array
- Use spaCy NLP to extract skills from descriptions

---

### Stage 3: Filter Module
**Purpose:** Apply exclusion criteria to remove unsuitable jobs

**Key Components:**
- **FAANG+ Blacklist:** Google, Apple, Facebook/Meta, Amazon, Microsoft, Netflix, Uber, Airbnb, Twitter/X, Tesla, OpenAI
- **Startup Detection:** Heuristic for <50 employees
  - Check `company_size` field
  - Look for keywords: "seed funded", "series A/B", "early stage", "founding team"
  - Optional: API lookup (Clearbit/LinkedIn) with caching
- **Geographic Filter:** User-configurable state list (loaded from config)
- **Toggle Filters:** Support modes like "Iowa-only", "remote-only"

**Critical File:** `src/modules/filter_module.py`

**Filter Logic:**
```python
def apply_all_filters(jobs: List[Job], config: FilterConfig) -> List[Job]:
    jobs = [j for j in jobs if not is_faang_plus(j.company_name)]
    jobs = [j for j in jobs if not is_startup(j)]
    jobs = [j for j in jobs if matches_geography(j.location, config)]
    jobs = apply_toggle_filters(jobs, config.toggles)
    return jobs
```

**Test Toggles:**
- `iowa_only`: Only jobs in Iowa
- `remote_only`: Only remote positions
- `no_salary_filter`: Remove salary requirements

---

### Stage 4: Rank Module
**Purpose:** Score and rank filtered jobs by relevance

**Ranking Algorithm:**
- **Skill Match Score (50% weight):** Jaccard similarity between job requirements and user skills
  - Required skills match: heavily weighted
  - Preferred skills match: bonus points
  - Experience level alignment
- **Location Score (30% weight):**
  - Preferred states: 80 points
  - Middle America states: 60 points minimum
  - Remote/hybrid: 100/90 points
- **Recency Score (20% weight):** Exponential decay over 30 days

**Critical File:** `src/modules/rank_module.py`

**Output:**
```python
@dataclass
class RankedJob:
    job: Job
    skill_match_score: float    # 0-100
    location_score: float       # 0-100
    recency_score: float        # 0-100
    composite_score: float      # Weighted average
    rank: int                   # 1-10
```

**Weights (configurable in `config/rank_config.yaml`):**
```yaml
skill_match_weight: 0.5
location_weight: 0.3
recency_weight: 0.2
top_n: 10
```

---

### Stage 5: Tailoring Module
**Purpose:** Generate personalized resumes and cover letters for top 3 jobs

**Key Components:**
- **Claude API Integration:** Use claude-3-5-sonnet-20241022 model
- **Resume Generation:** Tailor user's resume to highlight relevant skills/experience
- **Cover Letter Generation:** Create personalized cover letter for each job
- **Prompt Engineering:** Structured prompts that include job details + user profile
- **Human Scoring Interface:** Simple CLI/web interface for 1-5 scoring
- **Output Formats:** Markdown → PDF conversion

**Critical File:** `src/modules/tailoring_module.py`

**Generation Workflow:**
```python
for job in top_3_jobs:
    # Build context-rich prompt
    prompt = build_resume_prompt(job, user_resume, skill_profile)

    # Call Claude API
    resume_text = claude_api.generate(prompt, max_tokens=4000)

    # Save output
    save_as_pdf(resume_text, f"resumes/resume_{job.job_id}.pdf")

    # Collect human score
    score = get_human_score(resume_text)  # 1-5 scale
```

**Prompt Structure:**
```
You are an expert resume writer. Tailor this resume for the following job:

JOB DETAILS:
- Title: {job.title}
- Company: {job.company_name}
- Required Skills: {job.required_skills}
- Job Description: {job.description}

CANDIDATE PROFILE:
- Skills: {user.skills}
- Experience: {user.experience}

BASE RESUME:
{parsed_user_resume}

INSTRUCTIONS:
1. Highlight skills that match job requirements
2. Emphasize relevant experience
3. Use ATS-friendly formatting
4. Keep concise (1-2 pages)
5. Use action verbs and quantifiable achievements

Output the tailored resume in markdown format.
```

**Human Scoring:**
- Display generated resume + cover letter
- Ask human evaluator to score 1-5 vs. manual baseline
- Store scores for evaluation stage
- Target: Average score ≥ 4.0 (equivalent to manual quality)

---

### Stage 6: Evaluation Module
**Purpose:** Measure system performance against benchmarks

**Benchmark Dataset:**
- **10 Interview-Worthy Jobs:** Manually curated "ideal" jobs that would warrant interviews
- **10 Reject Jobs:** Jobs that should be filtered out (FAANG, startups, irrelevant)
- Store in `data/benchmark/benchmark_v1.json`

**Metrics:**

1. **Precision@10:** What % of top 10 ranked jobs are actually interview-worthy?
   ```
   Precision@10 = (# interview-worthy jobs in top 10) / 10
   Target: ≥ 0.70 (70%)
   ```

2. **Interview Yield Rate:** Of all jobs that passed filters, what % are interview-worthy?
   ```
   Interview Yield = (# interview-worthy jobs) / (# total filtered jobs)
   Target: ≥ 0.15 (15%)
   ```

3. **Bias Analysis:**
   - Geographic bias: Are certain states over/under-represented?
   - Company size bias: Distribution of company sizes in top 10
   - Skill bias: Are certain skill sets favored unfairly?

**Critical File:** `src/modules/evaluation_module.py`

**Implementation:**
```python
def calculate_precision_at_k(ranked_jobs: List[RankedJob],
                             benchmark: BenchmarkDataset,
                             k: int = 10) -> float:
    top_k = ranked_jobs[:k]
    worthy_ids = {j.job_id for j in benchmark.worthy_jobs}
    matches = sum(1 for j in top_k if j.job.job_id in worthy_ids)
    return matches / k

def analyze_bias(ranked_jobs: List[RankedJob]) -> BiasReport:
    # State distribution
    state_counts = Counter(parse_state(j.job.location) for j in ranked_jobs)

    # Company size distribution
    size_counts = Counter(j.job.company_size for j in ranked_jobs)

    # Skill distribution
    all_skills = [s for j in ranked_jobs for s in j.job.required_skills]
    skill_counts = Counter(all_skills)

    return BiasReport(
        state_distribution=dict(state_counts),
        size_distribution=dict(size_counts),
        top_skills=skill_counts.most_common(10)
    )
```

---

## Project File Structure

```
ai_job_agent/
├── README.md
├── requirements.txt
├── .env.example
├── .gitignore
│
├── config/
│   ├── api_config.yaml          # API keys, endpoints
│   ├── filter_config.yaml       # FAANG+ blacklist, rules
│   ├── rank_config.yaml         # Ranking weights
│   └── locations.yaml           # User-configurable states
│
├── data/
│   ├── raw/                     # Raw SerpAPI responses (JSON)
│   ├── processed/               # Filtered & ranked jobs (JSON)
│   ├── applications/            # Generated resumes & cover letters
│   │   ├── resumes/
│   │   └── cover_letters/
│   ├── benchmark/               # Ground truth dataset
│   │   └── benchmark_v1.json
│   └── evaluations/             # Metrics results
│
├── templates/
│   ├── prompts/
│   │   ├── resume_prompt.txt
│   │   └── cover_letter_prompt.txt
│   └── user_resume.pdf          # User's base resume
│
├── src/
│   ├── __init__.py
│   ├── models/
│   │   ├── job.py              # Job, RankedJob dataclasses
│   │   ├── application.py      # Application dataclass
│   │   └── config.py           # Config dataclasses
│   │
│   ├── modules/
│   │   ├── requirements_module.py   # Stage 1
│   │   ├── search_module.py         # Stage 2
│   │   ├── filter_module.py         # Stage 3
│   │   ├── rank_module.py           # Stage 4
│   │   ├── tailoring_module.py      # Stage 5
│   │   └── evaluation_module.py     # Stage 6
│   │
│   ├── utils/
│   │   ├── api_client.py       # SerpAPI & Claude wrappers
│   │   ├── pdf_parser.py       # PDF/DOCX resume parsing
│   │   ├── skill_extractor.py  # NLP skill extraction
│   │   ├── storage.py          # JSON read/write utilities
│   │   └── logger.py           # Logging setup
│   │
│   └── pipeline.py             # Main orchestration
│
├── scripts/
│   ├── run_pipeline.py         # Main execution
│   ├── create_benchmark.py     # Create ground truth dataset
│   ├── human_scoring.py        # Human scoring interface
│   └── evaluate.py             # Run evaluation
│
└── tests/
    ├── test_requirements.py
    ├── test_search.py
    ├── test_filter.py
    ├── test_rank.py
    ├── test_tailoring.py
    ├── test_evaluation.py
    └── test_integration.py
```

---

## Critical Files (Implementation Priority)

### 1. `src/models/job.py` - Core Data Models
Defines `Job`, `RankedJob`, `Application`, `SkillProfile`, `FilterConfig`, etc. All other modules depend on these.

### 2. `src/utils/api_client.py` - API Wrappers
```python
class SerpAPIClient:
    def search_jobs(query: str, location: str) -> List[dict]

class ClaudeAPIClient:
    def generate_resume(job: Job, profile: SkillProfile) -> str
    def generate_cover_letter(job: Job, profile: SkillProfile) -> str
```

### 3. `src/modules/search_module.py` - Job Search
First stage in pipeline. Must work to provide data for all downstream modules.

### 4. `src/modules/rank_module.py` - Ranking Logic
Core business logic. Contains algorithms for skill matching, location scoring, recency scoring.

### 5. `src/pipeline.py` - Main Orchestrator
```python
class JobApplicationPipeline:
    def run(self):
        # Stage 1: Load requirements
        requirements = RequirementsModule().load()

        # Stage 2: Search jobs
        jobs = SearchModule().search_jobs("AI Engineer", "Middle America")

        # Stage 3: Filter
        filtered = FilterModule().apply_filters(jobs, requirements.constraints)

        # Stage 4: Rank
        ranked = RankModule().rank_jobs(filtered, requirements.profile)

        # Stage 5: Tailor (top 3)
        applications = TailoringModule().generate_applications(ranked[:3])

        # Stage 6: Evaluate
        metrics = EvaluationModule().evaluate(ranked, applications)

        return Results(ranked_jobs=ranked, applications=applications, metrics=metrics)
```

---

## Dependencies & Tech Stack

**Core:**
- Python 3.10+
- `anthropic` - Claude API client
- `google-search-results` - SerpAPI client
- `pydantic` - Data validation
- `pyyaml` - Config files
- `python-dotenv` - Environment variables

**Data Processing:**
- `pandas` - Data manipulation
- `numpy` - Numerical operations

**NLP:**
- `spacy` - Skill extraction from job descriptions
- `python-Levenshtein` - Fuzzy string matching

**Document Parsing:**
- `PyPDF2` or `pdfplumber` - PDF resume parsing
- `python-docx` - Word document parsing

**PDF Generation:**
- `markdown2` - Markdown to HTML
- `weasyprint` - HTML to PDF

**Testing:**
- `pytest` - Unit tests
- `pytest-mock` - Mocking

**Utilities:**
- `requests` - HTTP requests
- `tenacity` - Retry logic
- `structlog` - Structured logging

---

## Configuration Files

### `config/filter_config.yaml`
```yaml
blacklist_companies:
  - Google
  - Apple
  - Meta
  - Facebook
  - Amazon
  - Microsoft
  - Netflix
  - Uber
  - Airbnb
  - Tesla
  - OpenAI
  - Twitter
  - X Corp

company_size:
  min: 50          # Exclude startups
  max: 5000        # Exclude mega-corps

toggles:
  iowa_only: false
  remote_only: false
```

### `config/locations.yaml`
```yaml
# User-configurable state preferences
preferred_states:
  - IA  # Iowa
  - NE  # Nebraska
  - MO  # Missouri
  - KS  # Kansas
  - MN  # Minnesota
  - WI  # Wisconsin
  - IL  # Illinois
  - IN  # Indiana
  - OH  # Ohio

remote_acceptable: true
hybrid_acceptable: true
```

### `config/rank_config.yaml`
```yaml
weights:
  skill_match: 0.5
  location: 0.3
  recency: 0.2

top_n: 10
top_n_tailor: 3
```

### `.env.example`
```bash
# API Keys (REQUIRED)
SERP_API_KEY=your_serpapi_key_here
ANTHROPIC_API_KEY=your_anthropic_key_here

# Optional: Company data
CLEARBIT_API_KEY=optional_clearbit_key

# Settings
MAX_JOBS_PER_SEARCH=100
LOG_LEVEL=INFO
```

---

## Testing Strategy

### Unit Tests
- **test_filter.py:** Test FAANG blacklist, startup detection, geography filters
- **test_rank.py:** Test skill matching, location scoring, composite ranking
- **test_tailoring.py:** Mock Claude API, test prompt construction
- **test_evaluation.py:** Test precision@10, interview yield calculations

### Integration Tests
- **test_integration.py:** End-to-end pipeline test with mocked APIs
- Test filter toggle modes (Iowa-only, remote-only)
- Test with sample benchmark dataset

### Manual Testing
1. Run pipeline with real SerpAPI data
2. Review top 10 ranked jobs for relevance
3. Generate applications for top 3
4. Human score generated resumes (1-5 scale)
5. Validate against manual baseline

---

## Verification & Testing Plan

### Stage 1 Verification: Requirements Module
✅ Successfully parse user's PDF/DOCX resume
✅ Extract skill profile (skills, years of experience)
✅ Load all config files (filter, rank, locations)
✅ Validate configuration schema

**Test:** `python -m pytest tests/test_requirements.py`

### Stage 2 Verification: Search Module
✅ Successfully query SerpAPI and retrieve ≥50 jobs
✅ Extract all required fields: title, company, location, skills, salary, URL
✅ Deduplicate results
✅ Save raw data to `data/raw/`

**Test:** `python scripts/run_pipeline.py --stage search --limit 50`

### Stage 3 Verification: Filter Module
✅ FAANG+ companies filtered out (0% in output)
✅ Startups (<50 employees) filtered out
✅ Geographic filter working (only configured states)
✅ Toggle modes working (e.g., Iowa-only reduces results)

**Test:** `python -m pytest tests/test_filter.py -v`

### Stage 4 Verification: Rank Module
✅ Skill match scores calculated (0-100 range)
✅ Location scores calculated (0-100 range)
✅ Recency scores calculated (0-100 range)
✅ Composite scores computed with correct weights
✅ Top 10 jobs returned in descending order

**Test:** `python scripts/run_pipeline.py --stage rank`

### Stage 5 Verification: Tailoring Module
✅ Claude API connection successful
✅ 3 resumes generated for top 3 jobs
✅ 3 cover letters generated for top 3 jobs
✅ Output saved as PDF in `data/applications/`
✅ Human scores collected (target avg ≥ 4.0)

**Test:**
```bash
python scripts/run_pipeline.py --stage tailor
python scripts/human_scoring.py  # Manual scoring interface
```

### Stage 6 Verification: Evaluation Module
✅ Benchmark dataset loaded (10 worthy, 10 reject)
✅ Precision@10 calculated (target ≥ 0.70)
✅ Interview yield calculated (target ≥ 0.15)
✅ Bias analysis report generated
✅ Metrics saved to `data/evaluations/`

**Test:** `python scripts/evaluate.py --benchmark data/benchmark/benchmark_v1.json`

### End-to-End Verification
```bash
# Run complete pipeline
python scripts/run_pipeline.py --full

# Expected output:
# - data/processed/ranked_jobs.json (top 10 jobs)
# - data/applications/resumes/ (3 tailored resumes)
# - data/applications/cover_letters/ (3 cover letters)
# - data/evaluations/eval_YYYYMMDD.json (metrics report)

# Verify metrics:
# - Precision@10 ≥ 0.70
# - Interview yield ≥ 0.15
# - Human scores avg ≥ 4.0
```

---

## Success Criteria

✅ **Functionality:**
- Pipeline runs end-to-end without errors
- All 6 stages complete successfully
- Outputs saved in correct formats

✅ **Quality:**
- Precision@10 ≥ 0.70 (70% of top 10 are interview-worthy)
- Interview yield ≥ 0.15 (15% of filtered jobs are worthy)
- Human scores avg ≥ 4.0 (tailored applications match manual quality)

✅ **Filtering:**
- 0% FAANG+ companies in output
- 0% startups (<50 employees) in output
- Geographic filters working (toggle tests pass)

✅ **Ranking:**
- Top 10 jobs have diverse companies (no duplicates)
- Skill match scores correlate with job relevance
- Location preferences respected

✅ **Tailoring:**
- Resumes highlight job-relevant skills
- Cover letters personalized to company/role
- ATS-friendly formatting maintained

✅ **Evaluation:**
- Bias analysis shows balanced geographic distribution
- No single state >40% of top 10
- Company size distribution: mostly mid-sized (50-5000)

---

## Implementation Sequence

### Week 1: Foundation
1. Set up project structure and virtual environment
2. Implement data models (`src/models/`)
3. Create configuration system (`config/`)
4. Set up logging and error handling
5. Write basic unit test framework

### Week 2: Data Acquisition
1. Implement SerpAPI client (`src/utils/api_client.py`)
2. Build search module (`src/modules/search_module.py`)
3. Create PDF/DOCX parser for resume (`src/utils/pdf_parser.py`)
4. Implement requirements module (`src/modules/requirements_module.py`)
5. Test data extraction end-to-end

### Week 3: Filtering & Ranking
1. Build filter module (`src/modules/filter_module.py`)
2. Implement startup detection heuristics
3. Create skill matching algorithm (`src/modules/rank_module.py`)
4. Implement location and recency scoring
5. Test with real SerpAPI data

### Week 4: Generation & Tailoring
1. Integrate Claude API (`src/utils/api_client.py`)
2. Build tailoring module (`src/modules/tailoring_module.py`)
3. Create resume and cover letter prompts
4. Implement PDF generation
5. Build human scoring interface

### Week 5: Evaluation & Polish
1. Create benchmark dataset (`data/benchmark/`)
2. Implement evaluation module (`src/modules/evaluation_module.py`)
3. Build metrics calculation (precision@10, interview yield)
4. Add bias analysis
5. Write comprehensive tests
6. Documentation and README

---

## Risk Mitigation

**Risk:** SerpAPI rate limits or cost
- **Mitigation:** Cache results, limit queries to 100/search, use demo data for testing

**Risk:** Claude API cost for generating applications
- **Mitigation:** Start with top 3 only, use caching for identical prompts, estimate $0.50-1.00 per application

**Risk:** Skill extraction inaccuracy from job descriptions
- **Mitigation:** Use spaCy NLP + manual skill list, allow config overrides, validate with test cases

**Risk:** Startup detection false positives/negatives
- **Mitigation:** Multi-signal heuristic (size field + keywords + API lookup), log filter decisions for audit

**Risk:** Ranking algorithm favors certain job types
- **Mitigation:** Configurable weights, bias analysis, A/B test different weight configurations

**Risk:** Generated resumes lack quality
- **Mitigation:** Prompt engineering, human scoring baseline (≥4.0), iterate on prompts based on feedback

---

## User's Sample Files Integration

**Provided by user:**
- Sample resume (PDF/DOCX format)
- Sample cover letter (optional)
- Sample job listings (optional)

**Integration steps:**
1. Parse user's resume to extract:
   - Contact information
   - Work experience
   - Education
   - Skills
   - Certifications
   - Projects
2. Use parsed data as `templates/user_resume.pdf` and create JSON representation
3. If cover letter provided, extract writing style and use as template
4. If sample jobs provided, use as benchmark dataset starting point

**Resume Parsing Approach:**
```python
# src/utils/pdf_parser.py
from pdfplumber import PDF
import docx

def parse_resume(file_path: str) -> dict:
    if file_path.endswith('.pdf'):
        return parse_pdf_resume(file_path)
    elif file_path.endswith('.docx'):
        return parse_docx_resume(file_path)
    else:
        raise ValueError("Unsupported format")

def parse_pdf_resume(pdf_path: str) -> dict:
    with pdfplumber.open(pdf_path) as pdf:
        text = "\n".join(page.extract_text() for page in pdf.pages)

    # Extract structured data using NLP + regex
    return {
        "name": extract_name(text),
        "email": extract_email(text),
        "phone": extract_phone(text),
        "skills": extract_skills(text),
        "experience": extract_experience(text),
        "education": extract_education(text),
        "raw_text": text
    }
```

---

## Next Steps After Plan Approval

1. **Setup:**
   - Create virtual environment
   - Install dependencies
   - Set up `.env` file with API keys
   - Create directory structure

2. **Parse User Resume:**
   - Run resume parser on user's provided file
   - Extract skill profile
   - Save structured representation

3. **Configuration:**
   - Customize `config/locations.yaml` with user's preferred states
   - Review `config/filter_config.yaml` FAANG+ list
   - Adjust `config/rank_config.yaml` weights if needed

4. **Development:**
   - Follow implementation sequence (weeks 1-5)
   - Test each stage before moving to next
   - Iterate based on results

5. **Validation:**
   - Run end-to-end pipeline
   - Collect human scores for generated applications
   - Verify metrics meet success criteria
   - Analyze bias report

---

## Questions for Clarification

Before implementation, please confirm:

1. **API Keys:** Do you have SerpAPI and Anthropic API keys ready? (If not, we can use demo data initially)

2. **Sample Resume:** What's the file path to your resume? (e.g., `/path/to/resume.pdf`)

3. **Location Preferences:** Which specific states should be prioritized? (We'll add to `config/locations.yaml`)

4. **Budget:** What's your budget tolerance for API calls? (SerpAPI: ~$50/month for 100 searches, Claude API: ~$20-50 for generating 50+ applications)

5. **Benchmark Dataset:** Do you have example "worthy" and "reject" jobs, or should we create them from search results?

---

This plan provides a complete blueprint for building the AI job application agent with clear stages, critical files, testing strategy, and success criteria. Ready to proceed with implementation once approved.

---

# README.md Content

Below is the complete content for the README.md file that will be created during implementation:

---

# AI Job Application Agent

> An autonomous AI agent that searches for AI Engineer jobs at mid-sized Middle American companies, intelligently filters and ranks them, and generates personalized resumes and cover letters.

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## 🎯 Overview

This project automates the job search and application process by:

1. **Searching** for AI Engineer jobs using SerpAPI
2. **Filtering** out unsuitable positions (FAANG+, startups, non-preferred locations)
3. **Ranking** jobs by skill match, location preference, and recency
4. **Generating** tailored resumes and cover letters using Claude AI
5. **Evaluating** results against benchmark datasets with precision metrics

**Key Features:**
- ✅ Smart filtering: Excludes FAANG+ companies and startups (<50 employees)
- ✅ Intelligent ranking: Multi-factor scoring (skills, location, recency)
- ✅ AI-powered tailoring: Personalized applications using Claude 3.5 Sonnet
- ✅ Quality metrics: Precision@10, interview yield, bias analysis
- ✅ Configurable: User-defined location preferences and ranking weights

---

## 🚀 Quick Start

### Prerequisites

- Python 3.10 or higher
- [SerpAPI](https://serpapi.com/) API key (for job search)
- [Anthropic](https://www.anthropic.com/) API key (for Claude AI)
- Your resume in PDF or DOCX format

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/ai-job-agent.git
cd ai-job-agent

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Download NLP model for skill extraction
python -m spacy download en_core_web_sm

# Set up environment variables
cp .env.example .env
# Edit .env and add your API keys
```

### Configure Your Preferences

1. **Add your resume:**
   ```bash
   cp /path/to/your/resume.pdf templates/user_resume.pdf
   ```

2. **Configure location preferences:**
   Edit `config/locations.yaml`:
   ```yaml
   preferred_states:
     - IA  # Iowa
     - NE  # Nebraska
     - MO  # Missouri
     # Add your preferred states
   ```

3. **Customize ranking weights (optional):**
   Edit `config/rank_config.yaml`:
   ```yaml
   weights:
     skill_match: 0.5  # 50% weight
     location: 0.3     # 30% weight
     recency: 0.2      # 20% weight
   ```

### Run the Pipeline

```bash
# Run complete pipeline (all 6 stages)
python scripts/run_pipeline.py --full

# Or run individual stages
python scripts/run_pipeline.py --stage search
python scripts/run_pipeline.py --stage filter
python scripts/run_pipeline.py --stage rank
python scripts/run_pipeline.py --stage tailor
```

### View Results

```bash
# Top 10 ranked jobs
cat data/processed/ranked_jobs.json

# Generated resumes
ls data/applications/resumes/

# Generated cover letters
ls data/applications/cover_letters/

# Evaluation metrics
cat data/evaluations/eval_*.json
```

---

## 📋 System Architecture

```
┌─────────────┐     ┌──────────────┐     ┌──────────────┐
│ Requirements│────▶│    Search    │────▶│    Filter    │
│   Module    │     │    Module    │     │    Module    │
│             │     │   (SerpAPI)  │     │  (FAANG+,    │
│ - Resume    │     │              │     │   Startups)  │
│ - Config    │     │ - Job Data   │     │              │
└─────────────┘     └──────────────┘     └──────────────┘
                                                │
                                                ▼
┌─────────────┐     ┌──────────────┐     ┌──────────────┐
│ Evaluation  │◀────│  Tailoring   │◀────│     Rank     │
│   Module    │     │    Module    │     │    Module    │
│             │     │  (Claude AI) │     │              │
│ - Metrics   │     │              │     │ - Top 10     │
│ - Bias      │     │ - Resumes    │     │ - Scoring    │
│   Analysis  │     │ - Covers     │     │   Algorithm  │
└─────────────┘     └──────────────┘     └──────────────┘
```

**Pipeline Flow:**
1. Load user requirements and resume
2. Search for jobs via SerpAPI
3. Filter out FAANG+, startups, non-preferred locations
4. Rank by skill match, location, and recency → Top 10
5. Generate tailored applications for top 3 jobs
6. Evaluate against benchmark (precision@10, interview yield)

---

## 📁 Project Structure

```
ai_job_agent/
├── README.md
├── requirements.txt
├── .env.example
│
├── config/                      # Configuration files
│   ├── api_config.yaml
│   ├── filter_config.yaml       # FAANG+ blacklist
│   ├── rank_config.yaml         # Ranking weights
│   └── locations.yaml           # Preferred states
│
├── data/                        # Data storage (JSON)
│   ├── raw/                     # Raw SerpAPI responses
│   ├── processed/               # Filtered & ranked jobs
│   ├── applications/            # Generated resumes & covers
│   ├── benchmark/               # Ground truth dataset
│   └── evaluations/             # Metrics results
│
├── templates/
│   ├── user_resume.pdf          # Your base resume
│   └── prompts/                 # LLM prompts
│       ├── resume_prompt.txt
│       └── cover_letter_prompt.txt
│
├── src/
│   ├── models/                  # Data models
│   ├── modules/                 # 6 pipeline stages
│   │   ├── requirements_module.py
│   │   ├── search_module.py
│   │   ├── filter_module.py
│   │   ├── rank_module.py
│   │   ├── tailoring_module.py
│   │   └── evaluation_module.py
│   ├── utils/                   # Utilities
│   │   ├── api_client.py        # SerpAPI & Claude
│   │   ├── pdf_parser.py        # Resume parsing
│   │   └── skill_extractor.py   # NLP extraction
│   └── pipeline.py              # Main orchestrator
│
├── scripts/
│   ├── run_pipeline.py          # Main execution
│   ├── create_benchmark.py      # Create benchmark dataset
│   ├── human_scoring.py         # Scoring interface
│   └── evaluate.py              # Run evaluation
│
└── tests/                       # Unit & integration tests
    ├── test_search.py
    ├── test_filter.py
    ├── test_rank.py
    └── test_integration.py
```

---

## ⚙️ Configuration

### Environment Variables (`.env`)

```bash
# Required API Keys
SERP_API_KEY=your_serpapi_key_here
ANTHROPIC_API_KEY=your_anthropic_key_here

# Optional: Company data APIs
CLEARBIT_API_KEY=optional_for_better_company_data

# Settings
MAX_JOBS_PER_SEARCH=100
LOG_LEVEL=INFO
```

### Filter Configuration (`config/filter_config.yaml`)

```yaml
# Companies to exclude
blacklist_companies:
  - Google
  - Apple
  - Meta
  - Amazon
  - Microsoft
  - Netflix
  - Uber
  - Airbnb
  - Tesla
  - OpenAI

# Company size filters
company_size:
  min: 50      # Exclude startups
  max: 5000    # Exclude mega-corps

# Toggle filters for testing
toggles:
  iowa_only: false
  remote_only: false
```

### Location Preferences (`config/locations.yaml`)

```yaml
# Customize your preferred states
preferred_states:
  - IA  # Iowa
  - NE  # Nebraska
  - MO  # Missouri
  - KS  # Kansas
  - MN  # Minnesota
  - WI  # Wisconsin
  - IL  # Illinois
  - IN  # Indiana
  - OH  # Ohio
  - MI  # Michigan

remote_acceptable: true
hybrid_acceptable: true
```

### Ranking Weights (`config/rank_config.yaml`)

```yaml
# Adjust weights to prioritize different factors
weights:
  skill_match: 0.5   # 50% - How well skills match
  location: 0.3      # 30% - Location preference
  recency: 0.2       # 20% - How recently posted

top_n: 10            # Number of jobs to rank
top_n_tailor: 3      # Number to generate applications for
```

---

## 💡 Usage Examples

### Example 1: Basic Job Search

```bash
# Search for AI Engineer jobs in Middle America
python scripts/run_pipeline.py --full
```

**Output:**
- `data/processed/ranked_jobs.json` - Top 10 ranked jobs
- `data/applications/resumes/*.pdf` - 3 tailored resumes
- `data/applications/cover_letters/*.pdf` - 3 cover letters

### Example 2: Iowa-Only Mode

```bash
# Enable Iowa-only filter toggle
# Edit config/filter_config.yaml:
#   toggles:
#     iowa_only: true

python scripts/run_pipeline.py --full
```

### Example 3: Search Specific Location

```bash
# Search specific city/state
python scripts/run_pipeline.py --query "AI Engineer" --location "Des Moines, IA"
```

### Example 4: Run Evaluation

```bash
# Create benchmark dataset first
python scripts/create_benchmark.py

# Run evaluation against benchmark
python scripts/evaluate.py --benchmark data/benchmark/benchmark_v1.json
```

**Metrics Output:**
```json
{
  "precision_at_10": 0.75,
  "interview_yield_rate": 0.18,
  "bias_metrics": {
    "state_distribution": {"IA": 3, "NE": 2, "MO": 2, ...},
    "company_size_distribution": {"51-200": 4, "201-500": 5, ...}
  }
}
```

### Example 5: Human Scoring Interface

```bash
# Review and score generated applications
python scripts/human_scoring.py

# Interface will show:
# - Generated resume
# - Generated cover letter
# - Prompt for 1-5 score
# - Comparison to manual baseline
```

---

## 🔍 How It Works

### Stage 1: Requirements Module
Parses your PDF/DOCX resume to extract:
- Skills (required and preferred)
- Years of experience per skill
- Work history
- Education

Loads configuration files for filtering and ranking.

### Stage 2: Search Module
Uses SerpAPI to search Google Jobs for "AI Engineer" positions. Extracts:
- Job title
- Company name
- Location
- Required/preferred skills (NLP extraction)
- Salary range
- Job URL
- Posting date

### Stage 3: Filter Module
Applies exclusion criteria:
- ❌ FAANG+ companies (Google, Apple, Meta, Amazon, etc.)
- ❌ Startups (<50 employees) via heuristics
- ❌ Non-preferred geographic locations
- ✅ Configurable toggles (Iowa-only, remote-only)

### Stage 4: Rank Module
Scores each job on three dimensions:

**Skill Match (50% weight):**
- Jaccard similarity between job requirements and your skills
- Bonus for experience level alignment

**Location (30% weight):**
- Preferred states: 80 points
- Middle America: 60 points minimum
- Remote: 100 points
- Hybrid: 90 points

**Recency (20% weight):**
- Exponential decay over 30 days
- Fresh postings scored higher

Returns **top 10** highest-scoring jobs.

### Stage 5: Tailoring Module
For the **top 3** ranked jobs:
1. Constructs detailed prompt with job requirements + your profile
2. Calls Claude 3.5 Sonnet API to generate:
   - Tailored resume (highlights relevant skills/experience)
   - Personalized cover letter (addresses company/role specifics)
3. Converts markdown output to PDF
4. Collects human scores (1-5 scale) for quality validation

### Stage 6: Evaluation Module
Measures system performance:

**Precision@10:**
```
P@10 = (# interview-worthy jobs in top 10) / 10
Target: ≥ 0.70 (70%)
```

**Interview Yield Rate:**
```
Yield = (# interview-worthy jobs) / (# total filtered jobs)
Target: ≥ 0.15 (15%)
```

**Bias Analysis:**
- Geographic distribution (avoid over-concentrating in one state)
- Company size distribution (ensure mid-sized focus)
- Skill distribution (detect unfair skill biases)

---

## 📊 Evaluation Metrics

### Success Criteria

| Metric | Target | Description |
|--------|--------|-------------|
| **Precision@10** | ≥ 0.70 | 70% of top 10 jobs are interview-worthy |
| **Interview Yield** | ≥ 0.15 | 15% of filtered jobs are worth applying to |
| **Human Score** | ≥ 4.0 | Generated applications match manual quality (1-5 scale) |
| **FAANG+ Rate** | = 0% | No FAANG+ companies in output |
| **Startup Rate** | = 0% | No startups (<50 employees) in output |

### Benchmark Dataset

Create a ground truth dataset with:
- **10 interview-worthy jobs:** Jobs you would definitely apply to
- **10 reject jobs:** Jobs that should be filtered out

```bash
python scripts/create_benchmark.py
```

This allows objective evaluation of ranking quality.

---

## 🧪 Testing

### Run All Tests

```bash
# Unit tests
pytest tests/ -v

# Integration test
pytest tests/test_integration.py -v

# Coverage report
pytest tests/ --cov=src --cov-report=html
```

### Test Individual Modules

```bash
# Test filtering logic
pytest tests/test_filter.py -v

# Test ranking algorithm
pytest tests/test_rank.py -v

# Test tailoring (mocked Claude API)
pytest tests/test_tailoring.py -v
```

### Manual Testing

```bash
# Test with limited jobs (faster, cheaper)
python scripts/run_pipeline.py --stage search --limit 10

# Test filter toggles
python scripts/run_pipeline.py --toggle iowa_only

# Test different ranking weights
# Edit config/rank_config.yaml, then:
python scripts/run_pipeline.py --stage rank
```

---

## 💰 Cost Estimation

### SerpAPI Costs
- **Free tier:** 100 searches/month
- **Paid:** $50/month for 5,000 searches
- **Estimated usage:** ~10 searches/month = **FREE**

### Anthropic Claude API Costs
- **Model:** Claude 3.5 Sonnet
- **Input:** ~$3 per million tokens
- **Output:** ~$15 per million tokens
- **Per application:** ~4,000 tokens input + 2,000 output = ~$0.05
- **Estimated usage:** 3 applications/search × 10 searches/month = **$1.50/month**

**Total estimated cost: $1.50-2.00/month**

---

## 🛠️ Troubleshooting

### Issue: SerpAPI returns no results

**Solution:**
- Check API key in `.env`
- Verify query syntax: `"AI Engineer" + location`
- Check rate limits (100/month on free tier)
- Try broader location: "United States" instead of specific city

### Issue: Resume parsing fails

**Solution:**
- Ensure resume is in PDF or DOCX format
- Check file path in `templates/user_resume.pdf`
- Try simpler formatting (avoid complex tables/graphics)
- Use `pdfplumber` debug mode:
  ```python
  import pdfplumber
  with pdfplumber.open("resume.pdf") as pdf:
      print(pdf.pages[0].extract_text())
  ```

### Issue: No jobs pass filters

**Solution:**
- Check if filters are too restrictive
- Review `config/filter_config.yaml`
- Try disabling some filters temporarily:
  ```yaml
  toggles:
    iowa_only: false  # Broaden geography
  ```
- Check filter stats:
  ```bash
  python scripts/run_pipeline.py --stage filter --verbose
  ```

### Issue: Claude API errors

**Solution:**
- Verify API key in `.env`
- Check rate limits (Anthropic dashboard)
- Retry with exponential backoff (already implemented)
- Reduce `max_tokens` if hitting limits

### Issue: Low precision@10 score

**Solution:**
- Adjust ranking weights in `config/rank_config.yaml`
- Review benchmark dataset quality
- Improve skill extraction (add custom skill list)
- Check if job descriptions are accurate

---

## 🤝 Contributing

Contributions welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Development Setup

```bash
# Install dev dependencies
pip install -r requirements-dev.txt

# Install pre-commit hooks
pre-commit install

# Run code formatting
black src/ tests/
ruff check src/ tests/

# Run type checking
mypy src/
```

---

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- [SerpAPI](https://serpapi.com/) for job search API
- [Anthropic](https://www.anthropic.com/) for Claude AI
- [spaCy](https://spacy.io/) for NLP capabilities

---

## 📧 Contact

Questions or issues? Open an issue on GitHub or contact [your-email@example.com]

---

## 🗺️ Roadmap

- [ ] Multi-source job search (LinkedIn, Indeed, Glassdoor)
- [ ] ML-based ranking (train on human feedback)
- [ ] Auto-apply integration
- [ ] Interview prep materials generation
- [ ] Application tracking dashboard
- [ ] Salary negotiation recommendations
- [ ] A/B testing for resume styles

---

**Happy job hunting! 🎯**
