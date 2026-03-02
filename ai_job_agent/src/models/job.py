from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional


@dataclass
class Job:
    job_id: str
    title: str
    company_name: str
    location: str
    description: str
    job_url: str
    posted_date: Optional[str] = None
    salary_range: Optional[dict] = None
    company_size: Optional[str] = None
    required_skills: List[str] = field(default_factory=list)
    preferred_skills: List[str] = field(default_factory=list)
    source: str = "SerpAPI"
    scraped_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        data = dataclasses.asdict(self)
        data["scraped_at"] = self.scraped_at.isoformat()
        return data
