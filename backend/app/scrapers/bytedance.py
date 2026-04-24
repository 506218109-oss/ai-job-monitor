import json
import time
import asyncio
import re
from datetime import datetime, date
from typing import Optional
from urllib.parse import unquote

import httpx

from app.scrapers.base import AbstractScraper, JobData
from app.scrapers import utils
from app.analyzers.salary_parser import parse_salary
from app.analyzers.requirement_parser import parse_experience, parse_education
from app.analyzers.job_classifier import classify_job

BYTEDANCE_CSRF_URL = "https://jobs.bytedance.com/api/v1/csrf/token"
BYTEDANCE_SEARCH_URL = "https://jobs.bytedance.com/api/v1/search/job/posts"

# Job categories to include (product, operations, etc.) — parent category IDs
# We'll filter by checking category names rather than IDs since IDs may change
EXCLUDE_CATEGORY_NAMES = {
    "研发", "后端", "前端", "算法", "测试", "运维", "安全",
    "数据工程师", "硬件", "客户端", "Android", "iOS",
    "架构师", "技术经理", "技术总监",
}

INCLUDE_CATEGORY_NAMES = {
    "产品经理", "产品运营", "运营", "用户运营", "内容运营",
    "策略运营", "市场", "商务", "销售", "增长",
    "培训", "客服", "审核", "编辑",
}


