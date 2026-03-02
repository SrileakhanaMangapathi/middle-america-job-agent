"""Tests for the skill_extractor utility."""
import pytest

from ai_job_agent.src.utils.skill_extractor import extract_skills


# ---------------------------------------------------------------------------
# Empty / blank descriptions
# ---------------------------------------------------------------------------


def test_empty_string_returns_empty_lists():
    required, preferred = extract_skills("")
    assert required == []
    assert preferred == []


def test_blank_string_returns_empty_lists():
    required, preferred = extract_skills("   \n\t  ")
    assert required == []
    assert preferred == []


# ---------------------------------------------------------------------------
# Skill identification
# ---------------------------------------------------------------------------


def test_known_skills_are_identified():
    desc = "We need Python, TensorFlow, and AWS experience."
    required, preferred = extract_skills(desc)
    all_skills = set(required) | set(preferred)
    assert "python" in all_skills
    assert "tensorflow" in all_skills
    assert "aws" in all_skills


def test_case_insensitive_matching():
    desc = "Proficiency in PYTHON and PyTorch is required."
    required, preferred = extract_skills(desc)
    all_skills = set(required) | set(preferred)
    assert "python" in all_skills
    assert "pytorch" in all_skills


# ---------------------------------------------------------------------------
# Required vs. Preferred classification
# ---------------------------------------------------------------------------


def test_skills_in_first_40_percent_are_required():
    # Place a skill clearly within the first 40% of the text.
    early_skill = "Python"
    padding_chars = "x" * 200
    # Build: early_skill at position ~0, then long padding
    desc = f"{early_skill} is essential. {padding_chars}"
    required, preferred = extract_skills(desc)
    assert "python" in required
    assert "python" not in preferred


def test_skills_only_in_last_60_percent_are_preferred():
    # 200 chars of filler (no skills), then 'Docker' mentioned at ~50% mark
    filler = "We are a great company. " * 10  # ~240 chars
    late_skill = "Docker"
    desc = filler + f" {late_skill} knowledge is a bonus."
    # Ensure Docker appears only after the 40% cutoff
    cutoff = int(len(desc) * 0.4)
    docker_pos = desc.lower().find("docker")
    assert docker_pos >= cutoff, "Test setup issue: Docker is not in the late section"
    required, preferred = extract_skills(desc)
    assert "docker" in preferred
    assert "docker" not in required


def test_skill_only_in_early_section_is_not_preferred():
    early_skill = "Kubernetes"
    filler = "z" * 300
    desc = f"{early_skill} {filler}"
    required, preferred = extract_skills(desc)
    assert "kubernetes" in required
    assert "kubernetes" not in preferred


# ---------------------------------------------------------------------------
# No false positives for unrelated text
# ---------------------------------------------------------------------------


def test_unrelated_text_returns_empty():
    desc = "We are hiring a bus driver with a clean license."
    required, preferred = extract_skills(desc)
    # 'r' is in the catalogue but should not match 'driver' or 'licence'
    all_skills = set(required) | set(preferred)
    # None of the catalogue skills should appear
    expected_empty = {"python", "tensorflow", "pytorch", "aws", "docker"}
    assert expected_empty.isdisjoint(all_skills)


# ---------------------------------------------------------------------------
# Search module integration: empty description → empty skill lists
# ---------------------------------------------------------------------------


def test_search_module_empty_description_produces_empty_skills(
    tmp_path, monkeypatch
):
    """Existing search module behaviour: empty desc → empty skill lists."""
    from unittest.mock import MagicMock

    monkeypatch.setenv("SERP_API_KEY", "test_key")

    raw_jobs = [
        {
            "title": "AI Engineer",
            "company_name": "Acme",
            "location": "Chicago, IL",
            "description": "",
            "share_link": "https://example.com/job",
            "detected_extensions": {},
        }
    ]

    mock_client = MagicMock()
    mock_client.search_jobs.return_value = raw_jobs

    import ai_job_agent.src.modules.search_module as sm_module
    from ai_job_agent.src.modules.search_module import SearchModule

    monkeypatch.setattr(sm_module, "_DATA_DIR", tmp_path)
    (tmp_path / "raw").mkdir(parents=True)
    (tmp_path / "processed").mkdir(parents=True)

    module = SearchModule(client=mock_client)
    jobs = module.search("AI Engineer", "United States")

    assert len(jobs) == 1
    assert jobs[0].required_skills == []
    assert jobs[0].preferred_skills == []


def test_search_module_populates_skills_from_description(tmp_path, monkeypatch):
    """Search module should populate skills when description contains them."""
    from unittest.mock import MagicMock

    monkeypatch.setenv("SERP_API_KEY", "test_key")

    raw_jobs = [
        {
            "title": "ML Engineer",
            "company_name": "TechCo",
            "location": "Remote",
            "description": "Python and TensorFlow required. Docker experience a plus.",
            "share_link": "https://example.com/job/2",
            "detected_extensions": {},
        }
    ]

    mock_client = MagicMock()
    mock_client.search_jobs.return_value = raw_jobs

    import ai_job_agent.src.modules.search_module as sm_module
    from ai_job_agent.src.modules.search_module import SearchModule

    monkeypatch.setattr(sm_module, "_DATA_DIR", tmp_path)
    (tmp_path / "raw").mkdir(parents=True)
    (tmp_path / "processed").mkdir(parents=True)

    module = SearchModule(client=mock_client)
    jobs = module.search("ML Engineer", "Remote")

    assert len(jobs) == 1
    all_skills = set(jobs[0].required_skills) | set(jobs[0].preferred_skills)
    assert "python" in all_skills
    assert "tensorflow" in all_skills
