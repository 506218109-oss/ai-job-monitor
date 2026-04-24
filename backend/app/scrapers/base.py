from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date
from typing import Optional


@dataclass
class JobData:
    platform: str
    platform_job_id: str
    title: str
    company_name: str
    company_size: Optional[str] = None
    company_industry: Optional[str] = None
    location_city: Optional[str] = None
    location_district: Optional[str] = None
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    salary_months: int = 12
    job_type: Optional[str] = None
    job_subtype: Optional[str] = None
    experience_required: Optional[str] = None
    education_required: Optional[str] = None
    description_text: Optional[str] = None
    description_html: Optional[str] = None
    benefits: Optional[str] = None
    posting_date: Optional[date] = None
    raw_json: Optional[str] = None


class AbstractScraper(ABC):

    @abstractmethod
    async def search(self, keyword: str, city: str = "", max_pages: int = 3) -> list[JobData]:
        """Search for jobs and return list of job data (without full description)."""
        ...

    @abstractmethod
    async def get_detail(self, job: JobData) -> JobData:
        """Fetch and fill full job description."""
        ...

    @abstractmethod
    async def close(self):
        """Clean up resources."""
        ...
