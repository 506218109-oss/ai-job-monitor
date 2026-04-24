import json
from datetime import date, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import Job, JobSnapshot, Skill, JobSkill, Company


def generate_snapshot():
    """Generate a daily snapshot of job statistics."""
    db = SessionLocal()
    try:
        today = date.today()

        # Check if snapshot already exists for today
        existing = db.query(JobSnapshot).filter(JobSnapshot.snapshot_date == today).first()
        if existing:
            print(f"Snapshot for {today} already exists, updating.")
        else:
            existing = JobSnapshot(snapshot_date=today)

        # Total counts
        existing.total_active = db.query(func.count(Job.id)).filter(Job.is_active == True).scalar() or 0
        existing.total_all_time = db.query(func.count(Job.id)).scalar() or 0

        # New today
        existing.new_today = db.query(func.count(Job.id)).filter(
            func.date(Job.first_seen_at) == today
        ).scalar() or 0

        # Removed today (was active yesterday, inactive today)
        yesterday = today - timedelta(days=1)
        existing.removed_today = db.query(func.count(Job.id)).filter(
            Job.is_active == False,
            func.date(Job.last_seen_at) == yesterday,
        ).scalar() or 0

        # Jobs by type
        type_rows = db.query(Job.job_type, func.count(Job.id)).filter(
            Job.is_active == True
        ).group_by(Job.job_type).all()
        existing.jobs_by_type = json.dumps({t: c for t, c in type_rows}, ensure_ascii=False)

        # Jobs by city
        city_rows = db.query(Job.location_city, func.count(Job.id)).filter(
            Job.is_active == True, Job.location_city.isnot(None)
        ).group_by(Job.location_city).all()
        existing.jobs_by_city = json.dumps({c or "未知": cnt for c, cnt in city_rows}, ensure_ascii=False)

        # Avg salary by type
        sal_rows = db.query(
            Job.job_type,
            func.avg(Job.salary_min).label("avg_min"),
            func.avg(Job.salary_max).label("avg_max"),
        ).filter(Job.is_active == True, Job.salary_min.isnot(None)).group_by(Job.job_type).all()
        existing.avg_salary_by_type = json.dumps({
            t: {"min": round(mn, 1) if mn else 0, "max": round(mx, 1) if mx else 0}
            for t, mn, mx in sal_rows
        }, ensure_ascii=False)

        # Top companies
        company_rows = db.query(Job.company_name, func.count(Job.id)).filter(
            Job.is_active == True
        ).group_by(Job.company_name).order_by(func.count(Job.id).desc()).limit(15).all()
        existing.top_companies = json.dumps(
            [{"name": n, "count": c} for n, c in company_rows], ensure_ascii=False
        )

        # Top skills
        skill_rows = db.query(
            Skill.name, Skill.name_cn, func.count(JobSkill.job_id).label("cnt")
        ).join(JobSkill, Skill.id == JobSkill.skill_id).join(
            Job, JobSkill.job_id == Job.id
        ).filter(Job.is_active == True).group_by(Skill.id).order_by(
            func.count(JobSkill.job_id).desc()
        ).limit(20).all()
        existing.top_skills = json.dumps(
            [{"name": n, "name_cn": nc, "count": cnt} for n, nc, cnt in skill_rows], ensure_ascii=False
        )

        if existing.id is None:
            db.add(existing)

        db.commit()
        print(f"Snapshot generated for {today}: {existing.total_active} active jobs")

        return existing

    finally:
        db.close()


def compute_trends(days: int = 30):
    """Return trend data for charts."""
    db = SessionLocal()
    try:
        snapshots = db.query(JobSnapshot).order_by(
            JobSnapshot.snapshot_date.asc()
        ).limit(days).all()
        return [
            {
                "date": s.snapshot_date.isoformat() if s.snapshot_date else None,
                "total_active": s.total_active,
                "total_all_time": s.total_all_time,
                "new_today": s.new_today,
            }
            for s in snapshots
        ]
    finally:
        db.close()
