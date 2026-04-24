from fastapi import APIRouter, Query, Depends
from sqlalchemy.orm import Session
from sqlalchemy import desc
from app.database import get_db
from app.models import Company, Job

router = APIRouter()


@router.get("/companies")
def list_companies(
    sort_by: str = Query("job_count"),
    limit: int = Query(20, le=50),
    db: Session = Depends(get_db),
):
    col = getattr(Company, sort_by, Company.active_job_count)
    companies = db.query(Company).order_by(col.desc().nullslast()).limit(limit).all()
    return [
        {
            "id": c.id,
            "name": c.name,
            "size": c.size,
            "industry": c.industry,
            "location_city": c.location_city,
            "avg_salary_min": c.avg_salary_min,
            "avg_salary_max": c.avg_salary_max,
            "active_job_count": c.active_job_count,
            "total_job_count": c.total_job_count,
        }
        for c in companies
    ]


@router.get("/companies/{company_id}")
def get_company(company_id: int, db: Session = Depends(get_db)):
    c = db.query(Company).filter(Company.id == company_id).first()
    if not c:
        return {"error": "not found"}, 404

    recent_jobs = db.query(Job).filter(
        Job.company_name == c.name, Job.is_active == True
    ).order_by(Job.posting_date.desc().nullslast()).limit(10).all()

    return {
        "id": c.id,
        "name": c.name,
        "size": c.size,
        "industry": c.industry,
        "location_city": c.location_city,
        "avg_salary_min": c.avg_salary_min,
        "avg_salary_max": c.avg_salary_max,
        "active_job_count": c.active_job_count,
        "total_job_count": c.total_job_count,
        "recent_jobs": [
            {
                "id": j.id,
                "title": j.title,
                "job_type": j.job_type,
                "salary_min": j.salary_min,
                "salary_max": j.salary_max,
                "posting_date": j.posting_date.isoformat() if j.posting_date else None,
            }
            for j in recent_jobs
        ],
    }
