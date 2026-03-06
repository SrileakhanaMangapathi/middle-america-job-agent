"""Evaluation module: computes hiring simulation metrics against a benchmark dataset.

Metrics computed:
    Precision@K  = (# interview-worthy jobs in top-K ranked) / K
                   Target: >= 0.70
    Interview Yield = (# interview-worthy in filtered set) / (# total filtered)
                      Target: >= 0.15
    Bias Analysis:
        - Geographic distribution of top-K ranked jobs
        - Skill distribution across top-K ranked jobs
        - FAANG / startup contamination rate (should be 0%)

Output saved to data/evaluations/eval_<date>.json
"""
from __future__ import annotations

import logging
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from ai_job_agent.src.models.job import Job
from ai_job_agent.src.models.ranked_job import RankedJob
from ai_job_agent.src.utils.logger import setup_logger
from ai_job_agent.src.utils.storage import save_json

_DATA_DIR = Path(__file__).resolve().parents[3] / "data"


class EvaluationModule:
    """Computes Precision@K, interview yield, and bias metrics.

    Args:
        k: Number of top ranked jobs to evaluate (default: 10).
    """

    def __init__(self, k: int = 10) -> None:
        self._logger: logging.Logger = setup_logger("evaluation_module")
        self._k = k

    # ── helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _benchmark_ids(benchmark: List[dict]) -> tuple[set, set]:
        """Return (interview_worthy_ids, reject_ids) from benchmark."""
        worthy = {e["job_id"] for e in benchmark if e.get("interview_worthy")}
        rejects = {e["job_id"] for e in benchmark if not e.get("interview_worthy")}
        return worthy, rejects

    @staticmethod
    def _extract_state(location: str) -> str:
        """Extract a 2-letter US state abbreviation from a location string."""
        if not location:
            return "Unknown"
        loc = location.strip()
        if "remote" in loc.lower():
            return "Remote"
        # Match ", XX" pattern at end or before "("
        match = re.search(r",\s*([A-Z]{2})\b", loc)
        if match:
            return match.group(1)
        # Match state abbreviation directly
        match = re.search(r"\b([A-Z]{2})\b", loc)
        if match:
            return match.group(1)
        return "Unknown"

    # ── metric computers ──────────────────────────────────────────────────────

    def precision_at_k(
        self,
        ranked_jobs: List[RankedJob],
        worthy_ids: set,
    ) -> float:
        """Fraction of top-K ranked jobs that are interview-worthy.

        If fewer than K jobs are ranked, uses the actual count as denominator.
        """
        top = ranked_jobs[: self._k]
        if not top:
            return 0.0
        hits = sum(1 for r in top if r.job.job_id in worthy_ids)
        return round(hits / len(top), 4)

    def interview_yield(
        self,
        filtered_jobs: List[Job],
        worthy_ids: set,
    ) -> float:
        """Fraction of filtered jobs that are interview-worthy."""
        if not filtered_jobs:
            return 0.0
        hits = sum(1 for j in filtered_jobs if j.job_id in worthy_ids)
        return round(hits / len(filtered_jobs), 4)

    def bias_metrics(self, ranked_jobs: List[RankedJob]) -> dict:
        """Compute geographic, skill, and score distribution metrics for top-K."""
        top = ranked_jobs[: self._k]

        state_counts: Counter = Counter()
        skill_counts: Counter = Counter()
        scores = []

        for rj in top:
            state = self._extract_state(rj.job.location)
            state_counts[state] += 1
            for skill in rj.job.required_skills + rj.job.preferred_skills:
                skill_counts[skill.lower()] += 1
            scores.append(rj.total_score)

        avg_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        score_range = (round(min(scores), 2), round(max(scores), 2)) if scores else (0, 0)

        # Geographic concentration: Herfindahl index (1 = monopoly, 0 = uniform)
        total = sum(state_counts.values()) or 1
        hhi = round(sum((c / total) ** 2 for c in state_counts.values()), 4)

        return {
            "state_distribution": dict(state_counts.most_common()),
            "top_10_skills": dict(skill_counts.most_common(10)),
            "score_stats": {
                "average": avg_score,
                "min": score_range[0],
                "max": score_range[1],
            },
            "geographic_concentration_hhi": hhi,
            "hhi_note": (
                "HHI < 0.25 = diverse geography; "
                "HHI > 0.25 = concentrated in few states"
            ),
        }

    # ── public API ────────────────────────────────────────────────────────────

    def evaluate(
        self,
        ranked_jobs: List[RankedJob],
        filtered_jobs: List[Job],
        benchmark: List[dict],
        human_scores: Optional[List[dict]] = None,
    ) -> dict:
        """Run full evaluation and save results to data/evaluations/.

        Args:
            ranked_jobs: Output of RankModule (sorted best-first).
            filtered_jobs: Output of FilterModule (all jobs that passed filters).
            benchmark: List of benchmark dicts with job_id + interview_worthy fields.
            human_scores: Optional list of human scoring dicts (from human_scoring.py).

        Returns:
            Metrics dict with precision, yield, bias, and pass/fail targets.
        """
        worthy_ids, reject_ids = self._benchmark_ids(benchmark)

        self._logger.info(
            "Evaluation started | ranked=%d | filtered=%d | benchmark=%d "
            "(worthy=%d, rejects=%d)",
            len(ranked_jobs),
            len(filtered_jobs),
            len(benchmark),
            len(worthy_ids),
            len(reject_ids),
        )

        p_at_k = self.precision_at_k(ranked_jobs, worthy_ids)
        yield_rate = self.interview_yield(filtered_jobs, worthy_ids)
        bias = self.bias_metrics(ranked_jobs)

        # Per-job breakdown for top-K
        top_k_breakdown = []
        for i, rj in enumerate(ranked_jobs[: self._k], start=1):
            in_benchmark = rj.job.job_id in worthy_ids or rj.job.job_id in reject_ids
            top_k_breakdown.append({
                "rank": i,
                "job_id": rj.job.job_id,
                "title": rj.job.title,
                "company": rj.job.company_name,
                "location": rj.job.location,
                "total_score": rj.total_score,
                "explanation": rj.explanation,
                "in_benchmark": in_benchmark,
                "interview_worthy": rj.job.job_id in worthy_ids if in_benchmark else None,
            })

        targets = {
            "precision_at_10": {
                "value": p_at_k,
                "target": 0.70,
                "passed": p_at_k >= 0.70,
            },
            "interview_yield": {
                "value": yield_rate,
                "target": 0.15,
                "passed": yield_rate >= 0.15,
            },
        }

        # Average human score if provided
        avg_human_score = None
        if human_scores:
            scores = [s["score"] for s in human_scores if "score" in s]
            avg_human_score = round(sum(scores) / len(scores), 2) if scores else None
            targets["human_score"] = {
                "value": avg_human_score,
                "target": 4.0,
                "passed": avg_human_score >= 4.0 if avg_human_score else False,
            }

        results = {
            "evaluated_at": datetime.now().isoformat(),
            "k": self._k,
            "benchmark_size": len(benchmark),
            "filtered_jobs_count": len(filtered_jobs),
            "ranked_jobs_count": len(ranked_jobs),
            "targets": targets,
            "bias_metrics": bias,
            "top_k_breakdown": top_k_breakdown,
            "human_scores": human_scores or [],
        }

        today = datetime.now().strftime("%Y-%m-%d")
        out_path = _DATA_DIR / "evaluations" / f"eval_{today}.json"
        save_json(results, out_path)
        self._logger.info("Evaluation results saved to %s", out_path)

        passed = sum(1 for t in targets.values() if t["passed"])
        self._logger.info(
            "Evaluation complete | P@%d=%.2f | yield=%.2f | targets passed=%d/%d",
            self._k,
            p_at_k,
            yield_rate,
            passed,
            len(targets),
        )

        return results
