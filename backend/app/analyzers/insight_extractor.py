from collections import Counter
from datetime import datetime, date, time, timedelta
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Job, JobSkill, Skill, JobSnapshot, JobEvent
from app.analyzers.job_classifier import normalize_job_type
from app.services.market_signal_service import get_market_sources, get_sources_for_topics
from app.target_companies import TARGET_COMPANY_NAMES

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

PRIMARY_DEMAND_EXCLUDED_TYPES = {"其他", "未识别", "技术研发"}

INDUSTRY_SIGNALS = [
    {
        "topic": "Agent/RAG 产品化",
        "concepts": ["Agent/智能体", "RAG/检索增强"],
        "source_topics": ["Agent", "RAG"],
        "viewpoint": "行业和 KOL 讨论正在从通用聊天转向可执行任务、企业知识库和工具调用，岗位会更偏场景拆解、流程设计和效果评估。",
        "advice": "准备一个 RAG 或 Agent 项目案例，讲清楚知识来源、流程编排、失败处理和评估指标。",
    },
    {
        "topic": "AI 产品评测与安全",
        "concepts": ["模型评估"],
        "source_topics": ["AI产品经理", "AI运营"],
        "viewpoint": "大模型应用进入落地阶段后，企业更关注可控性、稳定性、内容安全和效果验证，这会推高评测、合规和反馈闭环要求。",
        "advice": "简历里补充模型输出评估、A/B 实验、人工反馈闭环或安全审核相关经历。",
    },
    {
        "topic": "多模态与内容生产",
        "concepts": ["多模态"],
        "source_topics": ["多模态", "AI运营"],
        "viewpoint": "AI 视频、图像、语音和内容生成仍是应用创新高频方向，内容平台与 C 端产品会持续需要懂场景和用户体验的人。",
        "advice": "如果目标是产品/运营岗位，可以准备一个多模态场景分析，说明用户需求、生成质量和商业化路径。",
    },
    {
        "topic": "AI 商业化与增长",
        "concepts": ["商业化"],
        "source_topics": ["商业化", "AI产品经理"],
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
    type_counts = Counter(normalize_job_type(j.job_type) for j in active_jobs)
    type_pcts = {k: round(v / total * 100) for k, v in type_counts.most_common()}
    primary_type_counts = Counter({
        job_type: count
        for job_type, count in type_counts.items()
        if job_type not in PRIMARY_DEMAND_EXCLUDED_TYPES
    })
    primary_type_pcts = {
        k: round(v / total * 100)
        for k, v in primary_type_counts.most_common()
    }

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
    event_trends = _build_event_trends(db, today)
    if event_trends["today"]["removed"]:
        removed_today = event_trends["today"]["removed"]

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
    market_sources = get_market_sources()
    market_signals = _build_market_signals(concept_pcts)
    career_advice = _build_career_advice(type_counts, concept_pcts, top_skills)
    evidence_examples = {
        name: examples
        for name, examples in concept_jobs.items()
        if examples and name in concept_pcts
    }

    daily_radar = _build_daily_radar(total, trend, primary_type_pcts, concept_pcts, cities_top, companies_top)

    # 10. Generate daily summary text
    summary_text = _generate_summary(
        total, primary_type_pcts, exp_required, edu_required,
        concept_pcts, top_skills, trend, cities_top, companies_top, TARGET_COMPANY_NAMES
    )

    return {
        "total_active": total,
        "today_new": today_new,
        "removed_today": removed_today,
        "new_last_7_days": new_7days,
        "type_distribution": dict(type_counts.most_common()),
        "type_percentages": type_pcts,
        "primary_type_percentages": primary_type_pcts,
        "experience_distribution": dict(exp_required),
        "education_distribution": dict(edu_required),
        "ai_concepts": dict(concept_freq.most_common(12)),
        "ai_concept_percentages": concept_pcts,
        "top_skills": top_skills,
        "skill_groups": skill_groups,
        "city_distribution": [{"city": c, "count": n} for c, n in cities_top],
        "company_distribution": companies_top,
        "market_signals": market_signals,
        "market_sources": market_sources,
        "event_trends": event_trends,
        "career_advice": career_advice,
        "evidence_examples": evidence_examples,
        "daily_radar": daily_radar,
        "positioning": "每日优先追踪第三方招聘聚合源中的目标公司 AI 相关岗位，从 JD 细节中提取能力要求，并结合行业/KOL观点输出求职准备建议。",
        "trend_policy": {
            "periods": [7, 30],
            "removed_definition": "连续 2 天未抓到同一岗位即标记为下线",
            "track_updates": True,
        },
        "data_note": "当前样本优先来自第三方招聘聚合源；信息源目标公司：" + "、".join(TARGET_COMPANY_NAMES) + "；岗位会优先归入产品、运营、市场、销售、职能等具体方向，未识别和技术研发不参与主需求方向判断。",
        "source_companies": TARGET_COMPANY_NAMES,
        "trend": trend,
        "summary_text": summary_text,
        "generated_at": datetime.utcnow().isoformat(),
    }


def _generate_summary(total, type_pcts, exp, edu, concepts, skills, trend, cities, companies, source_companies):
    """Generate a concise daily summary for the homepage radar."""
    lines = []

    lines.append(f"当前监测到 {total} 个目标公司 AI 相关岗位，重点观察产品、运营、商业化等求职趋势。")

    if companies:
        company_items = [f"{c['name']} {c['count']} 个" for c in companies[:3]]
        lines.append(
            f"信息源目标公司覆盖 {'、'.join(source_companies)}；当前样本以 {'、'.join(company_items)} 为主，解读趋势时需注意公司样本占比。"
        )

    mixed_signals = []
    type_items = [f"{t}（{p}%）" for t, p in list(type_pcts.items())[:3]]
    concept_items = [f"{c}（{p}%）" for c, p in list(concepts.items())[:3]]
    if type_items:
        mixed_signals.append(f"岗位类型以 {'、'.join(type_items)} 为主")
    if concept_items:
        mixed_signals.append(f"JD 高频 AI 信号为 {'、'.join(concept_items)}")
    if mixed_signals:
        lines.append("；".join(mixed_signals) + "，可优先拆解这些 JD 要求准备简历。")

    if cities:
        top_cities = [f"{c[0]}（{c[1]}个）" for c in cities[:3]]
        lines.append(f"主要城市集中在 {'、'.join(top_cities)}，求职时可按城市机会密度安排投递优先级。")

    if skills:
        top_skill_names = [s["name"] for s in skills[:5]]
        lines.append(
            f"高频能力关键词包括 {'、'.join(top_skill_names)}；今日新增 {trend['today_new']} 个岗位，下线 {trend['removed_today']} 个岗位，近 7 天新增 {trend['new_last_7_days']} 个岗位。"
        )
    else:
        lines.append(
            f"今日新增 {trend['today_new']} 个岗位，下线 {trend['removed_today']} 个岗位，近 7 天新增 {trend['new_last_7_days']} 个岗位。"
        )

    return lines[:5]

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
        source_refs = get_sources_for_topics(item.get("source_topics", []))[:10]
        signals.append({
            "topic": item["topic"],
            "source_type": "行业/KOL观点",
            "viewpoint": item["viewpoint"],
            "job_signal": matched,
            "source_topics": item.get("source_topics", []),
            "source_refs": [
                {
                    "name": source["name"],
                    "type": source["type"],
                    "language": source["language"],
                    "url": source["url"],
                }
                for source in source_refs
            ],
            "advice": item["advice"],
        })
    return signals


def _build_career_advice(type_counts, concept_pcts, skills):
    items = [
        {
            "type": "产品经理",
            "role": "AI产品经理",
            "signal": f"当前样本中产品经理岗位 {type_counts.get('产品经理', 0)} 个，是最主要的非研发 AI 机会。",
            "prepare": [
                "准备一个 AI 产品从需求、方案、指标到迭代的完整案例。",
                "重点补 RAG/Agent、模型评测、数据指标和用户反馈闭环。",
                "简历中把“了解大模型”改写成具体场景、输入输出、效果指标。",
            ],
        },
        {
            "type": "AI运营",
            "role": "AI运营",
            "signal": f"AI运营岗位 {type_counts.get('AI运营', 0)} 个，通常连接内容、用户、模型反馈和增长。",
            "prepare": [
                "准备 Prompt 优化、内容质量、用户反馈或模型输出分析案例。",
                "突出数据分析、策略迭代和跨部门推动能力。",
                "如果有社群、内容、用户增长经历，要说明如何迁移到 AI 应用场景。",
            ],
        },
        {
            "type": "商业化/增长",
            "role": "商业化/增长",
            "signal": f"商业化/增长岗位 {type_counts.get('商业化/增长', 0)} 个，更看重 AI 场景能否转化为业务结果。",
            "prepare": [
                "准备行业场景、客户痛点、ROI 和增长指标相关案例。",
                "将 AI 能力翻译成效率提升、收入增长、成本下降或转化提升。",
                "关注企业知识库、智能客服、营销生成、行业解决方案等落地方向。",
            ],
        },
        {
            "type": "市场/品牌",
            "role": "市场/品牌",
            "signal": f"市场/品牌岗位 {type_counts.get('市场/品牌', 0)} 个，重点是把 AI 能力讲成清楚的用户价值和传播主题。",
            "prepare": [
                "准备一个 AI 产品或功能的定位、卖点、渠道和内容节奏案例。",
                "把技术词翻译成用户收益、场景故事和可验证的转化指标。",
                "关注开发者关系、品牌传播、增长内容和行业案例包装。",
            ],
        },
        {
            "type": "销售/客户成功",
            "role": "销售/客户成功",
            "signal": f"销售/客户成功岗位 {type_counts.get('销售/客户成功', 0)} 个，更看重行业场景、客户痛点和 AI 方案落地能力。",
            "prepare": [
                "准备客户画像、痛点诊断、方案匹配和 ROI 说明案例。",
                "把 AI 能力讲成效率提升、成本下降、转化提升或风险降低。",
                "补充 PoC、续约、渠道协同或大客户推进经验。",
            ],
        },
        {
            "type": "职能/支持",
            "role": "职能/支持",
            "signal": f"职能/支持岗位 {type_counts.get('职能/支持', 0)} 个，说明 AI 公司也在补招聘、财务、政策、安全、物流等运营底座。",
            "prepare": [
                "强调对 AI 行业节奏、组织扩张和跨区域协作的理解。",
                "用流程优化、合规意识、供应链或招聘效率等指标证明价值。",
                "简历中说明过往职能经验如何支持 AI 业务快速落地。",
            ],
        },
        {
            "type": "解决方案/交付",
            "role": "解决方案/交付",
            "signal": f"解决方案/交付岗位 {type_counts.get('解决方案/交付', 0)} 个，通常连接客户需求、产品能力和上线结果。",
            "prepare": [
                "准备一个从需求调研、方案设计、PoC 到上线验收的案例。",
                "突出行业 know-how、客户沟通和复杂项目推进能力。",
                "补充 RAG、知识库、智能客服或企业流程自动化方案理解。",
            ],
        },
        {
            "type": "策略/分析",
            "role": "策略/分析",
            "signal": f"策略/分析岗位 {type_counts.get('策略/分析', 0)} 个，重点看市场洞察、竞争分析和数据判断能力。",
            "prepare": [
                "准备一份 AI 产品/公司/赛道的结构化分析样例。",
                "突出数据来源、判断框架、业务假设和可执行建议。",
                "把分析结论和增长、商业化、产品优先级连接起来。",
            ],
        },
        {
            "type": "训练/标注/评测",
            "role": "训练/标注/评测",
            "signal": f"训练/标注/评测岗位 {type_counts.get('训练/标注/评测', 0)} 个；模型评估相关 JD 信号占比 {concept_pcts.get('模型评估', 0)}%。",
            "prepare": [
                "补充数据质量、标注规范、评测维度和 bad case 分析经验。",
                "理解 SFT/RLHF/人工反馈的基本流程。",
                "把细致度、标准制定和行业知识作为差异化优势。",
            ],
        },
    ]

    return sorted(
        items,
        key=lambda item: (
            type_counts.get(item["type"], 0) == 0,
            -type_counts.get(item["type"], 0),
        ),
    )


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


def _build_event_trends(db: Session, today: date):
    JobEvent.__table__.create(bind=db.get_bind(), checkfirst=True)
    windows = {}
    for days in [7, 30]:
        start = today - timedelta(days=days - 1)
        rows = db.query(
            JobEvent.event_type,
            func.count(JobEvent.id),
        ).filter(
            JobEvent.event_date >= start,
            JobEvent.event_date <= today,
        ).group_by(JobEvent.event_type).all()
        counts = _normalize_event_counts(rows)

        by_company_rows = db.query(
            JobEvent.company_name,
            JobEvent.event_type,
            func.count(JobEvent.id),
        ).filter(
            JobEvent.event_date >= start,
            JobEvent.event_date <= today,
        ).group_by(JobEvent.company_name, JobEvent.event_type).all()
        by_company = {}
        for company, event_type, count in by_company_rows:
            if not company:
                continue
            by_company.setdefault(company, {"new": 0, "updated": 0, "removed": 0, "reactivated": 0})
            key = _event_count_key(event_type)
            by_company[company][key] += count

        windows[str(days)] = {
            "days": days,
            "start_date": start.isoformat(),
            "end_date": today.isoformat(),
            **counts,
            "by_company": [
                {"company": company, **values}
                for company, values in sorted(by_company.items(), key=lambda item: item[1]["new"], reverse=True)
            ],
        }

    today_rows = db.query(
        JobEvent.event_type,
        func.count(JobEvent.id),
    ).filter(JobEvent.event_date == today).group_by(JobEvent.event_type).all()

    return {
        "today": _normalize_event_counts(today_rows),
        "windows": windows,
    }


def _normalize_event_counts(rows):
    counts = {"new": 0, "updated": 0, "removed": 0, "reactivated": 0}
    for event_type, count in rows:
        counts[_event_count_key(event_type)] += count
    return counts


def _event_count_key(event_type):
    if event_type in {"new", "updated", "removed", "reactivated"}:
        return event_type
    return "updated"


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
