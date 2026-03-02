"""Entry-point script: run a job search and print the number of results."""
from dotenv import load_dotenv

load_dotenv()

from ai_job_agent.src.modules.search_module import SearchModule  # noqa: E402


def main() -> None:
    module = SearchModule()
    jobs = module.search("AI Engineer", "United States")
    print(f"Jobs retrieved: {len(jobs)}")


if __name__ == "__main__":
    main()
