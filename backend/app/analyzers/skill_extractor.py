import json
import re
import jieba

from sqlalchemy.orm import Session
from app.models import Job, Skill, JobSkill


def extract_and_link_skills(db: Session, job_id: int = None):
    """
    Extract skills from job descriptions and create job-skill associations.
    If job_id is provided, process only that job. Otherwise process all active jobs.
    """
    skills = db.query(Skill).all()
    skill_dict = {}
    for s in skills:
        try:
            keywords = json.loads(s.keywords)
        except (json.JSONDecodeError, TypeError):
            keywords = []
        skill_dict[s.id] = {"name": s.name, "keywords": keywords}

    if job_id:
        jobs = db.query(Job).filter(Job.id == job_id).all()
    else:
        jobs = db.query(Job).filter(Job.is_active == True, Job.description_text.isnot(None)).all()

    total_matched = 0

    for job in jobs:
        # Remove existing associations
        db.query(JobSkill).filter(JobSkill.job_id == job.id).delete()

        text = ""
        if job.title:
            text += job.title + " "
        if job.description_text:
            text += job.description_text

        if not text:
            continue

        text_lower = text.lower()

        # Jieba tokenize for Chinese segmentation
        tokens = set(jieba.cut(text))
        tokens_lower = set(t.lower() for t in tokens)

        matched_skills = set()

        for skill_id, skill_info in skill_dict.items():
            keywords = skill_info["keywords"]
            matched = False

            for kw in keywords:
                kw_lower = kw.lower()
                # Exact match in text
                if kw_lower in text_lower:
                    matched = True
                    break
                # Substring match in tokens
                for token in tokens_lower:
                    if kw_lower in token and len(kw_lower) >= 2:
                        matched = True
                        break
                if matched:
                    break

            if matched:
                matched_skills.add(skill_id)

        # Insert associations
        for skill_id in matched_skills:
            js = JobSkill(job_id=job.id, skill_id=skill_id)
            db.add(js)
            total_matched += 1

    db.commit()
    return total_matched
