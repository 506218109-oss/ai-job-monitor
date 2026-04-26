from fastapi import APIRouter, Query, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from datetime import date, datetime, time, timedelta

from app.database import get_db
from app.models import Job, JobSnapshot, JobSkill, Skill, Company

router = APIRouter()


@router.get("/analytics/overview")
def get_overview(db: Session = Depends(get_db)):
    total_active = db.query(func.count(Job.id)).filter(Job.is_active == True).scalar() or 0
    total_all_time = db.query(func.count(Job.id)).scalar() or 0
    today = date.today()
    today_start = datetime.combine(today, time.min)
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

    skill_counts = db.query(
        Skill.name, Skill.name_cn, Skill.category, func.count(JobSkill.job_id).label("cnt")
    ).join(JobSkill, Skill.id == JobSkill.skill_id).join(Job, JobSkill.job_id == Job.id).filter(
        Job.is_active == True
    ).group_by(Skill.id).order_by(desc("cnt")).limit(20).all()

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
        "top_skills": [{"name": n, "name_cn": nc, "category": cat, "count": cnt} for n, nc, cat, cnt in skill_counts if cnt > 0],
    }


@router.get("/analytics/trends")
def get_trends(days: int = Query(30, le=365), db: Session = Depends(get_db)):
    snapshots = db.query(JobSnapshot).order_by(JobSnapshot.snapshot_date.asc()).limit(days).all()
    return [
        {
            "date": s.snapshot_date.isoformat() if s.snapshot_date else None,
            "total_active": s.total_active,
            "total_all_time": s.total_all_time,
            "new_today": s.new_today,
        }
        for s in snapshots
    ]


@router.get("/analytics/by-type")
def get_by_type(db: Session = Depends(get_db)):
    rows = db.query(
        Job.job_type,
        func.count(Job.id).label("cnt"),
        func.avg(Job.salary_min).label("avg_min"),
        func.avg(Job.salary_max).label("avg_max"),
    ).filter(Job.is_active == True).group_by(Job.job_type).order_by(desc("cnt")).all()

    return [
        {
            "type": r[0],
            "count": r[1],
            "avg_salary_min": round(r[2], 1) if r[2] else 0,
            "avg_salary_max": round(r[3], 1) if r[3] else 0,
        }
        for r in rows
    ]


@router.get("/analytics/by-company")
def get_by_company(limit: int = Query(15, le=50), db: Session = Depends(get_db)):
    companies = db.query(Company).order_by(Company.active_job_count.desc().nullslast()).limit(limit).all()
    result = []
    for c in companies:
        type_counts = db.query(
            Job.job_type, func.count(Job.id)
        ).filter(Job.company_name == c.name, Job.is_active == True).group_by(Job.job_type).all()
        result.append({
            "name": c.name,
            "size": c.size,
            "industry": c.industry,
            "location_city": c.location_city,
            "avg_salary_min": c.avg_salary_min,
            "avg_salary_max": c.avg_salary_max,
            "active_job_count": c.active_job_count,
            "total_job_count": c.total_job_count,
            "top_types": [{"type": t, "count": cnt} for t, cnt in type_counts],
        })
    return result


@router.get("/analytics/skills/top")
def get_top_skills(
    limit: int = Query(20, le=50),
    job_type: str = Query(None),
    db: Session = Depends(get_db),
):
    q = db.query(
        Skill.name, Skill.name_cn, Skill.category, func.count(JobSkill.job_id).label("cnt")
    ).join(JobSkill, Skill.id == JobSkill.skill_id).join(Job, JobSkill.job_id == Job.id).filter(
        Job.is_active == True
    )
    if job_type:
        q = q.filter(Job.job_type == job_type)

    rows = q.group_by(Skill.id).order_by(desc("cnt")).limit(limit).all()

    total_active = db.query(func.count(Job.id)).filter(Job.is_active == True).scalar() or 1
    return [
        {"name": n, "name_cn": nc, "category": cat, "count": cnt, "pct": round(cnt / total_active * 100, 1)}
        for n, nc, cat, cnt in rows
    ]


@router.get("/analytics/salary")
def get_salary_distribution(
    group_by: str = Query("job_type"),
    db: Session = Depends(get_db),
):
    col = getattr(Job, group_by, Job.job_type)
    rows = db.query(
        col,
        func.avg(Job.salary_min).label("avg_min"),
        func.avg(Job.salary_max).label("avg_max"),
        func.min(Job.salary_min).label("min_min"),
        func.max(Job.salary_max).label("max_max"),
        func.count(Job.id).label("cnt"),
    ).filter(Job.is_active == True, Job.salary_min.isnot(None)).group_by(col).order_by(desc("cnt")).all()

    return [
        {"group": r[0] or "未知", "avg_min": round(r[1], 1) if r[1] else 0,
         "avg_max": round(r[2], 1) if r[2] else 0,
         "min_min": r[3], "max_max": r[4], "count": r[5]}
        for r in rows if r[0]
    ]


@router.get("/analytics/insights")
def get_recruitment_insights(db: Session = Depends(get_db)):
    from app.analyzers.insight_extractor import extract_recruitment_insights
    return extract_recruitment_insights(db)


@router.get("/analytics/export/csv")
def export_csv(db: Session = Depends(get_db)):
    jobs = db.query(Job).filter(Job.is_active == True).order_by(Job.posting_date.desc().nullslast()).all()
    lines = ["id,title,company,location_city,job_type,salary_min,salary_max,experience,education,posting_date"]
    for j in jobs:
        lines.append(
            f'{j.id},"{j.title}","{j.company_name}","{j.location_city or ""}",'
            f'"{j.job_type}",{j.salary_min or ""},{j.salary_max or ""},'
            f'"{j.experience_required or ""}","{j.education_required or ""}",{j.posting_date or ""}'
        )
    from fastapi.responses import PlainTextResponse
    return PlainTextResponse("\n".join(lines), media_type="text/csv")
