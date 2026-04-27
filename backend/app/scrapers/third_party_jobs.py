import hashlib
import json
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Optional

import httpx

from app.analyzers.job_classifier import classify_job
from app.analyzers.requirement_parser import parse_education, parse_experience
from app.config import settings
from app.scrapers.base import AbstractScraper, JobData
from app.scrapers.official_jobs import _clean_html, _translate_location, _translate_overseas_title


SERPAPI_GOOGLE_JOBS_URL = "https://serpapi.com/search.json"
ADZUNA_SEARCH_URL = "https://api.adzuna.com/v1/api/jobs/{country}/search/{page}"


@dataclass(frozen=True)
class TargetCompany:
    id: str
    display_name: str
    search_name: str
    region: str
    aliases: tuple[str, ...]


@dataclass(frozen=True)
class SearchProfile:
    id: str
    label: str
    query: str
    keywords: tuple[str, ...]


TARGET_COMPANIES = [
    TargetCompany("meta", "Meta", "Meta", "全球", ("meta", "facebook")),
    TargetCompany("google", "Google", "Google", "全球", ("google", "google deepmind", "deepmind")),
    TargetCompany("anthropic", "Anthropic", "Anthropic", "全球", ("anthropic",)),
    TargetCompany("microsoft", "Microsoft", "Microsoft", "全球", ("microsoft",)),
    TargetCompany("xiaohongshu", "小红书", "Xiaohongshu", "中国", ("小红书", "xiaohongshu", "rednote")),
    TargetCompany("bilibili", "哔哩哔哩", "Bilibili", "中国", ("哔哩哔哩", "bilibili")),
    TargetCompany("kuaishou", "快手", "Kuaishou", "中国", ("快手", "kuaishou")),
    TargetCompany("meituan", "美团", "Meituan", "中国", ("美团", "meituan")),
    TargetCompany("alibaba", "阿里巴巴", "Alibaba", "中国", ("阿里巴巴", "alibaba", "aliyun", "aliexpress")),
    TargetCompany("jd", "京东", "JD.com", "中国", ("京东", "jd.com", "jingdong")),
]


BASE_SEARCH_PROFILES = [
    SearchProfile(
        id="product",
        label="产品",
        query="AI product manager OR LLM product manager jobs",
        keywords=("产品", "product"),
    ),
    SearchProfile(
        id="operations",
        label="运营/增长/商业",
        query="AI operations OR growth OR go-to-market jobs",
        keywords=("运营", "增长", "商业", "operations", "growth", "sales", "marketing"),
    ),
    SearchProfile(
        id="data",
        label="数据",
        query="AI data product manager OR analytics jobs",
        keywords=("数据", "data", "analytics"),
    ),
    SearchProfile(
        id="evaluation",
        label="训练/评测/提示词",
        query="AI evaluation OR prompt engineering OR human data jobs",
        keywords=("训练", "标注", "提示词", "evaluation", "prompt", "human data"),
    ),
]


def get_third_party_source_statuses() -> list[dict]:
    return [
        {
            "id": "third_party_serpapi",
            "company": "SerpApi Google Jobs",
            "region": "全球",
            "status": "active" if _serpapi_enabled() else "needs_config",
            "career_url": "https://serpapi.com/google-jobs-api",
            "note": "第三方 Google Jobs API；请求发送到 SerpApi，不直接访问目标公司招聘官网。配置 SERPAPI_API_KEY 或 AIJM_SERPAPI_API_KEY 后启用。",
        },
        {
            "id": "third_party_adzuna",
            "company": "Adzuna",
            "region": "全球",
            "status": "active" if _adzuna_enabled() else "needs_config",
            "career_url": "https://developer.adzuna.com/overview",
            "note": "第三方招聘聚合 API；配置 ADZUNA_APP_ID/ADZUNA_APP_KEY 或 AIJM_ 前缀环境变量后启用。",
        },
    ]