class ByteDanceScraper(AbstractScraper):

    def __init__(self):
        self.client = None
        self.csrf_token = None

    async def _ensure_client(self):
        if self.client is None:
            self.client = httpx.AsyncClient(
                headers={
                    "User-Agent": utils.random_ua(),
                    "Accept": "application/json, text/plain, */*",
                    "Origin": "https://jobs.bytedance.com",
                    "Referer": "https://jobs.bytedance.com/experienced/position",
                },
                timeout=30.0,
                follow_redirects=True,
            )

    async def _get_csrf_token(self) -> str:
        """Get a fresh CSRF token. Tokens are valid for 7 days."""
        await self._ensure_client()

        try:
            resp = await self.client.post(
                BYTEDANCE_CSRF_URL,
                json={"portal_entrance": 1},
            )
            data = resp.json()
            if data.get("code") == 0:
                token = data["data"]["token"]
                self.csrf_token = token
                # Also extract from cookies for backup (httpx Cookies maps name->value)
                csrf_cookie = resp.cookies.get("atsx-csrf-token")
                if csrf_cookie:
                    self.csrf_token = unquote(csrf_cookie)
                print(f"  [ByteDance] Got CSRF token")
                return self.csrf_token
            else:
                print(f"  [ByteDance] CSRF error: {data}")
                return ""
        except Exception as e:
            print(f"  [ByteDance] CSRF exception: {e}")
            return ""

    async def search(self, keyword: str, city: str = "", max_pages: int = 3) -> list[JobData]:
        await self._ensure_client()

        if not self.csrf_token:
            await self._get_csrf_token()
        if not self.csrf_token:
            print("  [ByteDance] No CSRF token, aborting")
            return []

        jobs = []
        page_size = 20

        for offset in range(0, max_pages * page_size, page_size):
            print(f"  [ByteDance] Searching: {keyword} @ {city} (offset {offset})")

            payload = {
                "job_category_id_list": [],
                "keyword": keyword,
                "limit": page_size,
                "location_code_list": [],
                "offset": offset,
                "portal_entrance": 1,
                "portal_type": 2,  # 社招
                "recruitment_id_list": [],
                "subject_id_list": [],
            }

            try:
                resp = await self.client.post(
                    BYTEDANCE_SEARCH_URL,
                    json=payload,
                    headers={
                        "x-csrf-token": self.csrf_token,
                        "Content-Type": "application/json",
                    },
                )

                if resp.status_code == 401 or resp.status_code == 403:
                    # Token expired, refresh
                    print(f"  [ByteDance] Token expired, refreshing...")
                    await self._get_csrf_token()
                    if not self.csrf_token:
                        break
                    resp = await self.client.post(
                        BYTEDANCE_SEARCH_URL,
                        json=payload,
                        headers={
                            "x-csrf-token": self.csrf_token,
                            "Content-Type": "application/json",
                        },
                    )

                data = resp.json()
                if data.get("code") != 0:
                    print(f"  [ByteDance] API error: {data}")
                    break

                posts = data.get("data", {}).get("job_post_list", [])
                if not posts:
                    break

                for post in posts:
                    try:
                        job_data = self._parse_post(post, keyword, city)
                        if job_data:
                            jobs.append(job_data)
                    except Exception as e:
                        print(f"  [ByteDance] Parse error: {e}")
                        continue

                print(f"  [ByteDance] Offset {offset}: {len(posts)} posts, {len(jobs)} kept")

                if len(posts) < page_size:
                    break

                if offset + page_size < max_pages * page_size:
                    utils.random_delay(1, 2)

            except Exception as e:
                print(f"  [ByteDance] Error at offset {offset}: {e}")
                continue

        return jobs

    def _parse_post(self, post: dict, keyword: str, city: str) -> Optional[JobData]:
        title = post.get("title", "")
        job_id = post.get("id", "")

        if not title or not job_id:
            return None

        # Filter by category name
        category_info = post.get("job_category", {})
        category_name = category_info.get("name", "")
        parent_category = category_info.get("parent", {})
        parent_name = parent_category.get("name", "") if parent_category else ""

        if category_name in EXCLUDE_CATEGORY_NAMES:
            return None
        if parent_name in EXCLUDE_CATEGORY_NAMES:
            return None

        # City
        city_info = post.get("city_info", {})
        city_name = city_info.get("name", city)
        if not city_name:
            city_name = city

        # Description - both job description and requirement come from search API
        description = post.get("description", "")
        requirement = post.get("requirement", "")

        combined_desc = description
        if requirement:
            combined_desc = f"{description}\n\n【任职要求】\n{requirement}"

        # Experience/Education - parse from requirement and description text
        exp_text = ""
        edu_text = ""
        combined_text = f"{title} {requirement}"
        exp_parsed = parse_experience(combined_text)
        edu_parsed = parse_education(combined_text)

        # Publish time (millisecond timestamp)
        pub_ts = post.get("publish_time")
        posting_date = None
        if pub_ts:
            try:
                posting_date = datetime.fromtimestamp(pub_ts / 1000).date()
            except Exception:
                pass

        # Classify
        job_type, job_subtype = classify_job(title, combined_desc)

        # Get address for district info
        address = post.get("job_post_info", {}).get("address", "") if post.get("job_post_info") else ""
        district = self._extract_district(city_name, address)

        return JobData(
            platform="bytedance",
            platform_job_id=job_id,
            title=title,
            company_name="字节跳动",
            company_size="10000人以上",
            company_industry="互联网",
            location_city=city_name,
            location_district=district,
            salary_min=None,
            salary_max=None,
            salary_months=12,
            job_type=job_type,
            job_subtype=job_subtype,
            experience_required=exp_parsed,
            education_required=edu_parsed,
            description_text=combined_desc,
            benefits=None,
            posting_date=posting_date,
            raw_json=json.dumps(post, ensure_ascii=False),
        )

    def _extract_district(self, city_name: str, address: str) -> str:
        """Extract district from address string."""
        if not address or not city_name:
            return ""
        # Pattern: 中国大陆北京市海淀区...
        pattern = city_name + r'([^市]+?)[区县]'
        match = re.search(pattern, address)
        if match:
            return match.group(1) + "区"
        return ""

    async def get_detail(self, job: JobData) -> JobData:
        # ByteDance search API already returns full description + requirement
        # No separate detail API needed
        return job

    async def close(self):
        if self.client:
            await self.client.aclose()
            self.client = None
