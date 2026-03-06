"""Interactive human scoring interface for generated resumes and cover letters.

Scores each tailored application on a 1-5 scale, then saves results to
data/evaluations/human_scores_<date>.json.

Usage:
    python -m ai_job_agent.scripts.human_scoring

Scale:
    1 = Poor — generic, wrong job, major errors
    2 = Below average — minimal tailoring, several issues
    3 = Average — some tailoring, acceptable quality
    4 = Good — clearly tailored, relevant, professional
    5 = Excellent — highly personalized, compelling, publication-ready
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

SCORE_LABELS = {
    1: "Poor",
    2: "Below average",
    3: "Average",
    4: "Good",
    5: "Excellent",
}

SCORE_GUIDE = """
Scoring guide (1–5):
  5 = Excellent   — highly personalized, compelling, publication-ready
  4 = Good        — clearly tailored, relevant, professional
  3 = Average     — some tailoring, acceptable quality
  2 = Below avg   — minimal tailoring, several issues
  1 = Poor        — generic, wrong job, or major errors
"""


def _load_tailor_trace() -> list[dict]:
    """Load the most recent tailor trace file."""
    matches = sorted(
        _DATA_DIR.glob("processed/tailor_trace_*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not matches:
        print("ERROR: No tailor trace found. Run the tailor stage first:")
        print("  python -m ai_job_agent.scripts.run_pipeline --stage tailor")
        sys.exit(1)
    with open(matches[0]) as f:
        return json.load(f)


def _display_document(label: str, path: str | None, error: str | None) -> bool:
    """Print document content to terminal. Returns True if content shown."""
    print(f"\n{'─' * 60}")
    print(f"  {label}")
    print(f"{'─' * 60}")
    if error:
        print(f"  [Generation failed: {error[:120]}]")
        return False
    if not path or not Path(path).exists():
        print("  [File not found]")
        return False
    content = Path(path).read_text(encoding="utf-8")
    # Print with line wrapping for readability
    print()
    for line in content.splitlines():
        print(f"  {line}")
    print()
    return True


def _prompt_score(label: str) -> int | None:
    """Prompt for a 1-5 score. Returns None to skip."""
    while True:
        raw = input(f"  Score for {label} [1-5 / s=skip / q=quit]: ").strip().lower()
        if raw in ("q", "quit"):
            return -1  # sentinel for quit
        if raw in ("s", "skip"):
            return None
        try:
            score = int(raw)
            if 1 <= score <= 5:
                print(f"  → {score}: {SCORE_LABELS[score]}")
                return score
            print("  Please enter a number between 1 and 5.")
        except ValueError:
            print("  Please enter a number between 1 and 5.")


def main() -> None:
    trace = _load_tailor_trace()
    print(f"Found {len(trace)} tailored applications to review.")
    print(SCORE_GUIDE)

    scores: list[dict] = []
    quit_early = False

    for app in trace:
        rank = app.get("rank", "?")
        title = app.get("title", "Unknown")
        company = app.get("company", "Unknown")

        print(f"\n{'=' * 60}")
        print(f"Application #{rank}: {title} @ {company}")
        print(f"Score: {app.get('total_score', 'N/A')} | {app.get('explanation', '')}")
        print(f"{'=' * 60}")

        resume_shown = _display_document(
            "TAILORED RESUME", app.get("resume_path"), app.get("resume_error")
        )
        cover_shown = _display_document(
            "COVER LETTER", app.get("cover_letter_path"), app.get("cover_letter_error")
        )

        if not resume_shown and not cover_shown:
            print("  No documents available to score — skipping.")
            continue

        # Score resume
        resume_score = None
        if resume_shown:
            resume_score = _prompt_score("resume")
            if resume_score == -1:
                quit_early = True
                break

        # Score cover letter
        cover_score = None
        if cover_shown:
            cover_score = _prompt_score("cover letter")
            if cover_score == -1:
                quit_early = True
                break

        notes = input("  Notes (optional, press Enter to skip): ").strip()

        if resume_score is not None or cover_score is not None:
            entry: dict = {
                "rank": rank,
                "job_id": app.get("job_id"),
                "title": title,
                "company": company,
                "resume_score": resume_score,
                "cover_letter_score": cover_score,
                "notes": notes,
            }
            # Combined score = average of non-None scores
            parts = [s for s in [resume_score, cover_score] if s is not None]
            entry["score"] = round(sum(parts) / len(parts), 2) if parts else None
            scores.append(entry)

        if quit_early:
            break

    if not scores:
        print("\nNo scores recorded.")
        return

    # Summary
    all_scores = [s["score"] for s in scores if s.get("score") is not None]
    avg = round(sum(all_scores) / len(all_scores), 2) if all_scores else None

    today = datetime.now().strftime("%Y-%m-%d")
    output = {
        "scored_at": datetime.now().isoformat(),
        "total_reviewed": len(scores),
        "average_score": avg,
        "target_score": 4.0,
        "target_passed": avg >= 4.0 if avg else False,
        "scores": scores,
    }

    out_path = _DATA_DIR / "evaluations" / f"human_scores_{today}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2)

    print(f"\n{'=' * 60}")
    print("HUMAN SCORING COMPLETE")
    print(f"{'=' * 60}")
    print(f"  Applications scored : {len(scores)}")
    print(f"  Average score       : {avg}/5.0  (target ≥ 4.0)")
    status = "✅ PASS" if avg and avg >= 4.0 else "❌ FAIL"
    print(f"  Target              : {status}")
    print(f"  Results saved to    : {out_path}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
