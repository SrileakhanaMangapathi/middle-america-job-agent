"""Pipeline orchestrator: wires Search → Filter → Rank → Tailor stages.

Usage (from Python):
    pipeline = Pipeline(query="AI Engineer", location="United States")
    results = pipeline.run_full()
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, List, Optional

from ai_job_agent.src.models.job import Job
from ai_job_agent.src.models.ranked_job import RankedJob
from ai_job_agent.src.modules.filter_module import FilterModule
from ai_job_agent.src.modules.rank_module import RankModule
from ai_job_agent.src.modules.search_module import SearchModule
from ai_job_agent.src.modules.tailoring_module import TailoringModule
from ai_job_agent.src.utils.logger import setup_logger
from ai_job_agent.src.utils.pdf_parser import extract_text_from_pdf
from ai_job_agent.src.utils.skill_extractor import extract_skills
from ai_job_agent.src.utils.storage import load_json, save_json

_DATA_DIR = Path(__file__).resolve().parents[2] / "data"
_TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "templates"


class Pipeline:
    """End-to-end job agent pipeline.

    Args:
        query: Job search query string (default: "AI Engineer").
        location: Search location (default: "United States").
        toggles: Filter toggles, e.g. {"iowa_only": True}.
        top_n_tailor: How many top jobs to tailor applications for (default: 3).
        resume_pdf_path: Path to candidate resume PDF.
    """

    DEFAULT_RESUME = _TEMPLATES_DIR / "SampleResume1.pdf"

    def __init__(
        self,
        query: str = "AI Engineer",
        location: str = "United States",
        toggles: Optional[Dict[str, bool]] = None,
        top_n_tailor: int = 3,
        resume_pdf_path: Optional[Path] = None,
    ) -> None:
        self._logger: logging.Logger = setup_logger("pipeline")
        self._query = query
        self._location = location
        self._toggles = toggles or {}
        self._top_n_tailor = top_n_tailor
        self._resume_path = Path(resume_pdf_path or self.DEFAULT_RESUME)

        # Extract user skills from resume once at startup
        self._user_skills = self._extract_resume_skills()

    # ── resume skill extraction ───────────────────────────────────────────────

    def _extract_resume_skills(self) -> List[str]:
        """Parse the resume PDF and return combined required + preferred skills."""
        try:
            resume_text = extract_text_from_pdf(self._resume_path)
            required, preferred = extract_skills(resume_text)
            user_skills = list(dict.fromkeys(required + preferred))  # dedup, preserve order
            self._logger.info(
                "Extracted %d user skills from resume: %s",
                len(user_skills),
                user_skills[:10],
            )
            return user_skills
        except Exception as exc:  # noqa: BLE001
            self._logger.warning(
                "Could not extract skills from resume (%s); ranking will use empty skill set.",
                exc,
            )
            return []

    # ── stage runners ─────────────────────────────────────────────────────────

    def run_search(self) -> List[Job]:
        """Stage 1: Search for jobs via SerpAPI."""
        self._logger.info("=== Stage 1: Search ===")
        module = SearchModule()
        jobs = module.search(self._query, self._location)
        self._logger.info("Search complete: %d jobs retrieved", len(jobs))
        return jobs

    def run_filter(self, jobs: List[Job]) -> List[Job]:
        """Stage 2: Filter out FAANG+, startups, and off-location jobs."""
        self._logger.info("=== Stage 2: Filter ===")
        module = FilterModule(toggles=self._toggles)
        passed = module.filter(jobs)
        self._logger.info("Filter complete: %d/%d jobs passed", len(passed), len(jobs))
        return passed

    def run_rank(self, jobs: List[Job]) -> List[RankedJob]:
        """Stage 3: Score and rank filtered jobs; return top-N."""
        self._logger.info("=== Stage 3: Rank ===")
        module = RankModule(user_skills=self._user_skills)
        ranked = module.rank(jobs)
        self._logger.info("Rank complete: top %d jobs selected", len(ranked))
        return ranked

    def run_tailor(self, ranked_jobs: List[RankedJob]) -> List[dict]:
        """Stage 4: Generate tailored resumes and cover letters for top-N jobs."""
        self._logger.info("=== Stage 4: Tailor ===")
        module = TailoringModule(
            resume_pdf_path=self._resume_path,
            top_n=self._top_n_tailor,
        )
        applications = module.tailor(ranked_jobs)
        self._logger.info("Tailor complete: %d applications generated", len(applications))
        return applications

    # ── full pipeline ─────────────────────────────────────────────────────────

    def run_full(self) -> dict:
        """Run all four stages end-to-end and return a summary dict."""
        self._logger.info(
            "Pipeline starting | query=%r | location=%r | toggles=%s",
            self._query,
            self._location,
            self._toggles,
        )

        jobs = self.run_search()
        filtered = self.run_filter(jobs)
        ranked = self.run_rank(filtered)
        applications = self.run_tailor(ranked)

        summary = {
            "query": self._query,
            "location": self._location,
            "toggles": self._toggles,
            "jobs_retrieved": len(jobs),
            "jobs_after_filter": len(filtered),
            "jobs_ranked": len(ranked),
            "applications_generated": len(applications),
            "top_jobs": [
                {
                    "rank": r.job.job_id,
                    "title": r.job.title,
                    "company": r.job.company_name,
                    "score": r.total_score,
                    "explanation": r.explanation,
                }
                for r in ranked[:3]
            ],
            "applications": applications,
        }

        self._logger.info("Pipeline complete. Summary: %s", {
            k: v for k, v in summary.items() if k not in ("top_jobs", "applications")
        })
        return summary

    # ── helpers for single-stage CLI runs ─────────────────────────────────────

    @staticmethod
    def _latest_file(pattern: str) -> Optional[Path]:
        """Return the most recently modified file matching a glob pattern under data/."""
        matches = sorted(_DATA_DIR.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
        return matches[0] if matches else None

    def load_structured_jobs(self) -> List[Job]:
        """Load the most recent structured_jobs JSON and reconstruct Job objects."""
        path = self._latest_file("processed/structured_jobs_*.json")
        if not path:
            raise FileNotFoundError(
                "No structured_jobs file found. Run --stage search first."
            )
        raw_list = load_json(path)
        return [self._job_from_dict(d) for d in raw_list]

    def load_filtered_jobs(self) -> List[Job]:
        """Load the most recent filtered_jobs JSON and reconstruct Job objects."""
        path = self._latest_file("processed/filtered_jobs_*.json")
        if not path:
            raise FileNotFoundError(
                "No filtered_jobs file found. Run --stage filter first."
            )
        raw_list = load_json(path)
        return [self._job_from_dict(d) for d in raw_list]

    def load_ranked_jobs(self) -> List[RankedJob]:
        """Load the most recent ranked_jobs JSON and reconstruct RankedJob objects."""
        path = self._latest_file("processed/ranked_jobs_*.json")
        if not path:
            raise FileNotFoundError(
                "No ranked_jobs file found. Run --stage rank first."
            )
        raw_list = load_json(path)
        return [self._ranked_job_from_dict(d) for d in raw_list]

    @staticmethod
    def _job_from_dict(d: dict) -> Job:
        from datetime import datetime
        d = dict(d)
        scraped_at_raw = d.pop("scraped_at", None)
        scraped_at = (
            datetime.fromisoformat(scraped_at_raw)
            if scraped_at_raw
            else datetime.now()
        )
        return Job(**d, scraped_at=scraped_at)

    @staticmethod
    def _ranked_job_from_dict(d: dict) -> RankedJob:
        from datetime import datetime
        d = dict(d)
        score_fields = {
            "total_score": d.pop("total_score", 0.0),
            "skill_score": d.pop("skill_score", 0.0),
            "location_score": d.pop("location_score", 0.0),
            "recency_score": d.pop("recency_score", 0.0),
            "explanation": d.pop("explanation", ""),
        }
        scraped_at_raw = d.pop("scraped_at", None)
        scraped_at = (
            datetime.fromisoformat(scraped_at_raw)
            if scraped_at_raw
            else datetime.now()
        )
        job = Job(**d, scraped_at=scraped_at)
        return RankedJob(job=job, **score_fields)
