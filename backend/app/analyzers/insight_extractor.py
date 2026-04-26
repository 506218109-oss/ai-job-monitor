from collections import Counter
from datetime import datetime, date, time, timedelta
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
}

SKILL_CATEGORY_LABELS = {
    "ai_knowledge": "AI技术认知",
    "product": "产品能力",
    "data": "数据/指标能力",
    "domain": "业务与商业化能力",
    "soft": "通用协作能力",
}

INDUSTRY_SIGNALS = [
    {
        "topic": "Agent/RAG 产品化",
        "concepts": ["Agent/智能体", "RAG/检索增强"],
        "viewpoint": "行业和 KOL 讨论正在从通用聊天转向可执行任务、企业知识库和工具调用，岗位会更偏场景拆解、流程设计和效果评估。",
        "advice": "准备一个 RAG 或 Agent 项目案例，讲清楚知识来源、流程编排、失败处理和评估指标。",
    },
    {
        "topic": "AI 产品评测与安全",
        "concepts": ["模型评估"],
        "viewpoint": "大模型应用进入落地阶段后，企业更关注可控性、稳定性、内容安全和效果验证，这会推高评测、合规和反馈闭环要求。",
        "advice": "简历里补充模型输出评估、A/B 实验、人工反馈闭环或安全审核相关经历。",
    },
    {
        "topic": "多模态与内容生产",
        "concepts": ["多模态"],
        "viewpoint": "AI 视频、图像、语音和内容生成仍是应用创新高频方向，内容平台与 C 端产品会持续需要懂场景和用户体验的人。",
        "advice": "如果目标是产品/运营岗位，可以准备一个多模态场景分析，说明用户需求、生成质量和商业化路径。",
    },
    {
        "topic": "AI 商业化与增长",
        "concepts": ["商业化"],
        "viewpoint": "招聘从“会不会 AI”逐步转向“能否把 AI 做成业务结果”，商业化、ROI、行业方案和增长指标会变得更重要。",
        "advice": "把过往项目包装成业务结果：效率提升、转化率、留存、收入或成本下降，而不只是功能描述。",
    },
]


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
    concept_jobs = {name: [] for name in AI_CONCEPTS}
    for j in active_jobs:
        full_text = f"{j.title} {j.description_text or ''}".lower()
        for concept_name, keywords in AI_CONCEPTS.items():
            if any(kw.lower() in full_text for kw in keywords):
                concept_freq[concept_name] += 1
                if len(concept_jobs[concept_name]) < 3:
                    concept_jobs[concept_name].append(_build_evidence_example(j, keywords))

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
            "category_label": SKILL_CATEGORY_LABELS.get(category, category),
            "count": cnt,
            "pct": round(cnt / total * 100),
        })

    # 6. New jobs today / recent trends
    today = date.today()
    today_start = datetime.combine(today, time.min)
    tomorrow_start = today_start + timedelta(days=1)
    yesterday_start = today_start - timedelta(days=1)
    seven_days_ago = today_start - timedelta(days=7)

    today_new = db.query(func.count(Job.id)).filter(
        Job.first_seen_at >= today_start,
        Job.first_seen_at < tomorrow_start,
    ).scalar() or 0

    yesterday_new = db.query(func.count(Job.id)).filter(
        Job.first_seen_at >= yesterday_start,
        Job.first_seen_at < today_start,
    ).scalar() or 0

    new_7days = db.query(func.count(Job.id)).filter(
        Job.first_seen_at >= seven_days_ago,
        Job.first_seen_at < tomorrow_start,
    ).scalar() or 0

    removed_today = db.query(func.count(Job.id)).filter(
        Job.is_active == False,
        Job.last_seen_at >= today_start,
        Job.last_seen_at < tomorrow_start,
    ).scalar() or 0

    # 7. City distribution
    city_counts = Counter(j.location_city for j in active_jobs if j.location_city)
    cities_top = city_counts.most_common(6)

    # 8. Company distribution and sample caveat
    company_counts = Counter(j.company_name for j in active_jobs if j.company_name)
    companies_top = [
        {"name": name, "count": count, "pct": round(count / total * 100)}
        for name, count in company_counts.most_common(6)
    ]

    # 9. Latest snapshot for trend comparison
    yesterday_snap = db.query(JobSnapshot).filter(
        JobSnapshot.snapshot_date == today - timedelta(days=1)
    ).first()

    trend = {
        "total_active": total,
        "today_new": today_new,
        "removed_today": removed_today,
        "new_last_7_days": new_7days,
        "yesterday_new": yesterday_new,
        "trend_direction": "up" if today_new > yesterday_new else "down" if today_new < yesterday_new else "flat",
        "prev_total": yesterday_snap.total_active if yesterday_snap else None,
    }

    skill_groups = _group_skills_by_category(top_skills)
    market_signals = _build_market_signals(concept_pcts)
    career_advice = _build_career_advice(type_counts, concept_pcts, top_skills)
    evidence_examples = {
        name: examples
        for name, examples in concept_jobs.items()
        if examples and name in concept_pcts
    }

    daily_radar = _build_daily_radar(total, trend, type_pcts, concept_pcts, cities_top, companies_top)

    # 10. Generate daily summary text
    summary_text = _generate_summary(
        total, type_pcts, exp_required, edu_required,
        concept_pcts, top_skills, trend, cities_top, companies_top
    )

    return {
        "total_active": total,
        "today_new": today_new,
        "removed_today": removed_today,
        "new_last_7_days": new_7days,
        "type_distribution": dict(type_counts.most_common()),
        "type_percentages": type_pcts,
        "experience_distribution": dict(exp_required),
        "education_distribution": dict(edu_required),
        "ai_concepts": dict(concept_freq.most_common(12)),
        "ai_concept_percentages": concept_pcts,
        "top_skills": top_skills,
        "skill_groups": skill_groups,
        "city_distribution": [{"city": c, "count": n} for c, n in cities_top],
        "company_distribution": companies_top,
        "market_signals": market_signals,
        "career_advice": career_advice,
        "evidence_examples": evidence_examples,
        "daily_radar": daily_radar,
        "positioning": "每日追踪腾讯、字节 AI 非研发岗位，从 JD 细节中提取能力要求，并结合行业/KOL观点输出求职准备建议。",
        "data_note": "当前样本聚焦腾讯与字节跳动，跨公司对比应同时参考公司招聘入口、抓取关键词和样本占比。",
        "trend": trend,
        "summary_text": summary_text,
        "generated_at": datetime.utcnow().isoformat(),
    }


