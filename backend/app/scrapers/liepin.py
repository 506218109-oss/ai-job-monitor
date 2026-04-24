import json
import re
import asyncio
from datetime import date, datetime
from typing import Optional
from pathlib import Path
from urllib.parse import quote

from playwright.async_api import async_playwright
from bs4 import BeautifulSoup

from app.scrapers.base import AbstractScraper, JobData
from app.scrapers import utils
from app.analyzers.salary_parser import parse_salary
from app.analyzers.requirement_parser import parse_experience, parse_education
from app.analyzers.job_classifier import classify_job

LIEPIN_CITY_CODES = {
    "北京": "010",
    "上海": "020",
    "深圳": "030",
    "杭州": "040",
    "广州": "050",
}

LIEPIN_SEARCH_URL = "https://www.liepin.com/zhaopin/"

PROFILE_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "browser_profile_liepin"
PROFILE_DIR.mkdir(parents=True, exist_ok=True)


class LiepinScraper(AbstractScraper):

    def __init__(self, headless: bool = True):
        self.headless = headless
        self.playwright = None
        self.context = None
        self.page = None

    async def _ensure_browser(self):
        if self.context is None:
            self.playwright = await async_playwright().start()
            self.context = await self.playwright.chromium.launch_persistent_context(
                user_data_dir=str(PROFILE_DIR),
                headless=self.headless,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                ],
                viewport={"width": 1440, "height": 900},
                locale="zh-CN",
                user_agent=utils.random_ua(),
            )
            await self.context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
                Object.defineProperty(navigator, 'languages', {get: () => ['zh-CN', 'zh', 'en']});
            """)
            if self.context.pages:
                self.page = self.context.pages[0]
            else:
                self.page = await self.context.new_page()

    async def search(self, keyword: str, city: str = "", max_pages: int = 3) -> list[JobData]:
        await self._ensure_browser()
        jobs = []

        city_code = LIEPIN_CITY_CODES.get(city, "")
        city_param = f"&city={city_code}" if city_code else ""

        for page_num in range(0, max_pages):
            encoded_keyword = quote(keyword)
            url = f"{LIEPIN_SEARCH_URL}?key={encoded_keyword}{city_param}&curPage={page_num}"
            print(f"  [Liepin] Searching: {keyword} @ {city} (page {page_num})")

            try:
                await self.page.goto(url, wait_until="domcontentloaded", timeout=30000)
                await asyncio.sleep(3)
                try:
                    await self.page.wait_for_load_state("networkidle", timeout=10000)
                except Exception:
                    pass

                page_title = await self.page.title()
                print(f"  [Liepin] Title: {page_title}")

                if "登录" in page_title and "猎聘" in page_title:
                    print(f"  [Liepin] Login wall hit. Page title: {page_title}")
                    break

                html = await self.page.content()
                page_jobs = self._parse_search_results(html, keyword, city)
                print(f"  [Liepin] Found {len(page_jobs)} jobs on page {page_num}")
                jobs.extend(page_jobs)

                if not page_jobs:
                    break

                if page_num < max_pages - 1:
                    utils.random_delay(2, 4)

            except Exception as e:
                print(f"  [Liepin] Error on page {page_num}: {e}")
                continue

        return jobs

    def _parse_search_results(self, html: str, keyword: str, city: str) -> list[JobData]:
        soup = BeautifulSoup(html, "lxml")
        jobs = []

        # 猎聘网: .job-card-pc-container is the stable class for job cards
        job_cards = soup.select(".job-card-pc-container")
        if not job_cards:
            # Fallback: broader selectors
            job_cards = soup.select("[class*='job-card']")

        for card in job_cards:
            try:
                # Detail link (contains title, salary, location)
                detail_a = card.select_one(".job-detail-box a[href]")
                if not detail_a:
                    continue

                link = detail_a.get("href", "")
                if not link:
                    continue

                # Title - first .ellipsis-1 in the link
                title_els = detail_a.select(".ellipsis-1")
                title = title_els[0].get_text(strip=True) if title_els else ""

                # City - second .ellipsis-1 (inside the location span)
                location_text = title_els[1].get_text(strip=True) if len(title_els) > 1 else city

                # Salary - span with k/K pattern
                salary_els = detail_a.select("[class*='salary'], [class*='pay']")
                if not salary_els:
                    # Find span containing 'k' or 'K'
                    all_spans = detail_a.select("span")
                    salary_els = [s for s in all_spans if re.search(r'\d+[kK]', s.get_text(strip=True))]
                salary_str = salary_els[0].get_text(strip=True) if salary_els else ""
                salary_min, salary_max, salary_months = parse_salary(salary_str)

                # Experience & Education - look through all spans in the detail link
                all_link_spans = detail_a.select("span")
                exp_text = ""
                edu_text = ""
                for span in all_link_spans:
                    text = span.get_text(strip=True)
                    if re.search(r'(\d+-\d+年|\d+年|应届|经验不限|在校|不限)', text):
                        if not exp_text:
                            exp_text = text
                    elif any(w in text for w in ["本科", "硕士", "博士", "大专", "统招", "学历", "高中"]):
                        if not edu_text:
                            edu_text = text

                exp_parsed = parse_experience(exp_text)
                edu_parsed = parse_education(edu_text)

                # Company section
                company_section = card.select_one("[data-nick='job-detail-company-info']")
                if not company_section:
                    company_section = card.select_one("[class*='company']")

                company_name = ""
                company_industry = ""
                company_size = ""

                if company_section:
                    company_name_els = company_section.select(".ellipsis-1")
                    if company_name_els:
                        company_name = company_name_els[0].get_text(strip=True)
                    # Industry/size info
                    info_spans = company_section.select("span")
                    info_texts = [s.get_text(strip=True) for s in info_spans if s.get_text(strip=True)]
                    for t in info_texts:
                        if any(w in t for w in ["互联网", "教育", "科技", "游戏", "金融", "电商", "AI", "软件", "人工智能"]):
                            company_industry = t
                        elif any(w in t for w in ["人", "上市", "融资", "天使", "A轮", "B轮", "C轮", "D轮", "未融资"]):
                            company_size = t

                # Fallback: try to parse company from card text
                if not company_name:
                    comp_el = card.select_one("[class*='company-name'], [class*='companyName']")
                    company_name = comp_el.get_text(strip=True) if comp_el else ""

                if not title or not company_name:
                    continue

                # Job ID from data attribute or URL
                job_id = self._extract_job_id(link)
                if not job_id:
                    # Try data attribute
                    data_ext = card.get("data-tlg-ext", "")
                    try:
                        import urllib.parse
                        decoded = urllib.parse.unquote(data_ext)
                        match = re.search(r'"jobId"\s*:\s*"(\d+)"', decoded)
                        if match:
                            job_id = match.group(1)
                    except Exception:
                        pass

                if not job_id:
                    continue

                city_name, district = self._split_location(location_text)
                if not city_name:
                    city_name = city

                job_type, job_subtype = classify_job(title, "")

                jobs.append(JobData(
                    platform="liepin",
                    platform_job_id=job_id,
                    title=title,
                    company_name=company_name,
                    company_size=company_size,
                    company_industry=company_industry,
                    location_city=city_name,
                    location_district=district,
                    salary_min=salary_min,
                    salary_max=salary_max,
                    salary_months=salary_months,
                    job_type=job_type,
                    job_subtype=job_subtype,
                    experience_required=exp_parsed,
                    education_required=edu_parsed,
                    raw_json=json.dumps({"title": title, "company": company_name, "link": link}, ensure_ascii=False),
                ))

            except Exception as e:
                print(f"  [Liepin] Failed to parse card: {e}")
                continue

        return jobs

    async def get_detail(self, job: JobData) -> JobData:
        await self._ensure_browser()

        detail_url = job.raw_json  # We stored the link in raw_json temporarily
        if detail_url:
            try:
                data = json.loads(detail_url)
                link = data.get("link", "")
            except (json.JSONDecodeError, TypeError):
                link = ""
        else:
            link = ""

        if not link:
            link = f"https://www.liepin.com/job/{job.platform_job_id}.shtml"

        if not link.startswith("http"):
            link = "https://www.liepin.com" + link

        try:
            await self.page.goto(link, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(2)
            html = await self.page.content()
            soup = BeautifulSoup(html, "lxml")

            # Job description
            desc_el = soup.select_one(
                ".job-detail, .job-description, .job-main-content, "
                "[class*='job-detail'], [class*='description'], "
                ".content-word, article, .job-intro"
            )
            if desc_el:
                job.description_text = desc_el.get_text(separator="\n", strip=True).strip()

            # Benefits
            tag_els = soup.select(".tag, .label, [class*='tag'], [class*='benefit']")
            benefits = []
            for tag in tag_els:
                text = tag.get_text(strip=True)
                if text and len(text) < 20:
                    benefits.append(text)
            if benefits:
                job.benefits = json.dumps(benefits, ensure_ascii=False)

            if job.description_text:
                # Re-classify with full description
                job.job_type, job.job_subtype = classify_job(job.title, job.description_text)

            # Store the original link for reference
            job.raw_json = json.dumps({"link": link, "has_detail": True}, ensure_ascii=False)

        except Exception as e:
            print(f"  [Liepin] Failed to get detail: {e}")

        return job

    def _extract_job_id(self, link: str) -> str:
        if not link:
            return ""
        match = re.search(r'/(\d+)\.s?html', link)
        if match:
            return match.group(1)
        match = re.search(r'jobid=(\d+)', link)
        if match:
            return match.group(1)
        # Use hash of link as ID
        return str(abs(hash(link)) % 10**10)

    def _split_location(self, text: str) -> tuple:
        if not text:
            return "", ""
        parts = re.split(r'[-·\s]', text.strip(), maxsplit=1)
        if len(parts) >= 2:
            return parts[0].strip(), parts[1].strip()
        return parts[0].strip(), ""

    async def close(self):
        if self.context:
            await self.context.close()
            self.context = None
            self.page = None
        if self.playwright:
            await self.playwright.stop()
            self.playwright = None
