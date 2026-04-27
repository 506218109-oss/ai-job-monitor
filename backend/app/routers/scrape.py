import asyncio
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.database import get_db, SessionLocal
from app.models import ScrapeRun
from app.schemas import ScrapeTrigger
from app.config import settings
from app.services.scraping_service import run_scrape
from app.scrapers.official_jobs import get_official_source_statuses
from app.scrapers.third_party_jobs import get_third_party_source_statuses

router = APIRouter()


def _run_scrape_sync(platform: str, keywords: list[str] = None):
    """Wrapper to run async scrape from sync context."""
    asyncio.run(run_scrape(platform, keywords))


@router.get("/scrape/status")
def get_scrape_status(db: Session = Depends(get_db)):
    current = db.query(ScrapeRun).filter(ScrapeRun.status == "running").first()
    if current and current.started_at and current.started_at < datetime.utcnow() - timedelta(minutes=30):
        current.status = "failed"
        current.finished_at = datetime.utcnow()
        current.error_message = current.error_message or "运行超过 30 分钟，已自动标记为超时"
        db.commit()
        current = None

    last = db.query(ScrapeRun).filter(ScrapeRun.status != "running").order_by(
        desc(ScrapeRun.finished_at)
    ).first()

    return {
        "current_run": {
            "id": current.id, "platform": current.platform, "keyword": current.keyword,
            "started_at": current.started_at.isoformat() if current and current.started_at else None,
            "status": current.status,
        } if current else None,
        "last_run": {
            "id": last.id, "platform": last.platform,
            "started_at": last.started_at.isoformat() if last and last.started_at else None,
            "finished_at": last.finished_at.isoformat() if last and last.finished_at else None,
            "status": last.status, "jobs_found": last.jobs_found, "jobs_new": last.jobs_new,
            "error_message": last.error_message,
        } if last else None,
    }


@router.get("/scrape/history")
def get_scrape_history(limit: int = 20, db: Session = Depends(get_db)):
    runs = db.query(ScrapeRun).order_by(desc(ScrapeRun.started_at)).limit(limit).all()
    return [
        {
            "id": r.id, "platform": r.platform, "keyword": r.keyword,
            "started_at": r.started_at.isoformat() if r.started_at else None,
            "finished_at": r.finished_at.isoformat() if r.finished_at else None,
            "pages_scraped": r.pages_scraped, "jobs_found": r.jobs_found,
            "jobs_new": r.jobs_new, "status": r.status,
            "error_message": r.error_message,
        }
        for r in runs
    ]


@router.post("/scrape/trigger")
def trigger_scrape(
    body: ScrapeTrigger = None,
    background_tasks: BackgroundTasks = None,
    platform: str = None,
    db: Session = Depends(get_db),
):
    # Support both body and query param for platform
    if body and body.platform:
        platforms = [body.platform]
    elif platform:
        platforms = [platform]
    else:
        platforms = [settings.DEFAULT_PLATFORM]

    keywords = body.keywords if body and body.keywords else None

    if platforms == ["all"]:
        platforms = ["third_party"]

    # Check if a scrape is already running
    running = db.query(ScrapeRun).filter(ScrapeRun.status == "running").first()
    if running:
        return {"message": "Scrape already in progress", "status": "running", "run_id": running.id}

    run_ids = []
    for p in platforms:
        run = ScrapeRun(
            platform=p,
            keyword=", ".join(keywords) if keywords else "default",
            started_at=datetime.utcnow(),
            status="pending",
        )
        db.add(run)
        db.commit()
        run_ids.append(run.id)

        # Launch in background
        if background_tasks:
            background_tasks.add_task(_run_scrape_sync, p, keywords)

    return {"message": f"Scrape started for {', '.join(platforms)}", "status": "started", "run_ids": run_ids}


@router.get("/scrape/sources")
def get_scrape_sources():
    return {
        "sources": [
            *get_third_party_source_statuses(),
            {
                "id": "tencent",
                "company": "腾讯",
                "region": "中国",
                "status": "manual",
                "career_url": "https://careers.tencent.com",
                "note": "公开招聘官网 API；为避免影响后续官网投递链路，默认调度不触发，仅保留手动备选。",
            },
            {
                "id": "bytedance",
                "company": "字节跳动",
                "region": "中国",
                "status": "skipped",
                "career_url": "https://jobs.bytedance.com",
                "note": "当前实现依赖 CSRF token；默认全量任务不再触发。",
            },
            *get_official_source_statuses(),
        ]
    }
