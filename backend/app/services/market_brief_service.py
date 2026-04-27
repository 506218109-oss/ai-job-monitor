import html
import re
import time
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Optional
from zoneinfo import ZoneInfo

import httpx
from bs4 import BeautifulSoup


CN_TZ = ZoneInfo("Asia/Shanghai")
BRIEF_CACHE_TTL_SECONDS = 30 * 60


BRIEF_SOURCES = [
    {
        "name": "Latent Space",
        "type": "英文播客/社区",
        "feed_url": "https://www.latent.space/feed",
        "language": "英文",
    },
    {
        "name": "Ben Thompson",
        "type": "英文分析师",
        "feed_url": "https://stratechery.com/feed/",
        "language": "英文",
    },
    {
        "name": "a16z AI",
        "type": "英文机构观点",
        "feed_url": "",
        "language": "英文",
    },
    {
        "name": "Anthropic",
        "type": "海外 AI 公司",
        "feed_url": "",
        "language": "英文",
    },
    {
        "name": "Google AI",
        "type": "海外科技公司",
        "feed_url": "https://blog.google/technology/ai/rss/",
        "language": "英文",
    },
    {
        "name": "Microsoft AI",
        "type": "海外科技公司",
        "feed_url": "https://blogs.microsoft.com/ai/feed/",
        "language": "英文",
    },
    {
        "name": "机器之心",
        "type": "行业媒体",
        "feed_url": "",
        "language": "中文",
    },
    {
        "name": "宝玉",
        "type": "KOL",
        "feed_url": "https://baoyu.io/feed.xml",
        "language": "中文",
    },
]


TREND_RULES = [
    {
        "topic": "Agent 产品化",
        "keywords": [
            "agent", "agents", "agentic", "workflow", "workflows", "tool use",
            "computer use", "mcp", "智能体", "工作流", "工具调用",
        ],
        "conclusion": "Agent 正从演示走向可执行工作流，产品岗位会更看重任务拆解、工具调用、权限边界和失败兜底设计。",
    },
    {
        "topic": "企业落地与商业化",
        "keywords": [
            "enterprise", "business", "revenue", "roi", "customer", "pricing",
            "adoption", "商业化", "企业", "客户", "收入", "成本", "效率",
        ],
        "conclusion": "AI 讨论正在从模型能力转向业务结果，能证明效率、成本、转化或收入变化的项目经历会更有说服力。",
    },
    {
        "topic": "评测、安全与可信",
        "keywords": [
            "eval", "evaluation", "benchmark", "safety", "alignment", "risk",
            "policy", "trust", "评测", "评估", "安全", "对齐", "风险", "合规",
        ],
        "conclusion": "AI 应用进入生产环境后，评测、安全和反馈闭环会成为产品与运营岗位的基础能力。",
    },
    {
        "topic": "多模态与内容生产",
        "keywords": [
            "multimodal", "video", "image", "audio", "voice", "creator",
            "content", "多模态", "视频", "图像", "语音", "内容",
        ],
        "conclusion": "多模态内容生产仍是应用创新的高频场景，相关岗位会更需要场景判断、质量标准和内容运营能力。",
    },
    {
        "topic": "模型与基础设施",
        "keywords": [
            "model", "llm", "inference", "open source", "open-source", "reasoning",
            "training", "模型", "大模型", "推理", "开源", "训练",
        ],
        "conclusion": "模型能力和推理成本仍在快速变化，产品判断需要同时理解能力边界、成本结构和可用性约束。",
    },
]


_cache = {
    "date": None,
    "fetched_at": 0.0,
    "data": None,
}


@dataclass
class BriefItem:
    source_name: str
    source_type: str
    title: str
    url: str
    published_date: date
    summary: str


def get_daily_market_brief(target_date: Optional[date] = None, force_refresh: bool = False) -> dict:
    today = target_date or datetime.now(CN_TZ).date()
    now = time.time()
    if (
        not force_refresh
        and _cache["date"] == today
        and _cache["data"] is not None
        and now - _cache["fetched_at"] < BRIEF_CACHE_TTL_SECONDS
    ):
        return _cache["data"]

    start_date = today - timedelta(days=6)
    all_recent_items, errors, sources_checked = _fetch_window_items(start_date, today)
    today_items = [item for item in all_recent_items if item.published_date == today]
    is_fallback = not today_items and bool(all_recent_items)
    items = today_items if today_items else all_recent_items
    briefs = _build_briefs(items)
    policy = "每日优先展示北京时间当天公开内容。"
    if is_fallback:
        policy = "当天没有命中公开内容，以下为近 7 日内容，已按来源和发布时间标注。"
    elif not items:
        policy = "每日优先展示北京时间当天公开内容；当天和近 7 日均无内容则不生成简报。"
    data = {
        "date": today.isoformat(),
        "start_date": start_date.isoformat(),
        "end_date": today.isoformat(),
        "window_days": 7 if is_fallback else 1,
        "is_fallback": is_fallback,
        "timezone": "Asia/Shanghai",
        "scope_label": "近 7 日回退" if is_fallback else "北京时间当日",
        "policy": policy,
        "briefs": briefs,
        "items_found": len(items),
        "today_items_found": len(today_items),
        "recent_items_found": len(all_recent_items),
        "sources_checked": sources_checked,
        "source_errors": errors[:5],
        "sources": [
            {
                "name": source["name"],
                "type": source["type"],
                "language": source["language"],
                "has_feed": bool(source.get("feed_url")),
            }
            for source in BRIEF_SOURCES
        ],
        "generated_at": datetime.now(CN_TZ).isoformat(),
    }
    _cache.update({"date": today, "fetched_at": now, "data": data})
    return data