class ThirdPartyJobsScraper(AbstractScraper):
    """Third-party job aggregator scraper. It never visits target-company apply pages."""

    def __init__(self, search_keywords: Optional[list[str]] = None):
        self.client: Optional[httpx.AsyncClient] = None
        self.search_keywords = search_keywords or settings.SEARCH_KEYWORDS
        self.source_statuses = get_third_party_source_statuses()
        self.platforms_to_mark_stale = [
            platform
            for platform, enabled in [
                ("third_party_serpapi", _serpapi_enabled()),
                ("third_party_adzuna", _adzuna_enabled()),
            ]
            if enabled
        ]
        self._has_run = False

    async def _ensure_client(self):
        if self.client is None:
            self.client = httpx.AsyncClient(
                headers={
                    "User-Agent": "AIJobMonitor/1.0 (+third-party-aggregators)",
                    "Accept": "application/json, text/plain, */*",
                },
                timeout=20.0,
                follow_redirects=True,
            )

    async def search(self, keyword: str, city: str = "", max_pages: int = 3) -> list[JobData]:
        if self._has_run:
            return []
        self._has_run = True
        await self._ensure_client()

        jobs: list[JobData] = []
        queries = _build_queries(self.search_keywords, settings.THIRD_PARTY_MAX_QUERIES_PER_RUN)
        if _serpapi_enabled():
            jobs.extend(await self._search_serpapi(queries))
        if _adzuna_enabled():
            jobs.extend(await self._search_adzuna(queries))
        return _dedupe_jobs(jobs)

    async def get_detail(self, job: JobData) -> JobData:
        return job

    async def close(self):
        if self.client:
            await self.client.aclose()
            self.client = None

    async def _search_serpapi(self, queries: list[tuple[TargetCompany, SearchProfile, str]]) -> list[JobData]:
        jobs: list[JobData] = []
        for company, profile, query in queries:
            try:
                response = await self.client.get(
                    SERPAPI_GOOGLE_JOBS_URL,
                    params={
                        "engine": "google_jobs",
                        "q": query,
                        "hl": "en",
                        "gl": "us",
                        "api_key": settings.SERPAPI_API_KEY,
                    },
                )
                data = response.json()
                for item in data.get("jobs_results") or []:
                    job = _parse_serpapi_job(item, company, profile, query)
                    if job:
                        jobs.append(job)
            except Exception as exc:
                print(f"  [ThirdPartyJobs] SerpApi skipped '{query}': {exc}")
        return jobs

    async def _search_adzuna(self, queries: list[tuple[TargetCompany, SearchProfile, str]]) -> list[JobData]:
        jobs: list[JobData] = []
        countries = _adzuna_countries()
        for country in countries:
            for company, profile, query in queries:
                try:
                    response = await self.client.get(
                        ADZUNA_SEARCH_URL.format(country=country, page=1),
                        params={
                            "app_id": settings.ADZUNA_APP_ID,
                            "app_key": settings.ADZUNA_APP_KEY,
                            "results_per_page": 10,
                            "what": query,
                            "content-type": "application/json",
                        },
                    )
                    data = response.json()
                    for item in data.get("results") or []:
                        job = _parse_adzuna_job(item, company, profile, query, country)
                        if job:
                            jobs.append(job)
                except Exception as exc:
                    print(f"  [ThirdPartyJobs] Adzuna skipped '{country}/{query}': {exc}")
        return jobs


def _serpapi_enabled() -> bool:
    return bool(settings.SERPAPI_API_KEY)


def _adzuna_enabled() -> bool:
    return bool(settings.ADZUNA_APP_ID and settings.ADZUNA_APP_KEY)


def _adzuna_countries() -> list[str]:
    return [
        item.strip().lower()
        for item in settings.THIRD_PARTY_ADZUNA_COUNTRIES.split(",")
        if item.strip()
    ]


def _build_queries(search_keywords: list[str], limit: int) -> list[tuple[TargetCompany, SearchProfile, str]]:
    profiles = _profiles_for_keywords(search_keywords)
    queries: list[tuple[TargetCompany, SearchProfile, str]] = []
    for profile in profiles:
        for company in TARGET_COMPANIES:
            query = f"{company.search_name} {profile.query}"
            queries.append((company, profile, query))
    return queries[:max(1, limit)]


def _profiles_for_keywords(search_keywords: list[str]) -> list[SearchProfile]:
    text = " ".join(search_keywords or []).lower()
    profiles = [
        profile
        for profile in BASE_SEARCH_PROFILES
        if any(keyword.lower() in text for keyword in profile.keywords)
    ]
    return profiles or BASE_SEARCH_PROFILES[:2]


