"""Interactive script to build the 20-job ground truth benchmark dataset.

Usage:
    python -m ai_job_agent.scripts.create_benchmark

Loads jobs from the most recent structured_jobs JSON, presents each one,
and asks whether it is interview-worthy (y/n). Saves to:
    data/benchmark/benchmark_v1.json

The benchmark needs at least 10 interview-worthy and 10 reject entries
to be valid for evaluation. The script warns if this target isn't met.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

_ENV_FILE = Path(__file__).resolve().parents[1] / ".env"
if _ENV_FILE.exists():
    load_dotenv(dotenv_path=_ENV_FILE)

_DATA_DIR = Path(__file__).resolve().parents[2] / "data"

TARGET_WORTHY = 10
TARGET_REJECTS = 10


def _latest_file(pattern: str) -> Path | None:
    matches = sorted(_DATA_DIR.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    return matches[0] if matches else None


def _load_jobs() -> list[dict]:
    """Load the most recent structured or filtered jobs file."""
    # Prefer filtered (already cleaned) over raw structured
    path = _latest_file("processed/filtered_jobs_*.json")
    if not path:
        path = _latest_file("processed/structured_jobs_*.json")
    if not path:
        print("ERROR: No job data found. Run the search stage first:")
        print("  python -m ai_job_agent.scripts.run_pipeline --stage search")
        sys.exit(1)
    print(f"Loading jobs from: {path.name}\n")
    with open(path) as f:
        return json.load(f)


def _display_job(idx: int, total: int, job: dict) -> None:
    """Print a formatted job card to the terminal."""
    print()
    print("=" * 60)
    print(f"Job {idx}/{total}")
    print("=" * 60)
    print(f"  Title   : {job.get('title', 'N/A')}")
    print(f"  Company : {job.get('company_name', 'N/A')}")
    print(f"  Location: {job.get('location', 'N/A')}")
    salary = job.get("salary_range")
    if salary:
        print(f"  Salary  : {salary.get('raw', 'N/A')}")
    req = job.get("required_skills", [])
    if req:
        print(f"  Skills  : {', '.join(req[:8])}")
    print(f"  URL     : {job.get('job_url', 'N/A')}")
    desc = job.get("description", "")
    if desc:
        print(f"\n  Description (excerpt):\n  {desc[:400].strip()}...")
    print()


def _prompt_verdict() -> tuple[bool, str]:
    """Prompt user for interview-worthy decision and optional notes."""
    while True:
        answer = input("  Interview-worthy? [y/n/s(skip)/q(quit)]: ").strip().lower()
        if answer in ("y", "yes"):
            notes = input("  Notes (optional, press Enter to skip): ").strip()
            return True, notes
        if answer in ("n", "no"):
            notes = input("  Notes (optional, press Enter to skip): ").strip()
            return False, notes
        if answer in ("s", "skip"):
            return None, ""  # type: ignore[return-value]
        if answer in ("q", "quit"):
            return None, "quit"  # type: ignore[return-value]
        print("  Please enter y, n, s, or q.")


def main() -> None:
    jobs = _load_jobs()
    print(f"Loaded {len(jobs)} jobs for benchmarking.")
    print(f"Goal: label at least {TARGET_WORTHY} interview-worthy and {TARGET_REJECTS} rejects.")
    print("Commands: y=yes/interview-worthy  n=no/reject  s=skip  q=quit+save\n")

    entries: list[dict] = []
    worthy_count = 0
    reject_count = 0

    for idx, job in enumerate(jobs, start=1):
        _display_job(idx, len(jobs), job)
        worthy, notes = _prompt_verdict()

        if notes == "quit":
            print("\nQuitting early — saving progress so far.")
            break
        if worthy is None:
            print("  Skipped.")
            continue

        entries.append({
            "job_id": job["job_id"],
            "title": job.get("title", ""),
            "company": job.get("company_name", ""),
            "location": job.get("location", ""),
            "interview_worthy": worthy,
            "notes": notes,
        })
        if worthy:
            worthy_count += 1
            print(f"  ✓ Marked interview-worthy ({worthy_count}/{TARGET_WORTHY} goal)")
        else:
            reject_count += 1
            print(f"  ✗ Marked reject ({reject_count}/{TARGET_REJECTS} goal)")

    # Save
    benchmark = {
        "version": "v1",
        "created_at": datetime.now().isoformat(),
        "total": len(entries),
        "interview_worthy_count": worthy_count,
        "reject_count": reject_count,
        "jobs": entries,
    }

    out_path = _DATA_DIR / "benchmark" / "benchmark_v1.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(benchmark, f, indent=2)

    print(f"\nBenchmark saved to: {out_path}")
    print(f"  Interview-worthy : {worthy_count}")
    print(f"  Rejects          : {reject_count}")
    print(f"  Total labeled    : {len(entries)}")

    if worthy_count < TARGET_WORTHY or reject_count < TARGET_REJECTS:
        print(
            f"\nWARNING: Target is {TARGET_WORTHY} worthy + {TARGET_REJECTS} rejects. "
            "Run more searches to get more jobs, then re-run this script."
        )
    else:
        print("\nBenchmark is ready for evaluation.")
        print("Run: python -m ai_job_agent.scripts.evaluate")


if __name__ == "__main__":
    main()
