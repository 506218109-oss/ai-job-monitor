import json
import time
import asyncio
import re
from datetime import date
from typing import Optional

import httpx
from bs4 import BeautifulSoup

from app.scrapers.base import AbstractScraper, JobData
from app.scrapers import utils
from app.analyzers.salary_parser import parse_salary
from app.analyzers.requirement_parser import parse_experience, parse_education
from app.analyzers.job_classifier import classify_job

TENCENT_SEARCH_URL = "https://careers.tencent.com/tencentcareer/api/post/Query"
TENCENT_DETAIL_URL = "https://careers.tencent.com/tencentcareer/api/post/ByPostId"

# Categories to exclude (engineering/tech roles)
EXCLUDE_CATEGORIES = {
    "技术", "技术研发", "软件开发", "测试", "运维", "安全",
    "设计",  # UI/UX design - depends on preference
}

# Categories we want to include
INCLUDE_CATEGORIES = {
    "产品", "产品/项目", "运营", "市场", "销售", "战略",
    "金融", "人力资源", "行政", "采购", "客服", "公关",
}


class TencentScraper(AbstractScraper):

    def __init__(self):
        self.client = None

    async def _ensure_client(self):
        if self.client is None:
            self.client = httpx.AsyncClient(
                headers={
                    "User-Agent": utils.random_ua(),
                    "Accept": "application/json",
                },
                timeout=30.0,
            )

    async def search(self, keyword: str, city: str = "", max_pages: int = 3) -> list[JobData]:
        await self._ensure_client()
        jobs = []

        for page in range(1, max_pages + 1):
            params = {
                "timestamp": str(int(time.time() * 1000)),
                "keyword": keyword,
                "pageIndex": page,
                "pageSize": 20,
                "language": "zh-cn",
                "area": "cn",
            }
            if city:
                params["locationName"] = city

            print(f"  [Tencent] Searching: {keyword} @ {city} (page {page})")

            try:
                resp = await self.client.get(TENCENT_SEARCH_URL, params=params)
                data = resp.json()

                if data.get("Code") != 200:
                    print(f"  [Tencent] API error: {data}")
                    break

                posts = data.get("Data", {}).get("Posts", [])
                if not posts:
                    break

                for post in posts:
                    try:
                        job_data = self._parse_post(post, keyword, city)
                        if job_data:
                            jobs.append(job_data)
                    except Exception as e:
                        print(f"  [Tencent] Parse error: {e}")
                        continue

                print(f"  [Tencent] Page {page}: {len(posts)} posts, {len(jobs)} kept")

                if page < max_pages:
                    utils.random_delay(1, 2)

            except Exception as e:
                print(f"  [Tencent] Error on page {page}: {e}")
                continue

        return jobs

    def _parse_post(self, post: dict, keyword: str, city: str) -> Optional[JobData]:
        category = post.get("CategoryName", "")
        title = post.get("RecruitPostName", "")
        post_id = str(post.get("PostId", ""))

        if not title or not post_id:
            return None

        # Filter out engineering roles by category
        if category in EXCLUDE_CATEGORIES:
            return None

        # Extract city
        location = post.get("LocationName", "")
        city_name, district = self._split_location(location)
        if not city_name:
            city_name = city

        # Experience
        exp_text = post.get("RequireWorkYearsName", "")
        exp_parsed = parse_experience(exp_text)

        # Description (Responsibility comes from search API)
        description = post.get("Responsibility", "")

        # Classify job type
        job_type, job_subtype = classify_job(title, description)

        return JobData(
            platform="tencent",
            platform_job_id=post_id,
            title=title,
            company_name="腾讯",
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
            education_required=None,
            description_text=description,
            benefits=None,
            posting_date=None,
            raw_json=json.dumps(post, ensure_ascii=False),
        )

    async def get_detail(self, job: JobData) -> JobData:
        await self._ensure_client()

        try:
            params = {
                "timestamp": str(int(time.time() * 1000)),
                "postId": job.platform_job_id,
                "language": "zh-cn",
            }
            resp = await self.client.get(TENCENT_DETAIL_URL, params=params)
            data = resp.json()

            if data.get("Code") == 200:
                post = data.get("Data", {})
                requirement = post.get("Requirement", "")
                responsibility = post.get("Responsibility", "")

                if requirement:
                    # Append requirement to existing responsibility text
                    existing = job.description_text or ""
                    if responsibility and responsibility not in existing:
                        existing = responsibility
                    job.description_text = f"{existing}\n\n【任职要求】\n{requirement}"

                edu_text = post.get("Education", "")
                if edu_text:
                    job.education_required = parse_education(edu_text)

                # Update raw_json with full data
                job.raw_json = json.dumps(post, ensure_ascii=False)

                # Re-classify with richer description
                if requirement:
                    job.job_type, job.job_subtype = classify_job(
                        job.title, job.description_text or ""
                    )

        except Exception as e:
            print(f"  [Tencent] Detail error for {job.platform_job_id}: {e}")

        return job

    def _split_location(self, text: str) -> tuple:
        if not text:
            return "", ""
        parts = re.split(r'[-·\s]', text.strip(), maxsplit=1)
        if len(parts) >= 2:
            return parts[0].strip(), parts[1].strip()
        return parts[0].strip(), ""

    async def close(self):
        if self.client:
            await self.client.aclose()
            self.client = None
