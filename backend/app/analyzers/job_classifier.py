from typing import Optional

UNRECOGNIZED_JOB_TYPE = "未识别"
LEGACY_UNRECOGNIZED_TYPES = {"", "其他", UNRECOGNIZED_JOB_TYPE}
NON_ACTIONABLE_JOB_TYPES = {"其他", UNRECOGNIZED_JOB_TYPE}

AI_KEYWORDS = [
    "AI", "人工智能", "大模型", "AIGC", "智能", "算法", "machine learning", "深度学习",
    "LLM", "GPT", "chatgpt", "copilot", "agent", "prompt", "提示词",
    "神经网络", "自然语言处理", "计算机视觉", "语音识别", "推荐系统",
    "文心", "通义", "kimi", "豆包", "混元", "星火", "claude",
    "模型", "数据科学", "RLHF", "SFT", "对齐", "生成式", "genai",
]

# Rules are (job_type, priority, title_keywords, desc_keywords)
# Higher priority = checked first
CLASSIFICATION_RULES = [
    ("提示词工程", 10,
     ["提示词工程师", "Prompt Engineer", "Prompt Engineering", "提示词"],
     ["提示词", "prompt engineer", "指令设计", "prompt engineering"]),

    ("训练/标注/评测", 9,
     ["训练师", "标注", "数据标注", "语料", "RLHF", "SFT", "对齐", "评测", "Evaluator"],
     ["数据标注", "训练数据", "语料库", "RLHF", "标注平台", "模型评测", "质量评估"]),

    ("产品经理", 10,
     [
         "产品经理", "产品负责人", "产品总监", "Product Manager", "Product Management",
         "Principal Product", "Director (Product)", "Sr. Director (Product)", "Group Product",
         "AI Product", "产品策划", "产品专家", "Product Lead", "Product Owner",
     ],
     ["产品规划", "PRD", "需求分析", "产品方案"]),

    ("AI运营", 8,
     ["运营", "AI运营", "大模型运营", "产品运营", "内容运营", "用户运营", "策略运营", "Community", "Product Support"],
     ["AI产品运营", "大模型运营", "社区运营", "生态运营", "用户运营"]),

    ("商业化/增长", 8,
     [
         "商业化", "增长", "变现", "Monetization", "Growth", "Go To Market", "GTM",
         "Commercialization", "Business Development", "商务拓展",
     ],
     ["商业化", "变现", "营收", "AI产品推广", "增长策略", "商务拓展", "go-to-market"]),

    ("销售/客户成功", 7,
     [
         "销售", "客户经理", "大客户", "Account Manager", "Customer Success", "Sales",
         "Channel", "Client Partner", "客户成功", "SKA",
     ],
     ["销售", "客户成功", "客户关系", "渠道策略", "商务谈判", "大客户"]),

    ("职能/支持", 7,
     [
         "Recruiter", "招聘", "HRBP", "Human Resources", "Finance", "Accounting",
         "Legal", "Policy", "Trust & Safety", "Loss Prevention", "Security Manager",
         "Warehouse", "Logistics", "Facility", "Facilities", "Quality Manager",
         "Schedule Lead", "Operations Manager", "Program Manager", "Project Manager",
     ],
     ["招聘", "财务", "法务", "合规", "人力资源", "仓储", "物流", "设施管理", "质量管理"]),

    ("解决方案/交付", 7,
     [
         "解决方案", "方案架构师", "Solution Architect", "Solutions Architect",
         "Implementation", "Delivery", "Field Engineer", "Pre-sales", "售前",
     ],
     ["解决方案", "售前", "客户交付", "实施交付", "行业方案"]),

    ("策略/分析", 6,
     [
         "Strategy", "Strategist", "策略", "分析师", "Analyst", "Analytics",
         "Market Intelligence", "Competitive Intelligence", "Business Operations",
         "运营分析", "数据分析师",
     ],
     ["策略分析", "市场洞察", "竞争分析", "商业分析", "数据分析"]),

    ("市场/品牌", 6,
     [
         "市场", "Marketing", "Brand", "品牌", "Evangelist", "Developer Relations",
         "DevRel", "传播", "公关", "PR Manager",
     ],
     ["市场推广", "品牌", "内容营销", "开发者关系", "公关传播"]),

    ("技术研发", 5,
     [
         "工程师", "Engineer", "Engineering", "研发", "开发", "Developer", "DevOps",
         "Software", "Algorithm", "算法", "Research Scientist", "Scientist",
         "Architect", "ETL", "Data Scientist", "Machine Learning",
     ],
     ["工程实现", "系统设计", "模型训练", "算法研发", "软件开发"]),
]


