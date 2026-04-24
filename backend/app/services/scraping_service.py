import json
import asyncio
from datetime import datetime, date, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import Job, Company, ScrapeRun
from app.scrapers.boss import BossScraper
from app.scrapers.liepin import LiepinScraper
from app.scrapers.tencent import TencentScraper
from app.scrapers.bytedance import ByteDanceScraper
from app.scrapers.base import JobData
from app.config import settings


async def run_scrape(platform: str = "liepin", keywords: list[str] = None):
    """
    Full scrape pipeline: fetch jobs, store in DB, update company stats.
    Supports: boss, liepin
    """
    if keywords is None:
        keywords = settings.SEARCH_KEYWORDS
    if not keywords:
        keywords = ["AI产品经理", "大模型产品经理", "AI运营"]

    db = SessionLocal()
    scraper = None
    run = None

    try:
        run = ScrapeRun(
            platform=platform,
            keyword=", ".join(keywords),
            started_at=datetime.utcnow(),
            status="running",
        )
        db.add(run)
        db.commit()

        total_found = 0
        total_new = 0
        total_updated = 0

        if platform == "boss":
            scraper = BossScraper(headless=True)
            max_p = 3
            delay_between_cities = 8
            fetch_details = False
            nationwide_api = False
        elif platform == "liepin":
            scraper = LiepinScraper(headless=True)
            max_p = 2
            delay_between_cities = 8
            fetch_details = False
            nationwide_api = False
        elif platform == "tencent":
            scraper = TencentScraper()
            max_p = 5
            delay_between_cities = 0
            fetch_details = True
            nationwide_api = True  # API returns all cities regardless of parameter
        elif platform == "bytedance":
            scraper = ByteDanceScraper()
            max_p = 5
            delay_between_cities = 0
            fetch_details = False
            nationwide_api = True  # API returns all cities regardless of parameter
        else:
            scraper = TencentScraper()
            max_p = 5
            delay_between_cities = 0
            fetch_details = True
            nationwide_api = True

        seen_job_ids = set()
        # For nationwide APIs, search once per keyword without city
        cities_to_search = [""] if nationwide_api else settings.TARGET_CITIES

        for keyword in keywords:
            for city in cities_to_search:
                try:
                    jobs = await scraper.search(keyword, city, max_pages=max_p)
                    display_city = city or "全国"
                    print(f"  [Scrape] '{keyword}' @ {display_city}: found {len(jobs)} raw jobs")

                    new_in_batch = 0
                    for job_data in jobs:
                        job_key = (job_data.platform, job_data.platform_job_id)
                        if job_key in seen_job_ids:
                            continue
                        seen_job_ids.add(job_key)

                        found, new = upsert_job(db, job_data)
                        total_found += found
                        if new:
                            total_new += 1
                            new_in_batch += 1

                            if fetch_details and scraper:
                                try:
                                    await scraper.get_detail(job_data)
                                    _update_job_detail(db, job_data)
                                except Exception as e:
                                    print(f"  [Scrape] Detail error: {e}")
                        else:
                            total_updated += 1

                    if new_in_batch:
                        print(f"  [Scrape] '{keyword}' @ {display_city}: {new_in_batch} new")

                    if delay_between_cities > 0:
                        await asyncio.sleep(delay_between_cities)

                except Exception as e:
                    print(f"  [Scrape] Error for '{keyword}' @ {city}: {e}")
                    continue

        run.jobs_found = total_found
        run.jobs_new = total_new
        run.jobs_updated = total_updated
        run.status = "success" if total_found > 0 else "partial"
        run.finished_at = datetime.utcnow()

    except Exception as e:
        print(f"[Scrape] Fatal error: {e}")
        if run:
            run.status = "failed"
            run.error_message = str(e)[:1000]
            run.finished_at = datetime.utcnow()

    finally:
        # Capture result values before they might detach
        result = {
            "jobs_found": run.jobs_found if run else 0,
            "jobs_new": run.jobs_new if run else 0,
            "jobs_updated": run.jobs_updated if run else 0,
            "status": run.status if run else "failed",
        }

        if run:
            try:
                db.commit()
            except Exception:
                db.rollback()

        if scraper:
            try:
                await scraper.close()
            except Exception:
                pass

        # Update company stats
        try:
            update_company_stats(db)
            db.commit()
        except Exception as e:
            print(f"  [Scrape] Failed to update company stats: {e}")
            db.rollback()

        # Extract and link skills for new/updated jobs
        try:
            from app.analyzers.skill_extractor import extract_and_link_skills
            count = extract_and_link_skills(db)
            print(f"  [Scrape] Linked {count} job-skill associations")
        except Exception as e:
            print(f"  [Scrape] Failed to extract skills: {e}")

        # Generate daily snapshot
        try:
            from app.services.analysis_service import generate_snapshot
            generate_snapshot()
            print(f"  [Scrape] Daily snapshot generated")
        except Exception as e:
            print(f"  [Scrape] Failed to generate snapshot: {e}")

        db.close()
        return result


AI_REQUIRED_KEYWORDS = [
    "AI", "人工智能", "大模型", "AIGC", "智能", "算法", "machine learning", "深度学习",
    "LLM", "GPT", "chatgpt", "copilot", "agent", "prompt", "提示词", "模型",
    "神经网络", "自然语言处理", "计算机视觉", "语音识别", "推荐系统",
    "文心", "通义", "kimi", "豆包", "混元", "星火", "claude", "数据标注",
    "训练师", "RLHF", "SFT", "对齐", "生成式",
]


