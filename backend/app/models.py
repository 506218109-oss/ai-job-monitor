from sqlalchemy import (
    Column, Integer, String, Text, Float, Boolean, Date, DateTime,
    ForeignKey, UniqueConstraint
)
from sqlalchemy.orm import relationship

from app.database import Base


class Job(Base):
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    platform = Column(String(32), nullable=False, default="boss")
    platform_job_id = Column(String(128), nullable=False)
    title = Column(String(256), nullable=False)
    company_name = Column(String(256), nullable=False)
    company_size = Column(String(64))
    company_industry = Column(String(128))
    location_city = Column(String(32))
    location_district = Column(String(64))
    salary_min = Column(Integer)
    salary_max = Column(Integer)
    salary_months = Column(Integer, default=12)
    job_type = Column(String(32), nullable=False, default="其他")
    job_subtype = Column(String(64))
    experience_required = Column(String(32))
    education_required = Column(String(32))
    description_text = Column(Text)
    benefits = Column(Text)
    posting_date = Column(Date)
    first_seen_at = Column(DateTime)
    last_seen_at = Column(DateTime)
    is_active = Column(Boolean, default=True)
    raw_json = Column(Text)

    job_skills = relationship("JobSkill", back_populates="job", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("platform", "platform_job_id", name="uq_platform_job"),
    )


class Skill(Base):
    __tablename__ = "skills"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(128), nullable=False, unique=True)
    name_cn = Column(String(128))
    category = Column(String(64), nullable=False)
    keywords = Column(Text, nullable=False)

    job_skills = relationship("JobSkill", back_populates="skill", cascade="all, delete-orphan")


class JobSkill(Base):
    __tablename__ = "job_skills"

    job_id = Column(Integer, ForeignKey("jobs.id", ondelete="CASCADE"), primary_key=True)
    skill_id = Column(Integer, ForeignKey("skills.id", ondelete="CASCADE"), primary_key=True)

    job = relationship("Job", back_populates="job_skills")
    skill = relationship("Skill", back_populates="job_skills")


class Company(Base):
    __tablename__ = "companies"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(256), nullable=False, unique=True)
    size = Column(String(64))
    industry = Column(String(128))
    location_city = Column(String(32))
    avg_salary_min = Column(Float)
    avg_salary_max = Column(Float)
    active_job_count = Column(Integer, default=0)
    total_job_count = Column(Integer, default=0)
    first_seen_at = Column(DateTime)
    last_scraped_at = Column(DateTime)


class JobSnapshot(Base):
    __tablename__ = "job_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    snapshot_date = Column(Date, nullable=False, unique=True)
    total_active = Column(Integer, default=0)
    total_all_time = Column(Integer, default=0)
    new_today = Column(Integer, default=0)
    removed_today = Column(Integer, default=0)
    jobs_by_type = Column(Text)
    jobs_by_city = Column(Text)
    avg_salary_by_type = Column(Text)
    top_companies = Column(Text)
    top_skills = Column(Text)
    created_at = Column(DateTime)


class ScrapeRun(Base):
    __tablename__ = "scrape_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    platform = Column(String(32), nullable=False)
    keyword = Column(String(128))
    started_at = Column(DateTime)
    finished_at = Column(DateTime)
    pages_scraped = Column(Integer, default=0)
    jobs_found = Column(Integer, default=0)
    jobs_new = Column(Integer, default=0)
    jobs_updated = Column(Integer, default=0)
    status = Column(String(16), default="running")
    error_message = Column(Text)
    meta_json = Column(Text)
