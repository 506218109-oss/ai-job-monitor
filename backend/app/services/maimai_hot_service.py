import re
import time
from datetime import date, datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

import httpx

from app.config import settings


CN_TZ = ZoneInfo("Asia/Shanghai")
MAIMAI_CACHE_TTL_SECONDS = 30 * 60
SERPAPI_SEARCH_URL = "https://serpapi.com/search.json"
MAX_TOPICS = 8

_cache = {
    "date": None,
    "fetched_at": 0.0,
    "data": None,
}


def get_maimai_hot_topics(target_date: Optional[date] = None, force_refresh: bool = False) -> dict:
    today = target_date or datetime.now(CN_TZ).date()
    now = time.time()
    if (
        not force_refresh
        and _cache["date"] == today
        and _cache["data"] is not None
        and now - _cache["fetched_at"] < MAIMAI_CACHE_TTL_SECONDS
    ):
        return _cache["data"]

    if not settings.SERPAPI_API_KEY:
        data = _empty_response(today, "needs_config", "未配置 SerpApi，暂无法读取脉脉公开搜索摘要。")
        _cache.update({"date": today, "fetched_at": now, "data": data})
        return data

    errors = []
    seen: set[tuple[str, str]] = set()
    topics = _search_public_maimai("d", errors, MAX_TOPICS, seen)
    if len(topics) < MAX_TOPICS:
        topics.extend(_search_public_maimai("d", errors, MAX_TOPICS - len(topics), seen, query_variant="companies"))
    supplemented = False
    if len(topics) < MAX_TOPICS:
        supplemented = bool(topics)
        topics.extend(_search_public_maimai("w", errors, MAX_TOPICS - len(topics), seen))
    if len(topics) < MAX_TOPICS:
        supplemented = bool(topics)
        topics.extend(_search_public_maimai("w", errors, MAX_TOPICS - len(topics), seen, query_variant="companies"))
    is_fallback = not topics or (not any(item["window"] == "day" for item in topics) and bool(topics))

    data = {
        "date": today.isoformat(),
        "start_date": (today - timedelta(days=6)).isoformat(),
        "end_date": today.isoformat(),
        "source": "脉脉公开搜索摘要",
        "source_url": "https://maimai.cn/",
        "scope_label": "当天 + 近 7 日补充" if supplemented and topics else "近 7 日回退" if is_fallback and topics else "北京时间当日",
        "is_fallback": is_fallback and bool(topics),
        "is_supplemented": supplemented and bool(topics),
        "items_found": len(topics),
        "topics": topics[:MAX_TOPICS],
        "policy": "不登录脉脉、不使用 Cookie、不绕过风控；仅展示搜索引擎可见的公开摘要。",
        "source_errors": errors[:3],
        "generated_at": datetime.now(CN_TZ).isoformat(),
    }
    if not topics:
        data["empty_message"] = "今天暂无可公开读取的脉脉热点摘要。"
    _cache.update({"date": today, "fetched_at": now, "data": data})
    return data


def _empty_response(today: date, status: str, message: str) -> dict:
    return {
        "date": today.isoformat(),
        "start_date": (today - timedelta(days=6)).isoformat(),
        "end_date": today.isoformat(),
        "source": "脉脉公开搜索摘要",
        "source_url": "https://maimai.cn/",
        "scope_label": "北京时间当日",
        "is_fallback": False,
        "items_found": 0,
        "topics": [],
        "status": status,
        "empty_message": message,
        "policy": "不登录脉脉、不使用 Cookie、不绕过风控；仅展示搜索引擎可见的公开摘要。",
        "source_errors": [],
        "generated_at": datetime.now(CN_TZ).isoformat(),
    }


def _search_public_maimai(
    window: str,
    errors: list[dict],
    limit: int,
    seen: set[tuple[str, str]],
    query_variant: str = "ai",
) -> list[dict]:
    if limit <= 0:
        return []
    if query_variant == "companies":
        query = 'site:maimai.cn ("字节跳动" OR "腾讯" OR "阿里" OR "美团" OR "小红书") ("AI" OR "大模型" OR "产品" OR "运营" OR "招聘")'
    else:
        query = (
            'site:maimai.cn '
            '("AI" OR "大模型" OR "AIGC" OR "Agent" OR "产品经理" OR "AI运营" OR "商业化") '
            '("脉脉" OR "职场")'
        )
    try:
        response = httpx.get(
            SERPAPI_SEARCH_URL,
            params={
                "engine": "google",
                "q": query,
                "hl": "zh-cn",
                "gl": "cn",
                "num": 10,
                "tbs": f"qdr:{window}",
                "api_key": settings.SERPAPI_API_KEY,
            },
            headers={"User-Agent": "AIJobMonitor/1.0 (+public-search-summary)"},
            timeout=6.0,
        )
        response.raise_for_status()
        data = response.json()
    except Exception as exc:
        errors.append({"source": "SerpApi Google Search", "error": str(exc)[:160]})
        return []

    results = data.get("organic_results") or []
    topics = []
    for item in results:
        link = item.get("link") or ""
        title = _clean(item.get("title") or "")
        snippet = _clean_snippet(item.get("snippet") or "")
        if "maimai.cn/article/detail" not in link or not title:
            continue
        key = (title, link.split("?")[0])
        if key in seen:
            continue
        seen.add(key)
        topics.append({
            "title": title,
            "snippet": _shorten(_remove_title_tail(snippet, title), 92),
            "url": link,
            "date": item.get("date") or "",
            "source": "脉脉",
            "window": "day" if window == "d" else "week",
        })
        if len(topics) >= limit:
            break
    return topics


def _clean(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def _clean_snippet(value: str) -> str:
    text = _clean(value)
    text = re.sub(r"声明：本文内容由脉脉用户.*$", "", text).strip()
    text = re.sub(r"脉脉不拥有其著作权.*$", "", text).strip()
    text = re.sub(r"\s*END\.?\s*阅读\s*\d+.*$", "", text, flags=re.IGNORECASE).strip()
    text = re.sub(r"\s*END\.?\s*$", "", text, flags=re.IGNORECASE).strip()
    return text


def _shorten(value: str, limit: int) -> str:
    text = _clean(value)
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "..."


def _remove_title_tail(snippet: str, title: str) -> str:
    text = _clean(snippet)
    if not text or not title:
        return text
    return re.sub(rf"\s*{re.escape(title)}\s*脉脉\.?$", "", text).strip()
