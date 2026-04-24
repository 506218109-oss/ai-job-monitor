import re


def parse_salary(salary_str: str) -> tuple:
    """
    Parse Chinese salary strings into (min_K, max_K, months).
    Handles: "15K-25K", "15-25K·15薪", "面议", "20K-40K·16薪", "8千-1.2万", etc.

    Returns (None, None, 12) if unparseable.
    """
    if not salary_str or salary_str in ("面议", "薪资面议", "薪资范围"):
        return (None, None, 12)

    s = salary_str.strip().replace(" ", "").replace(",", "")

    months = 12
    # Extract salary months: "·15薪", "*15薪", "x15"
    month_match = re.search(r'[·\*xX](\d+)\s*薪', s)
    if month_match:
        months = int(month_match.group(1))
        s = s[:month_match.start()] + s[month_match.end():]

    # Normalize: "万" -> convert to K, "千" -> convert to K
    # "1.5万-2.5万" -> "15K-25K"
    if "万" in s:
        s = re.sub(r'(\d+\.?\d*)\s*万', lambda m: str(int(float(m.group(1)) * 10)) + "K", s)
    if "千" in s:
        s = re.sub(r'(\d+\.?\d*)\s*千', lambda m: str(int(float(m.group(1)))) + "K", s)

    # Pattern: "15K-25K" or "15-25K" or "15000-25000"
    match = re.search(r'(\d+\.?\d*)\s*[Kk]?\s*[-~—至到]\s*(\d+\.?\d*)\s*[Kk]?', s)
    if match:
        min_val = float(match.group(1))
        max_val = float(match.group(2))
        # If values are > 100, they're likely raw numbers (15000), not K
        if min_val > 100:
            min_val = int(min_val / 1000)
        if max_val > 100:
            max_val = int(max_val / 1000)
        return (int(min_val), int(max_val), months)

    # Single value: "15K以上" or "25K"
    match = re.search(r'(\d+\.?\d*)\s*[Kk]', s)
    if match:
        val = int(float(match.group(1)))
        return (val, int(val * 1.5), months)

    return (None, None, months)
