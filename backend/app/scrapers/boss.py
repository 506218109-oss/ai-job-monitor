import json
import os
import re
import asyncio
from datetime import date, datetime
from typing import Optional
from pathlib import Path

from playwright.async_api import async_playwright
from bs4 import BeautifulSoup

from app.scrapers.base import AbstractScraper, JobData
from app.scrapers import utils
from app.analyzers.salary_parser import parse_salary
from app.analyzers.requirement_parser import parse_experience, parse_education
from app.analyzers.job_classifier import classify_job

BOSS_CITY_CODES = {
    "北京": "100010000",
    "上海": "100020000",
    "深圳": "100030000",
    "杭州": "100040000",
    "广州": "100050000",
}

BOSS_SEARCH_URL = "https://www.zhipin.com/web/geek/job"

PROFILE_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "browser_profile"
PROFILE_DIR.mkdir(parents=True, exist_ok=True)


class BossScraper(AbstractScraper):

    def __init__(self, headless: bool = True):
        self.headless = headless
        self.playwright = None
        self.context = None
        self.page = None

    async def _ensure_browser(self):
        if self.context is None:
            self.playwright = await async_playwright().start()
            profile_path = str(PROFILE_DIR)

            if not self.headless and not any(
                os.path.exists(os.path.join(profile_path, d))
                for d in ["Default", "Local Storage", "Preferences"]
            ):
                # First login: open visible browser for manual login
                pass

            self.context = await self.playwright.chromium.launch_persistent_context(
                user_data_dir=profile_path,
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

        city_code = BOSS_CITY_CODES.get(city, "")
        city_param = f"&city={city_code}" if city_code else ""

        for page_num in range(1, max_pages + 1):
            url = f"{BOSS_SEARCH_URL}?query={keyword}{city_param}&page={page_num}"
            print(f"  [BOSS] Searching: {keyword} @ {city} (page {page_num})")

            try:
                await self.page.goto(url, wait_until="domcontentloaded", timeout=30000)
                await asyncio.sleep(4)
                try:
                    await self.page.wait_for_load_state("networkidle", timeout=10000)
                except Exception:
                    pass

                page_url = self.page.url
                if "/user/" in page_url:
                    print(f"  [BOSS] Redirected to login page. Please run: python3 scripts/login_boss.py")
                    break

                # Try to extract data from API responses on the page
                api_data = await self._try_extract_api_data()
                if api_data:
                    print(f"  [BOSS] API data found: {len(api_data)} items")
                    for item in api_data:
                        job = self._parse_api_item(item, keyword)
                        if job:
                            jobs.append(job)
                else:
                    # Fall back to DOM parsing
                    html = await self.page.content()
                    page_jobs = self._parse_search_results(html, keyword)
                    if page_jobs:
                        print(f"  [BOSS] DOM parsed: {len(page_jobs)} jobs")
                    jobs.extend(page_jobs)

                if page_num < max_pages:
                    utils.random_delay(2, 4)

            except Exception as e:
                print(f"  [BOSS] Error on page {page_num}: {e}")
                continue

        return jobs

    async def _try_extract_api_data(self) -> Optional[list]:
        """Try to extract job data from embedded JSON in the page."""
        try:
            html = await self.page.content()
            soup = BeautifulSoup(html, "lxml")

            for script in soup.find_all("script"):
                text = script.string or ""
                if "jobList" in text or "zpList" in text or "geekJobList" in text:
                    for match in re.finditer(r'\{[^}]*"jobList"[^}]*\}', text):
                        try:
                            data = json.loads(match.group())
                            if "jobList" in data:
                                return data["jobList"]
                        except json.JSONDecodeError:
                            continue

            for script in soup.find_all("script"):
                text = script.string or ""
                if "window.__INITIAL_STATE__" in text or "window.__NUXT__" in text:
                    match = re.search(r'=\s*(\{.*\})', text, re.DOTALL)
                    if match:
                        try:
                            data = json.loads(match.group(1))
                            for key in ["jobList", "result", "list", "data"]:
                                if key in data:
                                    return data[key]
                                if isinstance(data, dict):
                                    for v in data.values():
                                        if isinstance(v, dict) and key in v:
                                            return v[key]
                        except (json.JSONDecodeError, TypeError):
                            continue
        except Exception:
            pass
        return None

    def _parse_api_item(self, item: dict, keyword: str) -> Optional[JobData]:
        try:
            job_id = str(item.get("encryptJobId") or item.get("jobId") or item.get("securityId") or item.get("id", ""))
            if not job_id:
                return None

            title = item.get("jobName") or item.get("title") or ""
            company = item.get("brandName") or item.get("companyName") or item.get("company") or item.get("brandComName") or ""
            if not title or not company:
                return None

            salary_str = item.get("salaryDesc") or item.get("salary") or ""
            salary_min, salary_max, salary_months = parse_salary(salary_str)

            city = item.get("cityName") or item.get("city") or ""
            district = item.get("areaDistrict") or item.get("district") or ""

            exp = item.get("jobExperience") or item.get("experience") or item.get("requireWorkYearsName") or ""
            edu = item.get("jobDegree") or item.get("education") or item.get("requireDegreeName") or ""

            exp_parsed = parse_experience(exp)
            edu_parsed = parse_education(edu)

            job_type, job_subtype = classify_job(title, item.get("jobDesc") or "")

            desc = item.get("jobDesc") or item.get("description") or ""

            posting_date = self._parse_post_date(item)

            return JobData(
                platform="boss",
                platform_job_id=job_id,
                title=title,
                company_name=company,
                company_size=item.get("brandScaleName") or item.get("companySize") or "",
                company_industry=item.get("brandIndustry") or item.get("industry") or "",
                location_city=city,
                location_district=district,
                salary_min=salary_min,
                salary_max=salary_max,
                salary_months=salary_months,
                experience_required=exp_parsed,
                education_required=edu_parsed,
                description_text=desc,
                posting_date=posting_date,
                raw_json=json.dumps(item, ensure_ascii=False),
            )
        except Exception as e:
            print(f"  [BOSS] Failed to parse API item: {e}")
            return None

    def _parse_search_results(self, html: str, keyword: str) -> list[JobData]:
        soup = BeautifulSoup(html, "lxml")
        jobs = []

        job_cards = soup.select(
            ".job-card-wrapper, .job-card-box, .search-job-result li, "
            ".job-list-box li, [class*='job-card'], .result-list li, "
            ".job-primary, .job-list-item"
        )

        for card in job_cards:
            try:
                title_el = (
                    card.select_one(".job-name, .job-title, a[class*='job-name'], h3 a")
                    or card.select_one("[class*='job-name'], [class*='job-title']")
                )
                company_el = (
                    card.select_one(".company-name, .company-text, a[class*='company']")
                    or card.select_one("[class*='company-name']")
                )
                salary_el = (
                    card.select_one(".salary, .red, [class*='salary']")
                    or card.select_one("[class*='red']")
                )

                if not title_el:
                    continue

                title = title_el.get_text(strip=True)
                company = company_el.get_text(strip=True) if company_el else ""
                salary_str = salary_el.get_text(strip=True) if salary_el else ""

                if not title or not company:
                    continue

                link_el = card.select_one("a[href]") or title_el.select_one("a[href]")
                job_id = ""
                if link_el:
                    href = link_el.get("href", "")
                    match = re.search(r'/job_detail/([^.]+)\.html', href)
                    if not match:
                        match = re.search(r'securityId=([^&]+)', href)
                    if match:
                        job_id = match.group(1)

                if not job_id:
                    continue

                salary_min, salary_max, salary_months = parse_salary(salary_str)

                location_text = ""
                loc_el = card.select_one(".job-area, .job-location, [class*='area']")
                if loc_el:
                    location_text = loc_el.get_text(strip=True)
                city, district = self._split_location(location_text)

                exp_text = ""
                edu_text = ""
                tag_els = card.select(".tag-item, .job-tag, .condition, [class*='tag'], .badge")
                for tag in tag_els:
                    text = tag.get_text(strip=True)
                    if any(w in text for w in ["年", "应届", "经验"]):
                        exp_text = text
                    elif any(w in text for w in ["本科", "硕士", "博士", "大专", "学历"]):
                        edu_text = text

                exp_parsed = parse_experience(exp_text)
                edu_parsed = parse_education(edu_text)

                job_type, job_subtype = classify_job(title, "")

                jobs.append(JobData(
                    platform="boss",
                    platform_job_id=job_id,
                    title=title,
                    company_name=company,
                    location_city=city,
                    location_district=district,
                    salary_min=salary_min,
                    salary_max=salary_max,
                    salary_months=salary_months,
                    experience_required=exp_parsed,
                    education_required=edu_parsed,
                    raw_json=json.dumps({"title": title, "company": company}, ensure_ascii=False),
                ))

            except Exception as e:
                print(f"  [BOSS] Failed to parse job card: {e}")
                continue

        return jobs

    async def get_detail(self, job: JobData) -> JobData:
        await self._ensure_browser()
        detail_url = f"https://www.zhipin.com/job_detail/{job.platform_job_id}.html"

        try:
            await self.page.goto(detail_url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(2)
            html = await self.page.content()
            soup = BeautifulSoup(html, "lxml")

            desc_el = soup.select_one(
                ".job-detail-section, .job-sec-text, .job-detail, [class*='job-detail'], "
                "[class*='job-sec'], .detail-content, article, .description, .job-desc"
            )
            if desc_el:
                job.description_text = desc_el.get_text(separator="\n", strip=True).strip()

            tag_els = soup.select(".tag-item, .job-tag, .condition, [class*='tag']")
            benefits = []
            for tag in tag_els:
                text = tag.get_text(strip=True)
                if text and len(text) < 20:
                    benefits.append(text)
            if benefits:
                job.benefits = json.dumps(benefits, ensure_ascii=False)

        except Exception as e:
            print(f"  [BOSS] Failed to get detail for {job.platform_job_id}: {e}")

        return job

    def _parse_post_date(self, item: dict) -> Optional[date]:
        for k in ["publishDate", "pubDate", "postDate", "activeTimeDesc", "bossOnlineTime"]:
            val = item.get(k, "")
            if val:
                try:
                    if isinstance(val, str):
                        if "T" in val:
                            return datetime.fromisoformat(val.replace("Z", "+00:00")).date()
                        if "-" in val and len(val) >= 10:
                            return date.fromisoformat(val[:10])
                    if isinstance(val, (int, float)):
                        return datetime.fromtimestamp(val / 1000).date()
                except (ValueError, TypeError):
                    pass
        return date.today()

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
