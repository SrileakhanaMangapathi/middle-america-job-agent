"""Unit tests for the Search/Data Module."""
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from ai_job_agent.src.models.job import Job
from ai_job_agent.src.modules.search_module import SearchModule


# ---------------------------------------------------------------------------
# generate_job_id
# ---------------------------------------------------------------------------


def test_generate_job_id_is_deterministic():
    id1 = SearchModule.generate_job_id("AI Engineer", "Acme Corp", "Des Moines, IA")
    id2 = SearchModule.generate_job_id("AI Engineer", "Acme Corp", "Des Moines, IA")
    assert id1 == id2


def test_generate_job_id_differs_for_different_inputs():
    id1 = SearchModule.generate_job_id("AI Engineer", "Acme Corp", "Des Moines, IA")
    id2 = SearchModule.generate_job_id("ML Engineer", "Acme Corp", "Des Moines, IA")
    assert id1 != id2


def test_generate_job_id_case_insensitive():
    id1 = SearchModule.generate_job_id("AI Engineer", "Acme Corp", "Des Moines, IA")
    id2 = SearchModule.generate_job_id("ai engineer", "acme corp", "des moines, ia")
    assert id1 == id2


# ---------------------------------------------------------------------------
# Job dataclass
# ---------------------------------------------------------------------------


def test_job_creation_defaults():
    job = Job(
        job_id="abc123",
        title="AI Engineer",
        company_name="Acme Corp",
        location="Des Moines, IA",
        description="Build cool things",
        job_url="https://example.com/job/1",
    )
    assert job.source == "SerpAPI"
    assert isinstance(job.scraped_at, datetime)
    assert job.required_skills == []
    assert job.preferred_skills == []


def test_job_to_dict_serialisation():
    job = Job(
        job_id="abc123",
        title="AI Engineer",
        company_name="Acme Corp",
        location="Des Moines, IA",
        description="Build cool things",
        job_url="https://example.com/job/1",
        salary_range={"min": 100000, "max": 150000},
    )
    d = job.to_dict()
    assert d["job_id"] == "abc123"
    assert d["title"] == "AI Engineer"
    assert isinstance(d["scraped_at"], str)  # ISO-formatted string
    assert d["salary_range"] == {"min": 100000, "max": 150000}


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------


def _make_raw_job(title: str, company: str, location: str) -> dict:
    return {
        "title": title,
        "company_name": company,
        "location": location,
        "description": "Some description",
        "share_link": "https://example.com/job",
        "detected_extensions": {},
    }


def test_deduplication_removes_duplicates(tmp_path, monkeypatch):
    """Duplicate raw jobs (same title/company/location) should produce one Job."""
    monkeypatch.setenv("SERP_API_KEY", "test_key")

    raw_jobs = [
        _make_raw_job("AI Engineer", "Acme", "Chicago, IL"),
        _make_raw_job("AI Engineer", "Acme", "Chicago, IL"),  # duplicate
        _make_raw_job("ML Engineer", "Globex", "Omaha, NE"),
    ]

    mock_client = MagicMock()
    mock_client.search_jobs.return_value = raw_jobs

    # Patch data directory so files are written to tmp_path
    import ai_job_agent.src.modules.search_module as sm_module

    monkeypatch.setattr(sm_module, "_DATA_DIR", tmp_path)
    (tmp_path / "raw").mkdir(parents=True)
    (tmp_path / "processed").mkdir(parents=True)

    module = SearchModule(client=mock_client)
    jobs = module.search("AI Engineer", "United States")

    assert len(jobs) == 2
    titles = {j.title for j in jobs}
    assert titles == {"AI Engineer", "ML Engineer"}