def _fetch_window_items(start_date: date, end_date: date) -> tuple[list[BriefItem], list[dict], int]:
    items: list[BriefItem] = []
    errors: list[dict] = []
    checkable_sources = [source for source in BRIEF_SOURCES if source.get("feed_url")]
    with ThreadPoolExecutor(max_workers=min(8, len(checkable_sources))) as pool:
        futures = {
            pool.submit(_fetch_source_items, source, start_date, end_date): source
            for source in checkable_sources
        }
        for future in as_completed(futures):
            source = futures[future]
            try:
                items.extend(future.result())
            except Exception as exc:
                errors.append({"source": source["name"], "error": str(exc)[:160]})
    items.sort(key=lambda item: (item.published_date, item.source_name, item.title), reverse=True)
    return items, errors, len(checkable_sources)


def _fetch_source_items(source: dict, start_date: date, end_date: date) -> list[BriefItem]:
    headers = {
        "User-Agent": "AIJobMonitor/1.0 (+https://localhost)",
        "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, */*",
    }
    response = httpx.get(source["feed_url"], headers=headers, follow_redirects=True, timeout=4.0)
    response.raise_for_status()
    return _parse_feed(source, response.text, start_date, end_date)


def _parse_feed(source: dict, xml_text: str, start_date: date, end_date: date) -> list[BriefItem]:
    root = ET.fromstring(xml_text.encode("utf-8"))
    entries = _rss_entries(root) or _atom_entries(root)
    items = []
    for entry in entries:
        published = _parse_date(entry.get("published") or entry.get("updated") or "")
        if not published:
            continue
        published_date = published.astimezone(CN_TZ).date()
        if not start_date <= published_date <= end_date:
            continue
        title = _clean_text(entry.get("title", ""))
        if not title:
            continue
        items.append(
            BriefItem(
                source_name=source["name"],
                source_type=source["type"],
                title=title,
                url=entry.get("link", ""),
                published_date=published_date,
                summary=_clean_text(entry.get("summary", "")),
            )
        )
    return items


def _rss_entries(root: ET.Element) -> list[dict]:
    items = root.findall("./channel/item")
    entries = []
    for item in items:
        entries.append({
            "title": _child_text(item, "title"),
            "link": _child_text(item, "link"),
            "published": _child_text(item, "pubDate") or _child_text(item, "published"),
            "summary": _child_text(item, "description"),
        })
    return entries


def _atom_entries(root: ET.Element) -> list[dict]:
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    entries = []
    for entry in root.findall(".//atom:entry", ns):
        link = ""
        link_el = entry.find("atom:link", ns)
        if link_el is not None:
            link = link_el.attrib.get("href", "")
        entries.append({
            "title": _child_text(entry, "atom:title", ns),
            "link": link,
            "published": _child_text(entry, "atom:published", ns),
            "updated": _child_text(entry, "atom:updated", ns),
            "summary": _child_text(entry, "atom:summary", ns) or _child_text(entry, "atom:content", ns),
        })
    return entries


def _child_text(parent: ET.Element, path: str, ns: Optional[dict] = None) -> str:
    child = parent.find(path, ns or {})
    if child is None or child.text is None:
        return ""
    return child.text.strip()


def _parse_date(value: str) -> Optional[datetime]:
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    except Exception:
        pass
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    except Exception:
        return None


def _clean_text(value: str) -> str:
    text = BeautifulSoup(html.unescape(value or ""), "html.parser").get_text(" ", strip=True)
    return re.sub(r"\s+", " ", text).strip()


def _build_briefs(items: list[BriefItem]) -> list[dict]:
    grouped = []
    for rule in TREND_RULES:
        matched = [item for item in items if _matches_rule(item, rule)]
        if not matched:
            continue
        source_names = _unique([item.source_name for item in matched])[:3]
        grouped.append({
            "topic": rule["topic"],
            "statement": f"{'、'.join(source_names)}认为，{rule['conclusion']}",
            "evidence": [
                {
                    "source": item.source_name,
                    "title": item.title,
                    "url": item.url,
                    "published_date": item.published_date.isoformat(),
                }
                for item in matched[:4]
            ],
        })

    if grouped:
        return grouped[:4]

    fallback = []
    for item in items[:4]:
        fallback.append({
            "topic": "今日动态",
            "statement": f"{item.source_name}关注「{item.title}」，可作为今日 AI 行业动态观察。",
            "evidence": [{
                "source": item.source_name,
                "title": item.title,
                "url": item.url,
                "published_date": item.published_date.isoformat(),
            }],
        })
    return fallback



def _matches_rule(item: BriefItem, rule: dict) -> bool:
    text = f"{item.title} {item.summary}".lower()
    return any(keyword.lower() in text for keyword in rule["keywords"])


def _unique(values: list[str]) -> list[str]:
    seen = set()
    result = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result
