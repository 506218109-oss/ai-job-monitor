from fastapi import APIRouter, Query, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from app.database import get_db
from app.models import Skill, JobSkill, Job

router = APIRouter()


@router.get("/skills")
def list_skills(category: str = Query(None), db: Session = Depends(get_db)):
    q = db.query(
        Skill.id, Skill.name, Skill.name_cn, Skill.category,
        func.count(JobSkill.job_id).label("job_count")
    ).outerjoin(JobSkill, Skill.id == JobSkill.skill_id).join(
        Job, (JobSkill.job_id == Job.id) & (Job.is_active == True), isouter=True
    ).group_by(Skill.id)

    if category:
        q = q.filter(Skill.category == category)

    rows = q.order_by(desc("job_count")).all()
    return [
        {"id": r[0], "name": r[1], "name_cn": r[2], "category": r[3], "job_count": r[4] or 0}
        for r in rows
    ]
