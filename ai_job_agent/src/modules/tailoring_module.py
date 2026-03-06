"""Tailoring module: generates personalized resumes and cover letters via Gemini.

For each of the top-N ranked jobs, the module:
    1. Reads the candidate resume text from the sample PDF.
    2. Calls Google Gemini to produce a tailored resume (markdown).
    3. Calls Google Gemini to produce a personalized cover letter (markdown).
    4. Saves both outputs to data/applications/.
    5. Writes a structured trace to data/processed/tailor_trace_<date>.json
       for the agent trace appendix required by the assignment report.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from tenacity import retry, stop_after_attempt, wait_exponential

from ai_job_agent.src.models.ranked_job import RankedJob
from ai_job_agent.src.utils.logger import setup_logger
from ai_job_agent.src.utils.pdf_parser import extract_text_from_pdf
from ai_job_agent.src.utils.storage import save_json

_DATA_DIR = Path(__file__).resolve().parents[3] / "data"
_TEMPLATES_DIR = Path(__file__).resolve().parents[2] / "templates"


class TailoringModule:
    """Calls Google Gemini to tailor resumes and cover letters for top-N ranked jobs.

    Args:
        resume_pdf_path: Path to the candidate's base resume PDF.
                         Defaults to templates/SampleResume1.pdf.
        top_n: Number of jobs to generate applications for (default: 3).
        model: Gemini model ID to use.
    """

    DEFAULT_RESUME = _TEMPLATES_DIR / "SampleResume1.pdf"
    MODEL = "gemini-2.0-flash"

    def __init__(
        self,
        resume_pdf_path: Optional[Path] = None,
        top_n: int = 3,
        model: str = MODEL,
    ) -> None:
        self._logger: logging.Logger = setup_logger("tailoring_module")
        self._top_n = top_n
        self._model = model
        self._resume_path = Path(resume_pdf_path or self.DEFAULT_RESUME)
        self._resume_text: str = extract_text_from_pdf(self._resume_path)
        self._client = self._build_client()

    # ── setup ─────────────────────────────────────────────────────────────────

    def _build_client(self):
        """Instantiate google-genai client using GEMINI_API_KEY from env."""
        try:
            from google import genai
        except ImportError as exc:
            raise RuntimeError(
                "google-genai package is required. "
                "Install with: pip install google-genai"
            ) from exc

        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise EnvironmentError(
                "GEMINI_API_KEY environment variable is not set. "
                "Get a free key at https://aistudio.google.com/app/apikey "
                "and add it to ai_job_agent/.env."
            )
        return genai.Client(api_key=api_key)

    # ── prompt builders ───────────────────────────────────────────────────────

    def _build_resume_prompt(self, job: RankedJob) -> str:
        j = job.job
        required = ", ".join(j.required_skills) or "not specified"
        preferred = ", ".join(j.preferred_skills) or "not specified"
        salary = (
            j.salary_range.get("raw", "not specified") if j.salary_range else "not specified"
        )

        return f"""You are an expert resume writer helping a candidate tailor their resume for a specific job.

JOB DETAILS:
- Title: {j.title}
- Company: {j.company_name}
- Location: {j.location}
- Salary: {salary}
- Match explanation: {job.explanation}

REQUIRED SKILLS: {required}
PREFERRED SKILLS: {preferred}

JOB DESCRIPTION:
{j.description[:3000]}

CANDIDATE'S CURRENT RESUME:
{self._resume_text}

TASK:
Rewrite the candidate's resume to best match this specific role. Follow these rules:
1. Keep all factual information accurate — do NOT invent experience or skills the candidate does not have.
2. Reorder bullet points to highlight the most relevant experience first.
3. Adjust the professional summary to mention the target role and company type.
4. Emphasize required skills that appear in the resume; use keywords from the job description naturally.
5. Output a clean, professional resume in markdown format.
6. Keep it to one page equivalent (roughly 600 words max).

Output only the tailored resume in markdown — no preamble or explanation."""

    def _build_cover_letter_prompt(self, job: RankedJob) -> str:
        j = job.job
        required = ", ".join(j.required_skills[:8]) or "not specified"

        return f"""You are an expert cover letter writer helping a candidate apply for a specific job.

JOB DETAILS:
- Title: {j.title}
- Company: {j.company_name}
- Location: {j.location}
- Match score: {job.total_score:.0f}/100 ({job.explanation})

TOP REQUIRED SKILLS: {required}

JOB DESCRIPTION (excerpt):
{j.description[:2000]}

CANDIDATE'S RESUME:
{self._resume_text}

