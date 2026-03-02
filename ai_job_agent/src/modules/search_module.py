import hashlib
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from ai_job_agent.src.models.job import Job
from ai_job_agent.src.utils.api_client import SerpAPIClient
from ai_job_agent.src.utils.logger import setup_logger
from ai_job_agent.src.utils.skill_extractor import extract_skills
from ai_job_agent.src.utils.storage import save_json

_DATA_DIR = Path(__file__).resolve().parents[3] / "data"


class SearchModule:
    def __init__(self, client: Optional[SerpAPIClient] = None) -> None:
        self._client = client or SerpAPIClient()
        self._logger: logging.Logger = setup_logger("search_module")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def generate_job_id(title: str, company: str, location: str) -> str:
        raw = f"{title.lower()}|{company.lower()}|{location.lower()}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    @staticmethod
    def extract_salary(job_data: dict) -> Optional[dict]:
        detected_ext = job_data.get("detected_extensions", {})
        salary_raw = detected_ext.get("salary", "")
        if not salary_raw:
            return None

        numbers = re.findall(r"[\d,]+", salary_raw)
        amounts = [int(n.replace(",", "")) for n in numbers if n]
        if len(amounts) >= 2:
            return {"min": amounts[0], "max": amounts[1], "raw": salary_raw}
        if len(amounts) == 1:
            return {"min": amounts[0], "max": amounts[0], "raw": salary_raw}
        return {"raw": salary_raw}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def search(self, query: str, location: str) -> List[Job]:
        self._logger.info("Starting job search: query=%r location=%r", query, location)

        raw_jobs = self._client.search_jobs(query, location)
        self._logger.info("Raw jobs retrieved: %d", len(raw_jobs))

        today = datetime.now().strftime("%Y-%m-%d")
        raw_path = _DATA_DIR / "raw" / f"raw_jobs_{today}.json"
        save_json(raw_jobs, raw_path)
        self._logger.info("Saved raw jobs to %s", raw_path)

        seen_ids: set = set()
        jobs: List[Job] = []

        for raw in raw_jobs:
            try:
                title = raw.get("title", "")
                company = raw.get("company_name", "")
                loc = raw.get("location", "")
                job_id = self.generate_job_id(title, company, loc)

                if job_id in seen_ids:
                    continue
                seen_ids.add(job_id)

                desc = raw.get("description", "")
                required_skills, preferred_skills = extract_skills(desc)

                job = Job(
                    job_id=job_id,
                    title=title,
                    company_name=company,
                    location=loc,
                    description=desc,
                    job_url=raw.get("share_link", raw.get("job_url", "")),
                    posted_date=raw.get("detected_extensions", {}).get(
                        "posted_at"
                    ),
                    salary_range=self.extract_salary(raw),
                    company_size=None,
                    required_skills=required_skills,
                    preferred_skills=preferred_skills,
                )
                jobs.append(job)
            except Exception as exc:  # noqa: BLE001
                self._logger.error(
                    "Failed to parse job entry: %s — %s", raw, exc, exc_info=True
                )

        self._logger.info("Deduplicated jobs count: %d", len(jobs))

        structured_path = _DATA_DIR / "processed" / f"structured_jobs_{today}.json"
        save_json([j.to_dict() for j in jobs], structured_path)
        self._logger.info("Saved structured jobs to %s", structured_path)

        self._logger.info("Search completed successfully.")
        return jobs
