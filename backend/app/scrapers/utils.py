import random
import time
import json
import os
from pathlib import Path

USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.2 Safari/605.1.15",
]

COOKIES_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "cookies"
COOKIES_DIR.mkdir(parents=True, exist_ok=True)


def random_delay(min_s=2.0, max_s=5.0):
    delay = random.uniform(min_s, max_s)
    time.sleep(delay)
    return delay


def random_ua() -> str:
    return random.choice(USER_AGENTS)


async def save_cookies(context, platform: str):
    cookies = await context.cookies()
    path = COOKIES_DIR / f"{platform}_cookies.json"
    with open(path, "w") as f:
        json.dump(cookies, f, ensure_ascii=False, indent=2)


def load_cookies(context, platform: str) -> bool:
    path = COOKIES_DIR / f"{platform}_cookies.json"
    if not path.exists():
        return False
    try:
        with open(path) as f:
            cookies = json.load(f)
        context.add_cookies(cookies)
        return True
    except Exception:
        return False
