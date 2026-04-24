import sys
import os
import asyncio

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.services.scraping_service import run_scrape
from app.config import settings


async def main():
    print("=" * 50)
    print("AI Job Monitor - Scraper")
    print("=" * 50)
    print(f"Platform: {settings.DEFAULT_PLATFORM}")
    print(f"Keywords: {', '.join(settings.SEARCH_KEYWORDS)}")
    print(f"Cities: {', '.join(settings.TARGET_CITIES)}")
    print("=" * 50)

    result = await run_scrape(settings.DEFAULT_PLATFORM, settings.SEARCH_KEYWORDS)
    print(f"\nDone! Found: {result['jobs_found']}, New: {result['jobs_new']}, Updated: {result['jobs_updated']}")
    print(f"Status: {result['status']}")


if __name__ == "__main__":
    asyncio.run(main())
