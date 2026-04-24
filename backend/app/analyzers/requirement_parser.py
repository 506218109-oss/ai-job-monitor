import re


def parse_experience(text: str) -> str:
    """
    Normalize Chinese experience requirements.
    "3-5年经验" -> "3-5年"
    "经验不限" -> "不限"
    "应届生" -> "应届"
    """
    if not text:
        return "不限"

    t = text.strip()

    if any(w in t for w in ["不限", "经验不限", "无经验"]):
        return "不限"

    if any(w in t for w in ["应届", "应届生", "毕业生", "校招"]):
        return "应届"

    # "3-5年经验" -> "3-5年"
    match = re.search(r'(\d+-\d+)\s*年', t)
    if match:
        return match.group(1) + "年"

    # "1年以上" -> "1年+"
    match = re.search(r'(\d+)\s*年\s*以[上内]', t)
    if match:
        return match.group(1) + "年+"

    # "3年以上" or just "3年"
    match = re.search(r'(\d+)\s*年', t)
    if match:
        return match.group(1) + "年"

    return t if len(t) < 20 else "不限"


def parse_education(text: str) -> str:
    """
    Normalize Chinese education requirements.
    """
    if not text:
        return "不限"

    t = text.strip()

    if any(w in t for w in ["不限", "学历不限"]):
        return "不限"

    if "博士" in t:
        return "博士"
    if "硕士" in t or "研究生" in t:
        return "硕士"
    if "本科" in t:
        return "本科"
    if "大专" in t or "专科" in t:
        return "大专"
    if "高中" in t:
        return "高中"

    return t if len(t) < 20 else "不限"