def _generate_summary(total, type_pcts, exp, edu, concepts, skills, trend, cities, companies):
    """Generate a human-readable daily summary."""
    lines = []

    # Overall
    lines.append(f"当前监测到 {total} 个腾讯/字节 AI 相关非研发岗位，重点用于观察产品、运营、商业化等求职趋势。")

    if companies:
        company_items = [f"{c['name']} {c['count']} 个" for c in companies[:2]]
        lines.append(f"样本来源以 {'、'.join(company_items)} 为主，解读趋势时需要注意公司样本占比。")

    # Type breakdown
    type_items = [f"{t}（{p}%）" for t, p in list(type_pcts.items())[:3]]
    if type_items:
        lines.append(f"岗位类型以 {'、'.join(type_items)} 为主，可优先拆解这些岗位的 JD 要求准备简历。")

    # City
    if cities:
        top_cities = [f"{c[0]}（{c[1]}个）" for c in cities[:3]]
        lines.append(f"主要城市集中在 {'、'.join(top_cities)}，求职时可按城市机会密度安排投递优先级。")

    # Experience
    top_exp = exp.most_common(3)
    if top_exp:
        exp_str = "、".join(f"{e}（{n}个）" for e, n in top_exp)
        lines.append(f"经验要求分布为 {exp_str}，可用于判断校招/转岗/社招的匹配度。")

    # Education
    top_edu = edu.most_common(3)
    if top_edu:
        edu_str = "、".join(f"{e}（{n}个）" for e, n in top_edu)
        lines.append(f"学历要求分布为 {edu_str}，但实际筛选仍应结合岗位细分方向判断。")

    # Hot AI concepts
    if concepts:
        top_concepts = [f"{c}（{p}%）" for c, p in list(concepts.items())[:5]]
        lines.append(f"JD 中高频 AI 信号包括 {'、'.join(top_concepts)}，这些应成为简历和面试案例的关键词。")

    # Hot skills
    if skills:
        top_skill_names = [s["name"] for s in skills[:5]]
        lines.append(f"高频能力关键词包括 {'、'.join(top_skill_names)}，建议用具体项目证明，而不是只写“了解 AI”。")

    # Trend
    lines.append(f"今日新增 {trend['today_new']} 个岗位，下线 {trend['removed_today']} 个岗位，近 7 天新增 {trend['new_last_7_days']} 个岗位。")

    return lines


def _group_skills_by_category(skills):
    grouped = {}
    for skill in skills:
        category = skill["category"]
        label = skill["category_label"]
        if category not in grouped:
            grouped[category] = {"category": category, "label": label, "count": 0, "skills": []}
        grouped[category]["count"] += skill["count"]
        grouped[category]["skills"].append(skill)

    ordered = ["ai_knowledge", "product", "data", "domain", "soft"]
    return [grouped[k] for k in ordered if k in grouped]


