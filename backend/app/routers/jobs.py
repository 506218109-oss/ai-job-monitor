from pathlib import Path
from fastapi import APIRouter, Query, Depends, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.database import get_db
from app.models import Job, JobSkill, Skill

TEMPLATES_DIR = Path(__file__).resolve().parent.parent.parent / "frontend" / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

router = APIRouter()


@router.get("/jobs")
def list_jobs(
    request: Request,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    job_type: str = Query(None),
    company_name: str = Query(None),
    location_city: str = Query(None),
    salary_min: int = Query(None),
    salary_max: int = Query(None),
    platform: str = Query(None),
    keyword: str = Query(None),
    is_active: bool = Query(True),
    sort_by: str = Query("posting_date"),
    order: str = Query("desc"),
    db: Session = Depends(get_db),
):
    q = db.query(Job)

    if platform:
        q = q.filter(Job.platform == platform)

    if is_active:
        q = q.filter(Job.is_active == True)
    if job_type:
        q = q.filter(Job.job_type == job_type)
    if company_name:
        q = q.filter(Job.company_name.like(f"%{company_name}%"))
    if location_city:
        q = q.filter(Job.location_city == location_city)
    if salary_min is not None:
        q = q.filter(Job.salary_max >= salary_min)
    if salary_max is not None:
        q = q.filter(Job.salary_min <= salary_max)
    if keyword:
        q = q.filter(
            (Job.title.like(f"%{keyword}%")) | (Job.description_text.like(f"%{keyword}%"))
        )

    total = q.count()

    sort_col = getattr(Job, sort_by, Job.posting_date)
    if order == "asc":
        q = q.order_by(sort_col.asc())
    else:
        q = q.order_by(sort_col.desc().nullslast())

    items = q.offset((page - 1) * per_page).limit(per_page).all()

    result = []
    for job in items:
        result.append({
            "id": job.id,
            "platform": job.platform,
            "platform_job_id": job.platform_job_id,
            "title": job.title,
            "company_name": job.company_name,
            "company_size": job.company_size,
            "company_industry": job.company_industry,
            "location_city": job.location_city,
            "location_district": job.location_district,
            "salary_min": job.salary_min,
            "salary_max": job.salary_max,
            "salary_months": job.salary_months,
            "job_type": job.job_type,
            "job_subtype": job.job_subtype,
            "experience_required": job.experience_required,
            "education_required": job.education_required,
            "posting_date": job.posting_date.isoformat() if job.posting_date else None,
            "is_active": job.is_active,
            "skills": [
                {
                    "id": js.skill.id,
                    "name": js.skill.name,
                    "name_cn": js.skill.name_cn,
                    "category": js.skill.category,
                    "category_label": _skill_category_label(js.skill.category),
                }
                for js in job.job_skills
            ],
        })

    pages = max(1, (total + per_page - 1) // per_page)

    if request.headers.get("HX-Request") == "true" or request.headers.get("hx-request") == "true":
        return templates.TemplateResponse("partials/job_table.html", {
            "request": request, "items": result, "total": total, "page": page, "pages": pages
        })
    return {"items": result, "total": total, "page": page, "pages": pages}


@router.get("/jobs/{job_id}")
def get_job(job_id: int, db: Session = Depends(get_db)):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        return {"error": "not found"}, 404
    return {
        "id": job.id,
        "platform": job.platform,
        "platform_job_id": job.platform_job_id,
        "title": job.title,
        "company_name": job.company_name,
        "company_size": job.company_size,
        "company_industry": job.company_industry,
        "location_city": job.location_city,
        "location_district": job.location_district,
        "salary_min": job.salary_min,
        "salary_max": job.salary_max,
        "salary_months": job.salary_months,
        "job_type": job.job_type,
        "job_subtype": job.job_subtype,
        "experience_required": job.experience_required,
        "education_required": job.education_required,
        "description_text": job.description_text,
        "benefits": job.benefits,
        "posting_date": job.posting_date.isoformat() if job.posting_date else None,
        "first_seen_at": job.first_seen_at.isoformat() if job.first_seen_at else None,
        "last_seen_at": job.last_seen_at.isoformat() if job.last_seen_at else None,
        "is_active": job.is_active,
        "skills": [
            {
                "id": js.skill.id,
                "name": js.skill.name,
                "name_cn": js.skill.name_cn,
                "category": js.skill.category,
                "category_label": _skill_category_label(js.skill.category),
            }
            for js in job.job_skills
        ],
    }


def _skill_category_label(category: str) -> str:
    labels = {
        "ai_knowledge": "AI技术认知",
        "product": "产品能力",
        "data": "数据/指标能力",
        "domain": "业务与商业化能力",
        "soft": "通用协作能力",
    }
    return labels.get(category, category or "其他")
