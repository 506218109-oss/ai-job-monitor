import re

# Rules are (job_type, priority, title_keywords, desc_keywords)
# Higher priority = checked first
CLASSIFICATION_RULES = [
    ("提示词工程", 10,
     ["提示词工程师", "Prompt Engineer", "Prompt Engineering", "提示词"],
     ["提示词", "prompt engineer", "指令设计", "prompt engineering"]),

    ("训练/标注", 9,
     ["训练师", "标注", "数据标注", "语料", "RLHF", "SFT", "对齐"],
     ["数据标注", "训练数据", "语料库", "RLHF", "标注平台"]),

    ("商业化/增长", 8,
     ["商业化", "增长", "变现", "AI销售", "AI市场", "商务"],
     ["商业化", "变现", "营收", "AI产品推广", "商务拓展"]),

    ("AI运营", 8,
     ["运营", "AI运营", "大模型运营", "产品运营", "内容运营", "用户运营", "策略运营"],
     ["AI产品运营", "大模型运营", "社区运营", "生态运营"]),

    ("产品经理", 10,
     ["产品经理", "产品负责人", "产品总监", "Product Manager", "PM"],
     ["产品规划", "PRD", "需求分析", "产品方案"]),
]


def classify_job(title: str, description: str = "") -> tuple:
    """
    Classify a job into type and subtype.
    Returns (job_type, job_subtype).
    """
    title_lower = title.lower()
    desc_lower = description.lower() if description else ""

    # Filter out obvious dev/engineering roles.
    # Use whole-word patterns to avoid false positives like
    # "开发者服务" (a product name) or "解决方案架构师" (a pre-sales role).
    dev_patterns = [
        # Engineer titles (exact)
        "工程师", "算法工程师", "研发工程师", "开发工程师", "软件工程师",
        "测试工程师", "运维工程师", "数据工程师", "系统工程师",
        "java开发", "python开发", "golang开发", "c++开发",
        "前端开发", "后端开发", "全栈", "devops",
        # Architect (only pure tech, not solutions/pre-sales)
        "技术架构师", "系统架构师", "软件架构师",
        # Scientist / Researcher
        "研究员", "研究科学家", "research scientist",
        "机器学习工程师", "深度学习工程师",
        "ETL",
    ]
    for pat in dev_patterns:
        if pat.lower() in title_lower:
            # Check exceptions: product/ops titles that contain tech context
            title_has_role = any(r in title_lower for r in [
                "产品经理", "产品运营", "运营", "增长", "商业化",
                "营销", "商务", "销售", "客户", "方案", "交付",
            ])
            if not title_has_role:
                return ("其他", "")

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

    # Check if it's AI-related at all
    ai_keywords = [
        "AI", "人工智能", "大模型", "AIGC", "智能", "算法", "machine learning", "深度学习",
        "LLM", "GPT", "chatgpt", "copilot", "agent", "prompt", "提示词",
        "神经网络", "自然语言处理", "计算机视觉", "语音识别", "推荐系统",
        "文心", "通义", "kimi", "豆包", "混元", "星火", "claude",
        "模型", "数据科学", "RLHF", "SFT", "对齐", "生成式",
    ]
    is_ai_related = any(kw.lower() in title_lower or kw.lower() in desc_lower for kw in ai_keywords)

    if not is_ai_related:
        return ("其他", "")

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
        return ("商业化/增长", "解决方案架构师")
    if "数据标注" in title_lower or "训练师" in title_lower or "语料" in title_lower:
        subtype = _extract_subtype(title, "训练/标注")
        return ("训练/标注", subtype)
    if "提示词" in title_lower or "prompt" in title_lower:
        return ("提示词工程", "提示词工程师")

    # Generic AI-related that didn't match any specific type
    return ("其他", "")


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
        if "增长" in title_lower:
            return "AI增长"
    elif job_type == "训练/标注":
        if "训练师" in title_lower:
            return "AI训练师"
        if "标注" in title_lower:
            return "数据标注"
    elif job_type == "提示词工程":
        return "提示词工程师"
    return ""