def _build_market_signals(concept_pcts):
    signals = []
    for item in INDUSTRY_SIGNALS:
        matched = [
            {"name": concept, "pct": concept_pcts.get(concept, 0)}
            for concept in item["concepts"]
            if concept in concept_pcts
        ]
        signals.append({
            "topic": item["topic"],
            "source_type": "行业/KOL观点",
            "viewpoint": item["viewpoint"],
            "job_signal": matched,
            "advice": item["advice"],
        })
    return signals


def _build_career_advice(type_counts, concept_pcts, skills):
    skill_names = {s["name"] for s in skills}
    return [
        {
            "role": "AI产品经理",
            "signal": f"当前样本中产品经理岗位 {type_counts.get('产品经理', 0)} 个，是最主要的非研发 AI 机会。",
            "prepare": [
                "准备一个 AI 产品从需求、方案、指标到迭代的完整案例。",
                "重点补 RAG/Agent、模型评测、数据指标和用户反馈闭环。",
                "简历中把“了解大模型”改写成具体场景、输入输出、效果指标。",
            ],
        },
        {
            "role": "AI运营",
            "signal": f"AI运营岗位 {type_counts.get('AI运营', 0)} 个，通常连接内容、用户、模型反馈和增长。",
            "prepare": [
                "准备 Prompt 优化、内容质量、用户反馈或模型输出分析案例。",
                "突出数据分析、策略迭代和跨部门推动能力。",
                "如果有社群、内容、用户增长经历，要说明如何迁移到 AI 应用场景。",
            ],
        },
        {
            "role": "商业化/增长",
            "signal": f"商业化/增长岗位 {type_counts.get('商业化/增长', 0)} 个，更看重 AI 场景能否转化为业务结果。",
            "prepare": [
                "准备行业场景、客户痛点、ROI 和增长指标相关案例。",
                "将 AI 能力翻译成效率提升、收入增长、成本下降或转化提升。",
                "关注企业知识库、智能客服、营销生成、行业解决方案等落地方向。",
            ],
        },
        {
            "role": "训练/标注/评测",
            "signal": f"模型评估相关 JD 信号占比 {concept_pcts.get('模型评估', 0)}%，说明评测和反馈闭环正在变重要。",
            "prepare": [
                "补充数据质量、标注规范、评测维度和 bad case 分析经验。",
                "理解 SFT/RLHF/人工反馈的基本流程。",
                "把细致度、标准制定和行业知识作为差异化优势。",
            ],
        },
    ]


def _build_daily_radar(total, trend, type_pcts, concept_pcts, cities, companies):
    top_type = next(iter(type_pcts.items()), None)
    top_concept = next(iter(concept_pcts.items()), None)
    top_city = cities[0] if cities else None
    top_company = companies[0] if companies else None

    return [
        {
            "label": "今天在招什么",
            "value": f"{total} 个活跃岗位",
            "detail": f"今日新增 {trend['today_new']} 个，下线 {trend['removed_today']} 个，近 7 天新增 {trend['new_last_7_days']} 个。",
        },
        {
            "label": "主需求方向",
            "value": top_type[0] if top_type else "暂无",
            "detail": f"占活跃岗位 {top_type[1]}%，适合优先拆解 JD 与简历关键词。" if top_type else "暂无岗位类型数据。",
        },
        {
            "label": "高频 AI 信号",
            "value": top_concept[0] if top_concept else "暂无",
            "detail": f"在 {top_concept[1]}% 的岗位中出现，建议准备可追溯项目证据。" if top_concept else "暂无 AI 能力数据。",
        },
        {
            "label": "机会密集区域",
            "value": top_city[0] if top_city else "暂无",
            "detail": f"{top_city[1]} 个岗位集中在该城市。" if top_city else "暂无城市数据。",
        },
        {
            "label": "样本占比提醒",
            "value": top_company["name"] if top_company else "暂无",
            "detail": f"{top_company['count']} 个岗位来自该公司，占样本 {top_company['pct']}%。" if top_company else "暂无公司数据。",
        },
    ]


def _build_evidence_example(job, keywords):
    text = job.description_text or job.title or ""
    snippet = _extract_snippet(text, keywords)
    return {
        "id": job.id,
        "title": job.title,
        "company_name": job.company_name,
        "location_city": job.location_city,
        "job_type": job.job_type,
        "snippet": snippet,
    }


def _extract_snippet(text, keywords, radius=42):
    if not text:
        return ""
    lower = text.lower()
    for kw in keywords:
        idx = lower.find(kw.lower())
        if idx >= 0:
            start = max(0, idx - radius)
            end = min(len(text), idx + len(kw) + radius)
            prefix = "..." if start > 0 else ""
            suffix = "..." if end < len(text) else ""
            return prefix + text[start:end].replace("\n", " ").strip() + suffix
    return text[:100].replace("\n", " ").strip()
