"""CLI entry point for the Middle America Job Agent pipeline.

Examples
--------
# Full pipeline (all 4 stages)
python -m ai_job_agent.scripts.run_pipeline --full

# Individual stages
python -m ai_job_agent.scripts.run_pipeline --stage search
python -m ai_job_agent.scripts.run_pipeline --stage filter
python -m ai_job_agent.scripts.run_pipeline --stage rank
python -m ai_job_agent.scripts.run_pipeline --stage tailor

# Custom query / location
python -m ai_job_agent.scripts.run_pipeline --full --query "ML Engineer" --location "Chicago, IL"

# Filter toggles
python -m ai_job_agent.scripts.run_pipeline --full --toggle iowa_only
python -m ai_job_agent.scripts.run_pipeline --full --toggle remote_only
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Load .env before any project imports so API keys are in env
from dotenv import load_dotenv

_ENV_FILE = Path(__file__).resolve().parents[1] / ".env"
if not _ENV_FILE.exists():
    print(
        f"ERROR: .env file not found at {_ENV_FILE}\n"
        "Copy ai_job_agent/.env.example to ai_job_agent/.env and fill in your API keys.",
        file=sys.stderr,
    )
    sys.exit(1)
load_dotenv(dotenv_path=_ENV_FILE)

from ai_job_agent.src.pipeline import Pipeline  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Middle America Job Agent — autonomous job search and application pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    # Run mode (mutually exclusive)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--full",
        action="store_true",
        help="Run the complete pipeline: search → filter → rank → tailor",
    )
    mode.add_argument(
        "--stage",
        choices=["search", "filter", "rank", "tailor"],
        metavar="STAGE",
        help="Run a single stage (search | filter | rank | tailor)",
    )

    # Search options
    parser.add_argument(
        "--query",
        default="AI Engineer",
        help='Job search query (default: "AI Engineer")',
    )
    parser.add_argument(
        "--location",
        default="United States",
        help='Search location (default: "United States")',
    )

    # Filter toggles
    parser.add_argument(
        "--toggle",
        action="append",
        dest="toggles",
        metavar="TOGGLE",
        default=[],
        help="Enable a filter toggle: iowa_only | remote_only (repeatable)",
    )

    # Resume
    parser.add_argument(
        "--resume",
        type=Path,
        default=None,
        help="Path to candidate resume PDF (default: templates/SampleResume1.pdf)",
    )

    return parser


def print_summary(summary: dict) -> None:
    print("\n" + "=" * 60)
    print("PIPELINE SUMMARY")
    print("=" * 60)
    print(f"  Query      : {summary['query']}")
    print(f"  Location   : {summary['location']}")
    print(f"  Toggles    : {summary['toggles'] or 'none'}")
    print(f"  Retrieved  : {summary['jobs_retrieved']} jobs")
    print(f"  After filter: {summary['jobs_after_filter']} jobs")
    print(f"  Ranked top : {summary['jobs_ranked']} jobs")
    print(f"  Applications: {summary['applications_generated']} generated")
    print()
    print("TOP JOBS:")
    for i, job in enumerate(summary.get("top_jobs", []), 1):
        print(f"  {i}. {job['title']} @ {job['company']}  [score={job['score']}]")
        print(f"     {job['explanation']}")
    print()
    print("APPLICATIONS:")
    for app in summary.get("applications", []):
        print(f"  #{app['rank']} {app['title']} @ {app['company']}")
        if app.get("resume_path"):
            print(f"     Resume      : {app['resume_path']}")
        if app.get("cover_letter_path"):
            print(f"     Cover letter: {app['cover_letter_path']}")
        if app.get("resume_error"):
            print(f"     Resume ERROR: {app['resume_error']}")
        if app.get("cover_letter_error"):
            print(f"     Cover ERROR : {app['cover_letter_error']}")
    print("=" * 60)


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    # Build toggles dict from --toggle flags
    toggles = {t: True for t in args.toggles}

    pipeline = Pipeline(
        query=args.query,
        location=args.location,
        toggles=toggles,
        resume_pdf_path=args.resume,
    )

    if args.full:
        summary = pipeline.run_full()
        print_summary(summary)

    elif args.stage == "search":
        jobs = pipeline.run_search()
        print(f"\nSearch complete: {len(jobs)} jobs retrieved and saved.")

    elif args.stage == "filter":
        print("Loading structured jobs from disk...")
        jobs = pipeline.load_structured_jobs()
        filtered = pipeline.run_filter(jobs)
        print(f"\nFilter complete: {len(filtered)}/{len(jobs)} jobs passed.")

    elif args.stage == "rank":
        print("Loading filtered jobs from disk...")
        jobs = pipeline.load_filtered_jobs()
        ranked = pipeline.run_rank(jobs)
        print(f"\nRank complete: top {len(ranked)} jobs selected.")
        for i, r in enumerate(ranked, 1):
            print(f"  {i:2}. [{r.total_score:5.1f}] {r.job.title} @ {r.job.company_name}")
            print(f"       {r.explanation}")

    elif args.stage == "tailor":
        print("Loading ranked jobs from disk...")
        ranked = pipeline.load_ranked_jobs()
        applications = pipeline.run_tailor(ranked)
        print(f"\nTailor complete: {len(applications)} applications generated.")
        for app in applications:
            print(f"  #{app['rank']} {app['title']} @ {app['company']}")
            if app.get("resume_path"):
                print(f"     Resume      : {app['resume_path']}")
            if app.get("cover_letter_path"):
                print(f"     Cover letter: {app['cover_letter_path']}")


if __name__ == "__main__":
    main()