def _parse_serpapi_job(
    item: dict,
    expected_company: TargetCompany,
    profile: SearchProfile,
    query: str,
) -> Optional[JobData]:
    company = (item.get("company_name") or "").strip()
    target = _match_target_company(company)
    if not target or target.id != expected_company.id:
        return None

    raw_title = item.get("title") or ""
    if not raw_title:
        return None
    title = _translate_overseas_title(raw_title)
    location = _translate_location(item.get("location") or "全球")
    description = _clean_html(item.get("description") or "")
    posting_date = _date_from_posted_at((item.get("detected_extensions") or {}).get("posted_at") or "")
    links = _format_serpapi_links(item.get("apply_options") or item.get("related_links") or [])
    description_text = (
        f"第三方来源：SerpApi Google Jobs\n"
        f"目标公司：{target.display_name}\n"
        f"搜索口径：{profile.label} / {query}\n"
        f"英文原始标题：{raw_title}\n"
        f"{links}\n\n"
        f"{description}"
    ).strip()
    job_type, job_subtype = classify_job(title, description_text)
    return JobData(
        platform="third_party_serpapi",
        platform_job_id=_stable_id("serpapi", item.get("job_id") or item.get("share_link") or json.dumps(item, sort_keys=True)),
        title=title,
        company_name=target.display_name,
        company_size=None,
        company_industry="AI/互联网",
        location_city=location,
        location_district=None,
        salary_min=None,
        salary_max=None,
        salary_months=12,
        job_type=job_type,
        job_subtype=job_subtype,
        experience_required=parse_experience(description_text),
        education_required=parse_education(description_text),
        description_text=description_text,
        benefits=None,
        posting_date=posting_date,
        raw_json=json.dumps(_with_meta(item, profile=profile.id, query=query), ensure_ascii=False),
    )


def _parse_adzuna_job(
    item: dict,
    expected_company: TargetCompany,
    profile: SearchProfile,
    query: str,
    country: str,
) -> Optional[JobData]:
    company = ((item.get("company") or {}).get("display_name") or "").strip()
    target = _match_target_company(company)
    if not target or target.id != expected_company.id:
        return None

    raw_title = item.get("title") or ""
    if not raw_title:
        return None
    title = _translate_overseas_title(raw_title)
    location = _translate_location(((item.get("location") or {}).get("display_name") or country.upper()))
    description = _clean_html(item.get("description") or "")
    posting_date = _date_from_iso(item.get("created") or "")
    description_text = (
        f"第三方来源：Adzuna\n"
        f"目标公司：{target.display_name}\n"
        f"搜索口径：{profile.label} / {query}\n"
        f"英文原始标题：{raw_title}\n"
        f"聚合页链接：{item.get('redirect_url') or ''}\n\n"
        f"{description}"
    ).strip()
    job_type, job_subtype = classify_job(title, description_text)
    return JobData(
        platform="third_party_adzuna",
        platform_job_id=_stable_id("adzuna", item.get("id") or json.dumps(item, sort_keys=True)),
        title=title,
        company_name=target.display_name,
        company_size=None,
        company_industry=(item.get("category") or {}).get("label") or "AI/互联网",
        location_city=location,
        location_district=None,
        salary_min=_as_int(item.get("salary_min")),
        salary_max=_as_int(item.get("salary_max")),
        salary_months=12,
        job_type=job_type,
        job_subtype=job_subtype,
        experience_required=parse_experience(description_text),
        education_required=parse_education(description_text),
        description_text=description_text,
        benefits=None,
        posting_date=posting_date,
        raw_json=json.dumps(_with_meta(item, profile=profile.id, query=query, country=country), ensure_ascii=False),
    )


def _match_target_company(value: str) -> Optional[TargetCompany]:
    haystack = (value or "").lower()
    if not haystack:
        return None
    for company in TARGET_COMPANIES:
        if any(alias.lower() in haystack for alias in company.aliases):
            return company
    return None


def _format_serpapi_links(links: list[dict]) -> str:
    if not links:
        return "聚合页链接："
    lines = []
    for link in links[:3]:
        title = link.get("title") or link.get("source") or "链接"
        url = link.get("link") or ""
        if url:
            lines.append(f"{title}：{url}")
    return "聚合页链接：" + "；".join(lines)


def _date_from_posted_at(value: str) -> Optional[date]:
    text = (value or "").strip().lower()
    if not text:
        return None
    number_match = re.search(r"(\d+)", text)
    number = int(number_match.group(1)) if number_match else 1
    today = datetime.now(timezone.utc).date()
    if "hour" in text or "minute" in text or "today" in text:
        return today
    if "day" in text:
        return today - timedelta(days=number)
    if "week" in text:
        return today - timedelta(weeks=number)
    if "month" in text:
        return today - timedelta(days=number * 30)
    return None


def _date_from_iso(value: str) -> Optional[date]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except Exception:
        return None


def _stable_id(provider: str, value: object) -> str:
    text = f"{provider}:{value}"
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:32]


def _dedupe_jobs(jobs: list[JobData]) -> list[JobData]:
    seen = set()
    result = []
    for job in jobs:
        key = (job.platform, job.platform_job_id)
        if key in seen:
            continue
        seen.add(key)
        result.append(job)
    return result


def _as_int(value) -> Optional[int]:
    try:
        if value is None:
            return None
        return int(float(value))
    except Exception:
        return None


def _with_meta(item: dict, **meta) -> dict:
    data = dict(item)
    data["_third_party_meta"] = meta
    return data
