"""Entry-point script: run a job search and print the number of results."""
from pathlib import Path

from dotenv import load_dotenv

# Load .env from the ai_job_agent/ directory so the script works regardless
# of where it is invoked from.
_ENV_FILE = Path(__file__).resolve().parents[1] / ".env"
if not _ENV_FILE.exists():
    raise FileNotFoundError(
        f".env file not found at {_ENV_FILE}\n"
        "Copy ai_job_agent/.env.example to ai_job_agent/.env "
        "and fill in your SERP_API_KEY."
    )
load_dotenv(dotenv_path=_ENV_FILE)

from ai_job_agent.src.modules.search_module import SearchModule  # noqa: E402


def main() -> None:
    module = SearchModule()
    jobs = module.search("AI Engineer", "United States")
    print(f"Jobs retrieved: {len(jobs)}")


if __name__ == "__main__":
    main()
