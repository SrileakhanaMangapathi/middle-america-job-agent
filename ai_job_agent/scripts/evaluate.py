"""Run evaluation metrics against the ground truth benchmark.

Usage:
    python -m ai_job_agent.scripts.evaluate
    python -m ai_job_agent.scripts.evaluate --benchmark data/benchmark/benchmark_v1.json
    python -m ai_job_agent.scripts.evaluate --k 5

Requires:
    - data/benchmark/benchmark_v1.json  (from create_benchmark.py)
    - data/processed/ranked_jobs_*.json (from run_pipeline --stage rank)
    - data/processed/filtered_jobs_*.json (from run_pipeline --stage filter)
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

_ENV_FILE = Path(__file__).resolve().parents[1] / ".env"
if _ENV_FILE.exists():
    load_dotenv(dotenv_path=_ENV_FILE)

_DATA_DIR = Path(__file__).resolve().parents[2] / "data"

from ai_job_agent.src.modules.evaluation_module import EvaluationModule  # noqa: E402
from ai_job_agent.src.pipeline import Pipeline  # noqa: E402


def _latest_file(pattern: str) -> Path | None:
    matches = sorted(_DATA_DIR.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    return matches[0] if matches else None


def _load_json(path: Path) -> list | dict:
    with open(path) as f:
        return json.load(f)


def _load_human_scores() -> list[dict]:
    """Load the most recent human scoring file if available."""
    path = _latest_file("evaluations/human_scores_*.json")
    if path:
        data = _load_json(path)
        return data if isinstance(data, list) else data.get("scores", [])
    return []


def _print_results(results: dict) -> None:
    print("\n" + "=" * 60)
    print("EVALUATION RESULTS")
    print("=" * 60)

    targets = results.get("targets", {})

    # Precision@K
    p = targets.get("precision_at_10", {})
    status = "✅ PASS" if p.get("passed") else "❌ FAIL"
    print(f"\n  Precision@{results['k']}: {p.get('value', 0):.2%}  "
          f"(target ≥ {p.get('target', 0):.0%})  {status}")

    # Interview Yield
    y = targets.get("interview_yield", {})
    status = "✅ PASS" if y.get("passed") else "❌ FAIL"
    print(f"  Interview Yield : {y.get('value', 0):.2%}  "
          f"(target ≥ {y.get('target', 0):.0%})  {status}")

    # Human score (optional)
    if "human_score" in targets:
        h = targets["human_score"]
        status = "✅ PASS" if h.get("passed") else "❌ FAIL"
        print(f"  Human Score     : {h.get('value', 0):.1f}/5.0  "
              f"(target ≥ {h.get('target', 0):.1f})  {status}")

    # Bias metrics
    bias = results.get("bias_metrics", {})
    print("\n  BIAS ANALYSIS:")
    state_dist = bias.get("state_distribution", {})
    print(f"    Geographic distribution: {dict(list(state_dist.items())[:6])}")
    hhi = bias.get("geographic_concentration_hhi", 0)
    hhi_verdict = "diverse" if hhi < 0.25 else "concentrated"
    print(f"    Geographic HHI: {hhi:.3f} ({hhi_verdict})")
    top_skills = bias.get("top_10_skills", {})
    if top_skills:
        print(f"    Top skills in shortlist: {', '.join(list(top_skills.keys())[:5])}")
    score_stats = bias.get("score_stats", {})
    print(f"    Score range: {score_stats.get('min', 0)} – {score_stats.get('max', 0)} "
          f"(avg {score_stats.get('average', 0)})")

    # Top-K breakdown
    breakdown = results.get("top_k_breakdown", [])
    if breakdown:
        print(f"\n  TOP-{results['k']} BREAKDOWN:")
        for entry in breakdown:
            worthy_str = ""
            if entry["in_benchmark"]:
                worthy_str = " [WORTHY]" if entry["interview_worthy"] else " [REJECT]"
            print(f"    {entry['rank']:2}. [{entry['total_score']:5.1f}] "
                  f"{entry['title']} @ {entry['company']}{worthy_str}")

    eval_path = _latest_file("evaluations/eval_*.json")
    print(f"\n  Full results saved to: {eval_path}")
    print("=" * 60)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run evaluation against benchmark")
    parser.add_argument(
        "--benchmark",
        type=Path,
        default=None,
        help="Path to benchmark JSON (default: data/benchmark/benchmark_v1.json)",
    )
    parser.add_argument("--k", type=int, default=10, help="Precision@K value (default: 10)")
    args = parser.parse_args()

    # Load benchmark
    benchmark_path = args.benchmark or _DATA_DIR / "benchmark" / "benchmark_v1.json"
    if not benchmark_path.exists():
        print(f"ERROR: Benchmark not found at {benchmark_path}")
        print("Run first: python -m ai_job_agent.scripts.create_benchmark")
        sys.exit(1)
    benchmark_data = _load_json(benchmark_path)
    benchmark_jobs = benchmark_data.get("jobs", benchmark_data) if isinstance(benchmark_data, dict) else benchmark_data
    print(f"Loaded benchmark: {len(benchmark_jobs)} labeled jobs")

    # Load ranked jobs
    ranked_path = _latest_file("processed/ranked_jobs_*.json")
    if not ranked_path:
        print("ERROR: No ranked jobs found. Run: python -m ai_job_agent.scripts.run_pipeline --stage rank")
        sys.exit(1)
    pipeline = Pipeline()
    ranked_jobs = pipeline.load_ranked_jobs()
    print(f"Loaded {len(ranked_jobs)} ranked jobs")

    # Load filtered jobs
    filtered_path = _latest_file("processed/filtered_jobs_*.json")
    if not filtered_path:
        print("ERROR: No filtered jobs found. Run --stage filter first.")
        sys.exit(1)
    filtered_jobs = pipeline.load_filtered_jobs()
    print(f"Loaded {len(filtered_jobs)} filtered jobs")

    # Load human scores if available
    human_scores = _load_human_scores()
    if human_scores:
        print(f"Loaded {len(human_scores)} human scores")

    # Run evaluation
    module = EvaluationModule(k=args.k)
    results = module.evaluate(ranked_jobs, filtered_jobs, benchmark_jobs, human_scores or None)

    _print_results(results)


if __name__ == "__main__":
    main()
