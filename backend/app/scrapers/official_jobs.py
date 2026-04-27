import html
import json
import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional

import httpx
from bs4 import BeautifulSoup

from app.analyzers.job_classifier import classify_job
from app.analyzers.requirement_parser import parse_education, parse_experience
from app.scrapers.base import AbstractScraper, JobData


MEITUAN_JOB_LIST_URL = "https://zhaopin.meituan.com/api/official/job/getJobList"
MEITUAN_JOB_DETAIL_URL = "https://zhaopin.meituan.com/api/official/job/getJobDetail"
ANTHROPIC_GREENHOUSE_URL = "https://boards-api.greenhouse.io/v1/boards/anthropic/jobs"


@dataclass(frozen=True)
class OfficialSource:
    id: str
    company_name: str
    company_name_cn: str
    region: str
    status: str
    career_url: str
    note: str


OFFICIAL_SOURCES = [
    OfficialSource(
        id="official_meituan",
        company_name="Meituan",
        company_name_cn="美团",
        region="中国",
        status="manual",
        career_url="https://zhaopin.meituan.com/web/social",
        note="公开招聘官网 JSON 接口；为降低对后续官网投递链路的影响，默认调度不触发，仅保留手动备选。",
    ),
    OfficialSource(
        id="official_anthropic",
        company_name="Anthropic",
        company_name_cn="Anthropic",
        region="全球",
        status="manual",
        career_url="https://www.anthropic.com/careers/jobs",
        note="公开 Greenhouse job board API；默认调度优先第三方聚合源，此源仅保留手动备选。",
    ),
    OfficialSource(
        id="official_xiaohongshu",
        company_name="Xiaohongshu",
        company_name_cn="小红书",
        region="中国",
        status="skipped",
        career_url="https://job.xiaohongshu.com",
        note="招聘站为动态前端，当前未确认稳定公开岗位 JSON；跳过，避免硬抓。",
    ),
    OfficialSource(
        id="official_bilibili",
        company_name="Bilibili",
        company_name_cn="哔哩哔哩",
        region="中国",
        status="skipped",
        career_url="https://jobs.bilibili.com/social/positions",
        note="岗位接口返回 ajSessionId 要求，按不稳定会话源跳过。",
    ),
    OfficialSource(
        id="official_kuaishou",
        company_name="Kuaishou",
        company_name_cn="快手",
        region="中国",
        status="skipped",
        career_url="https://zhaopin.kuaishou.cn/recruit/e/#/official/social",
        note="公开端点当前返回 fail，未确认稳定匿名查询参数；跳过。",
    ),
    OfficialSource(
        id="official_alibaba",
        company_name="Alibaba",
        company_name_cn="阿里巴巴",
        region="中国",
        status="skipped",
        career_url="https://talent.alibaba.com",
        note="待确认稳定公开接口；未接入登录、验证码、投递或候选人接口。",
    ),
    OfficialSource(
        id="official_jd",
        company_name="JD",
        company_name_cn="京东",
        region="中国",
        status="skipped",
        career_url="https://zhaopin.jd.com",
        note="待确认稳定公开接口；未接入登录、验证码、投递或候选人接口。",
    ),
    OfficialSource(
        id="official_meta",
        company_name="Meta",
        company_name_cn="Meta",
        region="全球",
        status="skipped",
        career_url="https://www.metacareers.com/jobs",
        note="动态站点未确认稳定匿名 JSON；跳过。",
    ),
    OfficialSource(
        id="official_google",
        company_name="Google",
        company_name_cn="Google",
        region="全球",
        status="skipped",
        career_url="https://www.google.com/about/careers/applications/jobs/results",
        note="动态页面未确认稳定匿名 JSON；跳过。",
    ),
    OfficialSource(
        id="official_microsoft",
        company_name="Microsoft",
        company_name_cn="Microsoft",
        region="全球",
        status="skipped",
        career_url="https://apply.careers.microsoft.com/careers",
        note="Eightfold 页面依赖会话/CSRF，按不稳定会话源跳过。",
    ),
]


OVERSEAS_TERM_MAP = {
    "产品": ["product", "product manager", "product lead"],
    "运营": ["operations", "growth", "program manager", "customer success"],
    "商业": ["account executive", "sales", "go-to-market", "marketing", "partnership"],
    "增长": ["growth", "marketing"],
    "数据": ["data", "analytics"],
    "提示词": ["prompt", "prompt engineering"],
    "训练": ["training", "human data", "rlhf", "evaluation", "eval"],
    "标注": ["human data", "data annotation", "evaluation", "eval"],
    "大模型": ["llm", "large language model", "model", "claude"],
    "人工智能": ["ai", "artificial intelligence", "machine learning"],
    "AI": ["ai", "artificial intelligence", "machine learning", "claude"],
}


GENERIC_OVERSEAS_KEYS = {"AI", "人工智能", "大模型"}


