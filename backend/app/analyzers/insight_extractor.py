import re
import json
from collections import Counter
from datetime import datetime, date, timedelta
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Job, JobSkill, Skill, JobSnapshot

# Key AI concepts to track in job descriptions
AI_CONCEPTS = {
    "大模型/LLM": ["大模型", "LLM", "GPT", "大语言模型", "语言模型", "预训练", "预训练模型"],
    "Agent/智能体": ["agent", "智能体", "自主决策", "多智能体"],
    "Prompt Engineering": ["prompt", "提示词", "指令设计", "few-shot", "上下文学习"],
    "RAG/检索增强": ["RAG", "检索增强", "知识库", "向量检索", "知识增强"],
    "模型微调": ["SFT", "RLHF", "微调", "fine-tun", "指令微调", "对齐"],
    "多模态": ["多模态", "文生图", "文生视频", "图生文", "语音识别", "视觉理解"],
    "模型评估": ["模型评估", "效果评估", "评测体系", "benchmark", "模型评测"],
    "AI产品方法论": ["产品规划", "需求分析", "PRD", "竞品分析", "用户研究"],
    "数据分析": ["数据分析", "SQL", "指标体系", "A/B测试", "埋点", "数据驱动"],
    "商业化": ["商业化", "变现", "ROI", "营收", "增长", "盈利模式"],
    "协作/项目管理": ["跨部门", "推动", "协调", "项目管理", "scrum", "敏捷"],
}


def extract_recruitment_insights(db: Session) -> dict:
    """
    Analyze all active jobs to extract recruitment trends and patterns.
    Returns a structured dictionary with insights.
    """
    active_jobs = db.query(Job).filter(Job.is_active == True).all()
    if not active_jobs:
        return {}

    total = len(active_jobs)

    # 1. Job type distribution
    type_counts = Counter(j.job_type for j in active_jobs)
    type_pcts = {k: round(v / total * 100) for k, v in type_counts.most_common()}

    # 2. Experience requirements
    exp_required = Counter()
    for j in active_jobs:
        exp = j.experience_required
        if not exp:
            exp_required["未标注"] += 1
        elif "应届" in exp or "不限" in exp or "经验不限" in exp:
            exp_required["不限/应届"] += 1
        elif any(p in exp for p in ["1年", "一年", "2年", "两年"]):
            exp_required["1-2年"] += 1
        elif any(p in exp for p in ["3年", "三年", "4年", "四年"]):
            exp_required["3-4年"] += 1
        elif any(p in exp for p in ["5年", "五年", "6年", "六年", "7年", "七年"]):
            exp_required["5-7年"] += 1
        elif any(p in exp for p in ["8年", "八年", "10年", "十年"]):
            exp_required["8年+"] += 1
        else:
            exp_required["未标注"] += 1

    # 3. Education requirements
    edu_required = Counter()
    for j in active_jobs:
        edu = j.education_required
        if not edu:
            edu_required["未标注"] += 1
        elif "博士" in edu or "Ph.D" in edu:
            edu_required["博士"] += 1
        elif "硕士" in edu or "研究生" in edu:
            edu_required["硕士"] += 1
        elif "本科" in edu or "学士" in edu:
            edu_required["本科"] += 1
        elif "大专" in edu:
            edu_required["大专"] += 1
        elif "不限" in edu:
            edu_required["不限"] += 1
        else:
            edu_required["未标注"] += 1

    # 4. AI concepts frequency in descriptions
    concept_freq = Counter()
    for j in active_jobs:
        full_text = f"{j.title} {j.description_text or ''}".lower()
        for concept_name, keywords in AI_CONCEPTS.items():
            if any(kw.lower() in full_text for kw in keywords):
                concept_freq[concept_name] += 1

    concept_pcts = {k: round(v / total * 100) for k, v in concept_freq.most_common(12)}

    # 5. Top skills (from job_skills table)
    top_skills = []
    skill_rows = db.query(
        Skill.name_cn, Skill.category, func.count(JobSkill.job_id).label("cnt")
    ).join(JobSkill, Skill.id == JobSkill.skill_id
    ).join(Job, JobSkill.job_id == Job.id
    ).filter(Job.is_active == True
    ).group_by(Skill.id
    ).order_by(func.count(JobSkill.job_id).desc()
    ).limit(15).all()

    for skill_name, category, cnt in skill_rows:
        top_skills.append({
            "name": skill_name or skill_name,
            "category": category,
            "count": cnt,
            "pct": round(cnt / total * 100),
        })

    # 6. New jobs today / recent trends
    today = date.today()
    today_new = db.query(func.count(Job.id)).filter(
        Job.first_seen_at >= today
    ).scalar() or 0

    yesterday_new = db.query(func.count(Job.id)).filter(
        Job.first_seen_at >= today - timedelta(days=1),
        Job.first_seen_at < today
    ).scalar() or 0

    # 7. City distribution
    city_counts = Counter(j.location_city for j in active_jobs if j.location_city)
    cities_top = city_counts.most_common(6)

    # 8. Latest snapshot for trend comparison
    latest_snap = db.query(JobSnapshot).order_by(
        JobSnapshot.snapshot_date.desc()
    ).first()

    yesterday_snap = db.query(JobSnapshot).filter(
        JobSnapshot.snapshot_date == today - timedelta(days=1)
    ).first()

    trend = {
        "total_active": total,
        "today_new": today_new,
        "yesterday_new": yesterday_new,
        "trend_direction": "up" if today_new > yesterday_new else "down" if today_new < yesterday_new else "flat",
        "prev_total": yesterday_snap.total_active if yesterday_snap else None,
    }

    # 9. Generate daily summary text
    summary_text = _generate_summary(
        total, type_pcts, exp_required, edu_required,
        concept_pcts, top_skills, trend, cities_top
    )

    return {
        "total_active": total,
        "today_new": today_new,
        "type_distribution": dict(type_counts.most_common()),
        "type_percentages": type_pcts,
        "experience_distribution": dict(exp_required),
        "education_distribution": dict(edu_required),
        "ai_concepts": dict(concept_freq.most_common(12)),
        "ai_concept_percentages": concept_pcts,
        "top_skills": top_skills,
        "city_distribution": [{"city": c, "count": n} for c, n in cities_top],
        "trend": trend,
        "summary_text": summary_text,
        "generated_at": datetime.utcnow().isoformat(),
    }


