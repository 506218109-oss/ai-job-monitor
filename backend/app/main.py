import os
from pathlib import Path
from datetime import datetime, date, timedelta

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.requests import Request
from sqlalchemy import func
from apscheduler.schedulers.background import BackgroundScheduler

from app.config import settings
from app.database import SessionLocal
from app.models import Job, Company, JobSnapshot, Skill, JobSkill
from app.routers import jobs, analytics, skills, companies, scrape

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "frontend" / "templates"
STATIC_DIR = Path(__file__).resolve().parent.parent / "frontend" / "static"

app = FastAPI(title="AI Job Monitor", version="1.0.0")


@app.on_event("startup")
def startup_init():
    """Create tables and seed skills on first run."""
    from app.database import engine, Base, SessionLocal
    from app.models import Skill

    # Ensure data directory + create all tables
    (settings.PROJECT_ROOT / "data").mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind=engine)

    # Seed skill dictionary if empty
    from app.seed_data import SEED_SKILLS
    db = SessionLocal()
    try:
        if db.query(Skill).count() == 0:
            for name, name_cn, category, keywords in SEED_SKILLS:
                db.add(Skill(name=name, name_cn=name_cn, category=category, keywords=keywords))
            db.commit()
    finally:
        db.close()


# Allow Railway to set the port via $PORT
_railway_port = int(os.environ.get("PORT", 0))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=_railway_port or 8000)
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

app.include_router(jobs.router, prefix="/api", tags=["jobs"])
app.include_router(analytics.router, prefix="/api", tags=["analytics"])
app.include_router(skills.router, prefix="/api", tags=["skills"])
app.include_router(companies.router, prefix="/api", tags=["companies"])
app.include_router(scrape.router, prefix="/api", tags=["scrape"])


def get_overview_stats():
    db = SessionLocal()
    try:
        total_active = db.query(func.count(Job.id)).filter(Job.is_active == True).scalar() or 0
        total_all_time = db.query(func.count(Job.id)).scalar() or 0
        now = datetime.utcnow()
        today_start = datetime.combine(now.date(), datetime.min.time())
        tomorrow_start = today_start + timedelta(days=1)
        seven_days_ago = today_start - timedelta(days=7)
        today_new = db.query(func.count(Job.id)).filter(
            Job.first_seen_at >= today_start,
            Job.first_seen_at < tomorrow_start,
        ).scalar() or 0
        removed_today = db.query(func.count(Job.id)).filter(
            Job.is_active == False,
            Job.last_seen_at >= today_start,
            Job.last_seen_at < tomorrow_start,
        ).scalar() or 0
        new_7days = db.query(func.count(Job.id)).filter(
            Job.first_seen_at >= seven_days_ago
        ).scalar() or 0
        companies_count = db.query(func.count(Company.id)).scalar() or 0

        avg_sal = db.query(
            func.avg(Job.salary_min), func.avg(Job.salary_max)
        ).filter(Job.is_active == True, Job.salary_min.isnot(None)).first()

        type_counts = db.query(
            Job.job_type, func.count(Job.id)
        ).filter(Job.is_active == True).group_by(Job.job_type).order_by(func.count(Job.id).desc()).all()

        company_counts = db.query(
            Job.company_name, func.count(Job.id)
        ).filter(Job.is_active == True).group_by(Job.company_name).order_by(func.count(Job.id).desc()).limit(10).all()

        skill_rows = db.query(
            Skill.name, Skill.name_cn, Skill.category, func.count(JobSkill.job_id).label("cnt")
        ).join(JobSkill, Skill.id == JobSkill.skill_id).join(Job, JobSkill.job_id == Job.id).filter(
            Job.is_active == True
        ).group_by(Skill.id).order_by(func.count(JobSkill.job_id).desc()).limit(20).all()

        return {
            "total_active": total_active,
            "total_all_time": total_all_time,
            "today_new": today_new,
            "removed_today": removed_today,
            "new_last_7_days": new_7days,
            "companies_tracked": companies_count,
            "avg_salary_min": round(avg_sal[0], 1) if avg_sal and avg_sal[0] else 0,
            "avg_salary_max": round(avg_sal[1], 1) if avg_sal and avg_sal[1] else 0,
            "top_types": [{"type": t, "count": c} for t, c in type_counts],
            "top_companies": [{"name": n, "count": c} for n, c in company_counts],
            "top_skills": [{"name": n, "name_cn": nc, "category": cat, "count": cnt}
                           for n, nc, cat, cnt in skill_rows if cnt > 0],
        }
    finally:
        db.close()


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/")
async def dashboard_page(request: Request):
    try:
        stats = get_overview_stats()
        return templates.TemplateResponse("pages/dashboard.html", {"request": request, "stats": stats})
    except Exception as e:
        return {"error": str(e), "type": type(e).__name__}


@app.get("/jobs")
async def jobs_page(request: Request):
    return templates.TemplateResponse("pages/jobs.html", {"request": request})


@app.get("/jobs/{job_id}")
async def job_detail_page(request: Request, job_id: int):
    return templates.TemplateResponse("pages/job_detail.html", {"request": request, "job_id": job_id})


@app.get("/analytics")
async def analytics_page(request: Request):
    return templates.TemplateResponse("pages/analytics.html", {"request": request})


@app.get("/admin")
async def admin_page(request: Request):
    return templates.TemplateResponse("pages/admin.html", {"request": request})


import asyncio


def scheduled_scrape():
    """Run the full scrape pipeline for all platforms (called by APScheduler)."""
    from app.services.scraping_service import run_scrape
    from app.config import settings
    platforms = ["third_party"]
    for p in platforms:
        print(f"[Scheduler] Starting {p} scrape at {datetime.utcnow()}")
        try:
            result = asyncio.run(run_scrape(p, settings.SEARCH_KEYWORDS))
            print(f"[Scheduler] {p} done: {result['jobs_new']} new, {result['jobs_found']} total")
        except Exception as e:
            print(f"[Scheduler] {p} failed: {e}")


scheduler = BackgroundScheduler()
scheduler.add_job(
    scheduled_scrape,
    "cron",
    hour=settings.SCRAPE_TIME_HOUR,
    minute=settings.SCRAPE_TIME_MINUTE,
    id="daily_scrape",
    name="Daily multi-platform scrape",
)
scheduler.start()