TITLE_TRANSLATIONS = [
    ("Finance Systems Integration Engineer", "财务系统集成工程师"),
    ("Product Marketing Manager", "产品市场经理"),
    ("Technical Program Manager", "技术项目经理"),
    ("Technical Product Manager", "技术产品经理"),
    ("Customer Success Manager", "客户成功经理"),
    ("Solutions Architect", "解决方案架构师"),
    ("Solution Architect", "解决方案架构师"),
    ("Account Executive", "客户经理"),
    ("Product Manager", "产品经理"),
    ("Program Manager", "项目经理"),
    ("Product Lead", "产品负责人"),
    ("Operations", "运营"),
    ("Marketing", "市场"),
    ("Partnerships", "合作伙伴"),
    ("Sales", "销售"),
    ("Research", "研究"),
    ("Engineer", "工程师"),
    ("Academic Medical Centers", "学术医疗中心"),
    ("AI Safety", "AI 安全"),
    ("Machine Learning", "机器学习"),
]


LOCATION_TRANSLATIONS = [
    ("San Francisco, CA", "旧金山"),
    ("New York City, NY", "纽约"),
    ("Seattle, WA", "西雅图"),
    ("London, UK", "伦敦"),
    ("Dublin, Ireland", "都柏林"),
    ("Tokyo, Japan", "东京"),
    ("Remote", "远程"),
    ("United States", "美国"),
]


def get_official_source_statuses() -> list[dict]:
    return [
        {
            "id": source.id,
            "company": source.company_name_cn,
            "region": source.region,
            "status": source.status,
            "career_url": source.career_url,
            "note": source.note,
        }
        for source in OFFICIAL_SOURCES
    ]


class OfficialJobsScraper(AbstractScraper):
    """Public official-career-site scraper for target companies."""

    def __init__(self):
        self.client: Optional[httpx.AsyncClient] = None
        self._anthropic_jobs: Optional[list[dict]] = None
        self.source_statuses = get_official_source_statuses()
        self.platforms_to_mark_stale = ["official_meituan", "official_anthropic"]

    async def _ensure_client(self):
        if self.client is None:
            self.client = httpx.AsyncClient(
                headers={
                    "User-Agent": "AIJobMonitor/1.0 (+public-career-sites)",
                    "Accept": "application/json, text/plain, */*",
                },
                timeout=20.0,
                follow_redirects=True,
            )

    async def search(self, keyword: str, city: str = "", max_pages: int = 3) -> list[JobData]:
        await self._ensure_client()
        jobs: list[JobData] = []
        jobs.extend(await self._search_meituan(keyword, max_pages=max_pages))
        jobs.extend(await self._search_anthropic(keyword))
        return jobs

    async def get_detail(self, job: JobData) -> JobData:
        if job.platform != "official_meituan":
            return job
        await self._ensure_client()
        try:
            response = await self.client.post(
                MEITUAN_JOB_DETAIL_URL,
                json={"jobUnionId": job.platform_job_id, "jobShareType": "1"},
            )
            data = response.json()
            if data.get("status") != 1 or not data.get("data"):
                return job
            detail = data["data"]
            job.description_text = _meituan_description(detail)
            job.experience_required = parse_experience(detail.get("workYear") or "")
            job.education_required = parse_education(job.description_text or "")
            job.job_type, job.job_subtype = classify_job(job.title, job.description_text or "")
            job.raw_json = json.dumps(_with_source(detail, "detail"), ensure_ascii=False)
        except Exception as exc:
            print(f"  [OfficialJobs] Meituan detail error for {job.platform_job_id}: {exc}")
        return job

    async def close(self):
        if self.client:
            await self.client.aclose()
            self.client = None

    async def _search_meituan(self, keyword: str, max_pages: int) -> list[JobData]:
        jobs: list[JobData] = []
        page_size = 20
        for page in range(1, max_pages + 1):
            payload = {
                "page": {"pageNo": page, "pageSize": page_size},
                "keywords": keyword,
                "highlightType": "social",
            }
            try:
                response = await self.client.post(MEITUAN_JOB_LIST_URL, json=payload)
                data = response.json()
                if data.get("status") != 1:
                    print(f"  [OfficialJobs] Meituan API skipped page {page}: {data.get('message')}")
                    break
                posts = data.get("data", {}).get("list", [])
                if not posts:
                    break
                for post in posts:
                    job = self._parse_meituan(post)
                    if job:
                        jobs.append(job)
                if len(posts) < page_size:
                    break
            except Exception as exc:
                print(f"  [OfficialJobs] Meituan error on page {page}: {exc}")
                break
        return jobs

    async def _search_anthropic(self, keyword: str) -> list[JobData]:
        try:
            posts = await self._fetch_anthropic_jobs()
        except Exception as exc:
            print(f"  [OfficialJobs] Anthropic error: {exc}")
            return []

        terms = _english_terms_for_keyword(keyword)
        jobs = []
        for post in posts:
            title = post.get("title", "")
            content = _clean_html(post.get("content", ""))
            haystack = f"{title} {content}".lower()
            if terms and not any(term in haystack for term in terms):
                continue
            job = self._parse_anthropic(post)
            if job:
                jobs.append(job)
        return jobs[:50]

    async def _fetch_anthropic_jobs(self) -> list[dict]:
        if self._anthropic_jobs is not None:
            return self._anthropic_jobs
        response = await self.client.get(
            ANTHROPIC_GREENHOUSE_URL,
            params={"content": "true"},
            headers={"Accept": "application/json"},
        )
        data = response.json()
        self._anthropic_jobs = data.get("jobs", [])
        return self._anthropic_jobs

    def _parse_meituan(self, post: dict) -> Optional[JobData]:
        job_id = str(post.get("jobUnionId") or "")
        title = post.get("name") or ""
        if not job_id or not title:
            return None
        description = _meituan_description(post)
        city = _join_names(post.get("cityList") or [])
        department = _join_names(post.get("department") or [])
        posting_date = _date_from_millis(post.get("firstPostTime") or post.get("refreshTime"))
        job_type, job_subtype = classify_job(title, description)
        return JobData(
            platform="official_meituan",
            platform_job_id=job_id,
            title=title,
            company_name="美团",
            company_size="10000人以上",
            company_industry="互联网",
            location_city=city,
            location_district=None,
            salary_min=None,
            salary_max=None,
            salary_months=12,
            job_type=job_type,
            job_subtype=job_subtype,
            experience_required=parse_experience(post.get("workYear") or ""),
            education_required=parse_education(description),
            description_text=description,
            benefits=post.get("highLight"),
            posting_date=posting_date,
            raw_json=json.dumps(_with_source(post, "list", department=department), ensure_ascii=False),
        )

    def _parse_anthropic(self, post: dict) -> Optional[JobData]:
        job_id = str(post.get("id") or "")
        title = post.get("title") or ""
        if not job_id or not title:
            return None
        translated_title = _translate_overseas_title(title)
        description = _clean_html(post.get("content", ""))
        location = _translate_location((post.get("location") or {}).get("name", "全球"))
        posting_date = _date_from_iso(post.get("first_published") or post.get("updated_at"))
        description = (
            f"英文原始标题：{title}\n"
            f"公开岗位链接：{post.get('absolute_url') or ''}\n\n"
            f"{description}"
        ).strip()
        job_type, job_subtype = classify_job(translated_title, description)
        return JobData(
            platform="official_anthropic",
            platform_job_id=job_id,
            title=translated_title,
            company_name="Anthropic",
            company_size=None,
            company_industry="AI",
            location_city=location,
            location_district=None,
            salary_min=None,
            salary_max=None,
            salary_months=12,
            job_type=job_type,
            job_subtype=job_subtype,
            experience_required=parse_experience(description),
            education_required=parse_education(description),
            description_text=description,
            benefits=None,
            posting_date=posting_date,
            raw_json=json.dumps(_with_source(post, "greenhouse"), ensure_ascii=False),
        )