def classify_job(title: str, description: str = "") -> tuple:
    """
    Classify a job into type and subtype.
    Returns (job_type, job_subtype).
    """
    title_lower = title.lower()
    desc_lower = description.lower() if description else ""

    functional_patterns = [
        "recruit", "招聘", "hrbp", "human resources", "finance", "accounting",
        "legal", "policy", "trust & safety", "loss prevention", "warehouse",
        "logistics", "facility", "facilities", "quality manager", "schedule lead",
    ]
    for pat in functional_patterns:
        if pat.lower() in title_lower:
            return ("职能/支持", _extract_subtype(title, "职能/支持"))

    if "market intelligence" in title_lower or "competitive intelligence" in title_lower:
        return ("策略/分析", _extract_subtype(title, "策略/分析"))

    market_patterns = ["市场", "marketing", "brand", "品牌", "evangelist", "developer relations", "devrel"]
    for pat in market_patterns:
        if pat in title_lower:
            return ("市场/品牌", _extract_subtype(title, "市场/品牌"))

    # Filter obvious dev/engineering roles before broad AI keyword fallback.
    # Keep exceptions for product, ops, GTM and solution titles that mention tech context.
    dev_patterns = [
        "工程师", "算法工程师", "研发工程师", "开发工程师", "软件工程师",
        "测试工程师", "运维工程师", "数据工程师", "系统工程师",
        "java开发", "python开发", "golang开发", "c++开发",
        "前端开发", "后端开发", "全栈", "devops",
        "技术架构师", "系统架构师", "软件架构师",
        "研究员", "研究科学家", "research scientist",
        "机器学习工程师", "深度学习工程师",
        "software engineer", "engineering manager", "production engineering",
        "data engineer", "security engineer", "etl",
    ]
    for pat in dev_patterns:
        if pat.lower() in title_lower:
            title_has_role = any(r in title_lower for r in [
                "产品经理", "产品运营", "运营", "增长", "商业化",
                "营销", "商务", "销售", "客户", "方案", "交付",
                "product management", "product manager", "go to market", "gtm",
                "customer", "sales", "solution", "solutions", "delivery",
            ])
            if not title_has_role:
                return ("技术研发", _extract_subtype(title, "技术研发"))

    # Check classification rules ordered by priority
    for job_type, priority, title_kws, desc_kws in sorted(CLASSIFICATION_RULES, key=lambda x: -x[1]):
        for kw in title_kws:
            if kw.lower() in title_lower:
                # Determine subtype from title
                subtype = _extract_subtype(title, job_type)
                return (job_type, subtype)

    # Fallback: check description
    for job_type, priority, title_kws, desc_kws in sorted(CLASSIFICATION_RULES, key=lambda x: -x[1]):
        for kw in desc_kws:
            if kw.lower() in desc_lower:
                subtype = _extract_subtype(title, job_type)
                return (job_type, subtype)

    is_ai_related = any(kw.lower() in title_lower or kw.lower() in desc_lower for kw in AI_KEYWORDS)

    if not is_ai_related:
        return (UNRECOGNIZED_JOB_TYPE, "")

    # Product / Ops roles with AI nexus — check BEFORE generic fallback
    # All matching against lowercase title
    ai_product_kws = {kw.lower() for kw in ["AI", "人工智能", "大模型", "AIGC", "智能", "agent", "copilot", "策略产品", "数据产品"]}
    ai_ops_kws = {kw.lower() for kw in ["AI", "人工智能", "大模型", "AIGC", "智能", "agent", "豆包", "元宝"]}

    if "产品" in title_lower and any(kw in title_lower for kw in ai_product_kws):
        subtype = _extract_subtype(title, "产品经理")
        return ("产品经理", subtype)
    if any(r in title_lower for r in ["运营", "营销", "增长"]):
        if any(kw in title_lower for kw in ai_ops_kws):
            subtype = _extract_subtype(title, "AI运营")
            return ("AI运营", subtype)
    if "商业化" in title_lower:
        subtype = _extract_subtype(title, "商业化/增长")
        return ("商业化/增长", subtype)
    if "方案" in title_lower and "架构师" in title_lower:
        return ("解决方案/交付", "解决方案架构师")
    if "数据标注" in title_lower or "训练师" in title_lower or "语料" in title_lower:
        subtype = _extract_subtype(title, "训练/标注/评测")
        return ("训练/标注/评测", subtype)
    if "提示词" in title_lower or "prompt" in title_lower:
        return ("提示词工程", "提示词工程师")

    return (UNRECOGNIZED_JOB_TYPE, "")


