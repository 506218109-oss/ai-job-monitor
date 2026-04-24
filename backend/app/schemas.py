from pydantic import BaseModel
from datetime import date, datetime
from typing import Optional


class JobBase(BaseModel):
    platform: str = "boss"
    platform_job_id: str
    title: str
    company_name: str
    company_size: Optional[str] = None
    company_industry: Optional[str] = None
    location_city: Optional[str] = None
    location_district: Optional[str] = None
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    salary_months: Optional[int] = 12
    job_type: str = "其他"
    job_subtype: Optional[str] = None
    experience_required: Optional[str] = None
    education_required: Optional[str] = None
    description_text: Optional[str] = None
    benefits: Optional[str] = None
    posting_date: Optional[date] = None
    is_active: bool = True


class JobOut(JobBase):
    id: int
    first_seen_at: Optional[datetime] = None
    last_seen_at: Optional[datetime] = None
    skills: list["SkillOut"] = []

    class Config:
        from_attributes = True


class JobListOut(BaseModel):
    items: list[JobOut]
    total: int
    page: int
    pages: int


class SkillBase(BaseModel):
    name: str
    name_cn: Optional[str] = None
    category: str
    keywords: str


class SkillOut(SkillBase):
    id: int
    job_count: Optional[int] = None

    class Config:
        from_attributes = True


class CompanyOut(BaseModel):
    id: int
    name: str
    size: Optional[str] = None
    industry: Optional[str] = None
    location_city: Optional[str] = None
    avg_salary_min: Optional[float] = None
    avg_salary_max: Optional[float] = None
    active_job_count: int = 0
    total_job_count: int = 0

    class Config:
        from_attributes = True


class ScrapeRunOut(BaseModel):
    id: int
    platform: str
    keyword: Optional[str] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    pages_scraped: int
    jobs_found: int
    jobs_new: int
    jobs_updated: int
    status: str
    error_message: Optional[str] = None

    class Config:
        from_attributes = True


class ScrapeTrigger(BaseModel):
    platform: str = "boss"
    keywords: Optional[list[str]] = None


class OverviewStats(BaseModel):
    total_active: int
    total_all_time: int
    new_last_7_days: int
    companies_tracked: int
    avg_salary_min: Optional[float] = None
    avg_salary_max: Optional[float] = None
    top_types: list[dict]
    top_companies: list[dict]


class SnapshotOut(BaseModel):
    snapshot_date: date
    total_active: int
    total_all_time: int
    new_today: int
    removed_today: int
    jobs_by_type: Optional[dict] = None
    jobs_by_city: Optional[dict] = None
    avg_salary_by_type: Optional[dict] = None
    top_companies: Optional[list] = None
    top_skills: Optional[list] = None

    class Config:
        from_attributes = True