def _generate_summary(total, type_pcts, exp, edu, concepts, skills, trend, cities):
    """Generate a human-readable daily summary."""
    lines = []

    # Overall
    lines.append(f"当前监测到 **{total}** 个 AI 相关非研发岗位")

    # Type breakdown
    type_items = [f"**{t}**（{p}%）" for t, p in list(type_pcts.items())[:3]]
    if type_items:
        lines.append(f"岗位类型以 {', '.join(type_items)} 为主")

    # City
    if cities:
        top_cities = [f"**{c[0]}**（{c[1]}个）" for c in cities[:3]]
        lines.append(f"主要城市集中在 {', '.join(top_cities)}")

    # Experience
    top_exp = exp.most_common(3)
    if top_exp:
        exp_str = "、".join(f"**{e}**（{n}个）" for e, n in top_exp)
        lines.append(f"经验要求分布：{exp_str}")

    # Education
    top_edu = edu.most_common(3)
    if top_edu:
        edu_str = "、".join(f"**{e}**（{n}个）" for e, n in top_edu)
        lines.append(f"学历要求分布：{edu_str}")

    # Hot AI concepts
    if concepts:
        top_concepts = [f"**{c}**（{p}%）" for c, p in list(concepts.items())[:5]]
        lines.append(f"热门 AI 能力要求：{', '.join(top_concepts)}")

    # Hot skills
    if skills:
        top_skill_names = [f"**{s['name']}**" for s in skills[:5]]
        lines.append(f"高频技能关键词：{', '.join(top_skill_names)}")

    # Trend
    if trend["today_new"] > 0:
        lines.append(f"今日新增 **{trend['today_new']}** 个岗位")
    else:
        lines.append(f"今日暂无新增岗位")

    return lines