def normalize_job_type(job_type: Optional[str]) -> str:
    """Normalize legacy catch-all labels to the current unknown label."""
    if not job_type or job_type in LEGACY_UNRECOGNIZED_TYPES:
        return UNRECOGNIZED_JOB_TYPE
    return job_type


def is_actionable_job_type(job_type: Optional[str]) -> bool:
    return normalize_job_type(job_type) not in NON_ACTIONABLE_JOB_TYPES


def reclassify_existing_jobs(db, active_only: bool = True) -> int:
    """Refresh stored job_type/job_subtype values using the latest classifier."""
    from app.models import Job

    query = db.query(Job)
    if active_only:
        query = query.filter(Job.is_active == True)

    changed = 0
    for job in query.all():
        job_type, job_subtype = classify_job(job.title or "", job.description_text or "")
        job_type = normalize_job_type(job_type)
        job_subtype = job_subtype or None
        if job.job_type != job_type or (job.job_subtype or None) != job_subtype:
            job.job_type = job_type
            job.job_subtype = job_subtype
            changed += 1
    return changed


def _extract_subtype(title: str, job_type: str) -> str:
    """Extract more specific subtype from job title."""
    title_lower = title.lower()
    if job_type == "产品经理":
        if "大模型" in title_lower or "llm" in title_lower:
            return "大模型产品经理"
        if "策略" in title_lower:
            return "策略产品经理"
        if "数据产品" in title_lower or "数据" in title_lower:
            return "数据产品经理"
        if "ai产品" in title_lower:
            return "AI产品经理"
    elif job_type == "AI运营":
        if "大模型" in title_lower:
            return "大模型运营"
        if "产品运营" in title_lower:
            return "AI产品运营"
        if "用户运营" in title_lower:
            return "用户运营"
        if "策略运营" in title_lower:
            return "策略运营"
    elif job_type == "商业化/增长":
        if "ai商业化" in title_lower or "aigc商业化" in title_lower:
            return "AI商业化"
        if "go to market" in title_lower or "gtm" in title_lower:
            return "GTM"
        if "monetization" in title_lower or "commercialization" in title_lower:
            return "商业化"
        if "增长" in title_lower:
            return "AI增长"
        if "growth" in title_lower:
            return "增长"
    elif job_type == "销售/客户成功":
        if "account" in title_lower or "客户经理" in title_lower:
            return "客户经理"
        if "customer success" in title_lower or "客户成功" in title_lower:
            return "客户成功"
        if "sales" in title_lower or "销售" in title_lower:
            return "销售"
    elif job_type == "职能/支持":
        if "recruit" in title_lower or "招聘" in title_lower or "hrbp" in title_lower:
            return "招聘/HR"
        if "finance" in title_lower or "accounting" in title_lower:
            return "财务"
        if "warehouse" in title_lower or "logistics" in title_lower or "物流" in title_lower:
            return "仓储/物流"
        if "policy" in title_lower or "trust & safety" in title_lower:
            return "政策/安全"
        if "facility" in title_lower or "quality" in title_lower:
            return "设施/质量"
    elif job_type == "解决方案/交付":
        if "架构师" in title_lower or "architect" in title_lower:
            return "解决方案架构师"
        if "delivery" in title_lower or "implementation" in title_lower:
            return "交付实施"
    elif job_type == "策略/分析":
        if "market intelligence" in title_lower or "competitive intelligence" in title_lower:
            return "市场/竞争情报"
        if "analytics" in title_lower or "analyst" in title_lower or "分析" in title_lower:
            return "分析"
        if "strategy" in title_lower or "strategist" in title_lower or "策略" in title_lower:
            return "策略"
    elif job_type == "市场/品牌":
        if "brand" in title_lower or "品牌" in title_lower:
            return "品牌"
        if "marketing" in title_lower or "市场" in title_lower:
            return "市场"
        if "evangelist" in title_lower or "devrel" in title_lower:
            return "开发者关系"
    elif job_type == "技术研发":
        if "security" in title_lower:
            return "安全工程"
        if "data" in title_lower:
            return "数据工程"
        if "engineer" in title_lower or "工程师" in title_lower:
            return "工程研发"
    elif job_type == "训练/标注/评测":
        if "训练师" in title_lower:
            return "AI训练师"
        if "标注" in title_lower:
            return "数据标注"
        if "评测" in title_lower or "evaluator" in title_lower:
            return "模型评测"
    elif job_type == "提示词工程":
        return "提示词工程师"
    return ""