def is_ai_related(title: str, desc: str = "") -> bool:
    """Check if a job is AI-related based on title and description."""
    text = (title + " " + (desc or "")).lower()
    return any(kw.lower() in text for kw in AI_REQUIRED_KEYWORDS)


def upsert_job(db: Session, job_data: JobData) -> tuple:
    """
    Insert or update a job record. Returns (1, True) for new, (1, False) for update.
    """
    if not job_data.platform_job_id or not job_data.title:
        return (0, False)

    # Skip non-AI jobs
    if not is_ai_related(job_data.title, job_data.description_text or ""):
        return (0, False)

    existing = db.query(Job).filter(
        Job.platform == job_data.platform,
        Job.platform_job_id == job_data.platform_job_id,
    ).first()

    if existing:
        if existing.is_active:
            existing.last_seen_at = datetime.utcnow()
            # Update fields that might change
            if job_data.salary_min is not None:
                existing.salary_min = job_data.salary_min
            if job_data.salary_max is not None:
                existing.salary_max = job_data.salary_max
            if job_data.description_text:
                existing.description_text = job_data.description_text
            existing.job_type = job_data.job_type or existing.job_type
            db.flush()
            return (1, False)
        else:
            existing.is_active = True
            existing.last_seen_at = datetime.utcnow()
            db.flush()
            return (1, True)
    else:
        new_job = Job(
            platform=job_data.platform,
            platform_job_id=job_data.platform_job_id,
            title=job_data.title,
            company_name=job_data.company_name,
            company_size=job_data.company_size,
            company_industry=job_data.company_industry,
            location_city=job_data.location_city,
            location_district=job_data.location_district,
            salary_min=job_data.salary_min,
            salary_max=job_data.salary_max,
            salary_months=job_data.salary_months,
            job_type=job_data.job_type or "其他",
            job_subtype=job_data.job_subtype,
            experience_required=job_data.experience_required,
            education_required=job_data.education_required,
            description_text=job_data.description_text,
            benefits=job_data.benefits,
            posting_date=job_data.posting_date or date.today(),
            first_seen_at=datetime.utcnow(),
            last_seen_at=datetime.utcnow(),
            is_active=True,
            raw_json=job_data.raw_json,
        )
        db.add(new_job)
        db.commit()
        return (1, True)


def _update_job_detail(db: Session, job_data: JobData):
    """Update an existing job with detail page data (description, education, etc.)."""
    job = db.query(Job).filter(
        Job.platform == job_data.platform,
        Job.platform_job_id == job_data.platform_job_id,
    ).first()
    if not job:
        return
    if job_data.description_text:
        job.description_text = job_data.description_text
    if job_data.education_required:
        job.education_required = job_data.education_required
    if job_data.benefits:
        job.benefits = job_data.benefits
    if job_data.job_type:
        job.job_type = job_data.job_type
    if job_data.job_subtype:
        job.job_subtype = job_data.job_subtype
    if job_data.raw_json:
        job.raw_json = job_data.raw_json
    db.flush()


def update_company_stats(db: Session):
    """Update aggregated company statistics from jobs table."""
    # Get distinct companies from jobs
    from sqlalchemy import case

    companies = db.query(
        Job.company_name,
        func.count(Job.id).label("total"),
        func.sum(case((Job.is_active == True, 1), else_=0)).label("active"),
        func.avg(Job.salary_min).label("avg_min"),
        func.avg(Job.salary_max).label("avg_max"),
        func.max(Job.company_size).label("size"),
        func.max(Job.company_industry).label("industry"),
        func.max(Job.location_city).label("city"),
        func.min(Job.first_seen_at).label("first_seen"),
        func.max(Job.last_seen_at).label("last_seen"),
    ).group_by(Job.company_name).all()

    for row in companies:
        name, total, active, avg_min, avg_max, size, industry, city, first_seen, last_seen = row
        if not name:
            continue

        company = db.query(Company).filter(Company.name == name).first()
        if company:
            company.size = size or company.size
            company.industry = industry or company.industry
            company.location_city = city or company.location_city
            company.avg_salary_min = round(float(avg_min), 1) if avg_min else None
            company.avg_salary_max = round(float(avg_max), 1) if avg_max else None
            company.active_job_count = int(active or 0)
            company.total_job_count = int(total or 0)
            company.last_scraped_at = last_seen
        else:
            company = Company(
                name=name,
                size=size,
                industry=industry,
                location_city=city,
                avg_salary_min=round(float(avg_min), 1) if avg_min else None,
                avg_salary_max=round(float(avg_max), 1) if avg_max else None,
                active_job_count=int(active or 0),
                total_job_count=int(total or 0),
                first_seen_at=first_seen,
                last_scraped_at=last_seen,
            )
            db.add(company)

    db.commit()


def mark_inactive_jobs(db: Session, days: int = 14):
    """Mark jobs as inactive if not seen for N days."""
    cutoff = datetime.utcnow() - timedelta(days=days)
    db.query(Job).filter(
        Job.is_active == True,
        Job.last_seen_at < cutoff,
    ).update({"is_active": False})
    db.commit()