def _meituan_description(post: dict) -> str:
    parts = [
        ("部门介绍", post.get("departmentIntro")),
        ("岗位亮点", post.get("highLight")),
        ("岗位职责", post.get("jobDuty")),
        ("任职要求", post.get("jobRequirement")),
        ("优先条件", post.get("precedence")),
        ("其他信息", post.get("otherInfo")),
    ]
    lines = []
    for label, value in parts:
        if value:
            lines.append(f"【{label}】\n{value}")
    return "\n\n".join(lines)


def _join_names(items: list[dict]) -> str:
    names = []
    for item in items:
        name = (item or {}).get("name") or ""
        name = re.sub(r"[省市]$", "", name.strip())
        if name and name not in names:
            names.append(name)
    return "、".join(names)


def _clean_html(value: str) -> str:
    text = BeautifulSoup(html.unescape(value or ""), "html.parser").get_text("\n", strip=True)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def _english_terms_for_keyword(keyword: str) -> list[str]:
    role_terms: list[str] = []
    generic_terms: list[str] = []
    for key, values in OVERSEAS_TERM_MAP.items():
        if key.lower() in keyword.lower():
            if key in GENERIC_OVERSEAS_KEYS:
                generic_terms.extend(values)
            else:
                role_terms.extend(values)
    terms = role_terms or generic_terms
    if not terms and re.search(r"[a-zA-Z]", keyword):
        terms.append(keyword.lower())
    return sorted(set(term.lower() for term in terms))


def _translate_overseas_title(title: str) -> str:
    result = title
    for english, chinese in TITLE_TRANSLATIONS:
        result = re.sub(re.escape(english), chinese, result, flags=re.IGNORECASE)
    if re.search(r"[A-Za-z]", result):
        return f"海外岗位：{result}"
    return result


def _translate_location(location: str) -> str:
    result = location or "全球"
    for english, chinese in LOCATION_TRANSLATIONS:
        result = result.replace(english, chinese)
    result = result.replace(" | ", "、").replace("; ", "、")
    return result[:32]


def _date_from_millis(value) -> Optional[date]:
    if not value:
        return None
    try:
        return datetime.fromtimestamp(int(value) / 1000).date()
    except Exception:
        return None


def _date_from_iso(value: str) -> Optional[date]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except Exception:
        return None


def _with_source(post: dict, source_stage: str, **extra) -> dict:
    data = dict(post)
    data["_source_stage"] = source_stage
    data.update(extra)
    return data