TASK:
Write a compelling, personalized cover letter for this specific role. Follow these rules:
1. Address it to the hiring manager (use "Dear Hiring Manager," if name is unknown).
2. Opening paragraph: express specific enthusiasm for {j.company_name} and the {j.title} role.
3. Body (2 paragraphs): highlight 2-3 concrete experiences/skills that directly match the job requirements.
4. Closing: include a call to action requesting an interview and mentioning availability.
5. Keep it to 3-4 paragraphs, professional tone, ~300 words max.
6. Sign off as: "Alex Jordan\\nAI Engineer Candidate"

Output only the cover letter text in markdown — no preamble or explanation."""

    # ── Gemini API call ───────────────────────────────────────────────────────

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    def _call_gemini(self, prompt: str) -> str:
        """Send a prompt to Gemini and return the text response."""
        response = self._client.models.generate_content(
            model=self._model,
            contents=prompt,
        )
        return response.text

    # ── file helpers ──────────────────────────────────────────────────────────

    def _save_markdown(self, content: str, directory: Path, filename: str) -> Path:
        directory.mkdir(parents=True, exist_ok=True)
        filepath = directory / filename
        filepath.write_text(content, encoding="utf-8")
        return filepath

    # ── public API ────────────────────────────────────────────────────────────

    def tailor(self, ranked_jobs: List[RankedJob]) -> List[dict]:
        """Generate tailored resumes and cover letters for the top-N ranked jobs.

        Writes:
            data/applications/resumes/<rank>_<company>_<title>_<date>_resume.md
            data/applications/cover_letters/<rank>_<company>_<title>_<date>_cover_letter.md
            data/processed/tailor_trace_<date>.json  — per-job metadata + paths

        Args:
            ranked_jobs: Ranked jobs list (sorted best-first by RankModule).

        Returns:
            List of application dicts with file paths and metadata for each job.
        """
        top = ranked_jobs[: self._top_n]
        self._logger.info(
            "Tailoring stage started | jobs=%d | model=%s | resume=%s",
            len(top),
            self._model,
            self._resume_path.name,
        )

        today = datetime.now().strftime("%Y-%m-%d")
        resume_dir = _DATA_DIR / "applications" / "resumes"
        cover_dir = _DATA_DIR / "applications" / "cover_letters"

        trace: List[dict] = []
        applications: List[dict] = []

        for rank, rj in enumerate(top, start=1):
            j = rj.job
            safe_company = "".join(c if c.isalnum() else "_" for c in j.company_name)
            safe_title = "".join(c if c.isalnum() else "_" for c in j.title)[:30]
            base_name = f"{rank:02d}_{safe_company}_{safe_title}_{today}"

            self._logger.info(
                "Job %d/%d: %s @ %s | score=%.1f | %s",
                rank,
                len(top),
                j.title,
                j.company_name,
                rj.total_score,
                rj.explanation,
            )

            # --- Tailored Resume ---
            resume_path: Optional[Path] = None
            resume_error: Optional[str] = None
            try:
                resume_md = self._call_gemini(self._build_resume_prompt(rj))
                resume_path = self._save_markdown(resume_md, resume_dir, f"{base_name}_resume.md")
                self._logger.info("Saved resume: %s", resume_path)
            except Exception as exc:  # noqa: BLE001
                resume_error = str(exc)
                self._logger.error(
                    "Resume generation failed for job %s: %s", j.job_id, exc, exc_info=True
                )

            # --- Cover Letter ---
            cover_path: Optional[Path] = None
            cover_error: Optional[str] = None
            try:
                cover_md = self._call_gemini(self._build_cover_letter_prompt(rj))
                cover_path = self._save_markdown(
                    cover_md, cover_dir, f"{base_name}_cover_letter.md"
                )
                self._logger.info("Saved cover letter: %s", cover_path)
            except Exception as exc:  # noqa: BLE001
                cover_error = str(exc)
                self._logger.error(
                    "Cover letter generation failed for job %s: %s", j.job_id, exc, exc_info=True
                )

            entry = {
                "rank": rank,
                "job_id": j.job_id,
                "title": j.title,
                "company": j.company_name,
                "location": j.location,
                "total_score": rj.total_score,
                "explanation": rj.explanation,
                "resume_path": str(resume_path) if resume_path else None,
                "cover_letter_path": str(cover_path) if cover_path else None,
                "resume_error": resume_error,
                "cover_letter_error": cover_error,
            }
            trace.append(entry)
            applications.append(entry)

        # Persist trace for agent trace appendix
        trace_path = _DATA_DIR / "processed" / f"tailor_trace_{today}.json"
        save_json(trace, trace_path)
        self._logger.info(
            "Tailoring complete | %d applications | trace: %s",
            len(applications),
            trace_path,
        )

        return applications
