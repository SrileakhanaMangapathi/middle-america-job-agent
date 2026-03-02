import os
from typing import List

from serpapi import GoogleSearch
from tenacity import retry, stop_after_attempt, wait_exponential


class SerpAPIClient:
    def __init__(self) -> None:
        api_key = os.environ.get("SERP_API_KEY")
        if not api_key:
            raise EnvironmentError(
                "SERP_API_KEY environment variable is not set. "
                "Please add your SerpAPI key to the .env file."
            )
        self._api_key = api_key

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    def search_jobs(
        self, query: str, location: str, num_results: int = 50
    ) -> List[dict]:
        params = {
            "engine": "google_jobs",
            "q": query,
            "location": location,
            "num": num_results,
            "api_key": self._api_key,
        }
        results = GoogleSearch(params).get_dict()
        return results.get("jobs_results", [])
