import os
from pydantic_settings import BaseSettings
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def _load_local_env():
    for env_path in (REPO_ROOT / ".env", REPO_ROOT / "backend" / ".env"):
        if not env_path.exists():
            continue
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value


def _env(name: str, default: str = "") -> str:
    return os.getenv(name) or os.getenv(f"AIJM_{name}") or default


_load_local_env()


class Settings(BaseSettings):
    PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent
    DATABASE_URL: str = f"sqlite:///{PROJECT_ROOT}/data/jobs.db"
    SCRAPE_INTERVAL_HOURS: int = 24
    SCRAPE_TIME_HOUR: int = 9
    SCRAPE_TIME_MINUTE: int = 0

    DEFAULT_PLATFORM: str = "third_party"
    SERPAPI_API_KEY: str = _env("SERPAPI_API_KEY")
    ADZUNA_APP_ID: str = _env("ADZUNA_APP_ID")
    ADZUNA_APP_KEY: str = _env("ADZUNA_APP_KEY")
    THIRD_PARTY_MAX_QUERIES_PER_RUN: int = 24
    THIRD_PARTY_ADZUNA_COUNTRIES: str = "us,gb,ca,au,sg"

    SEARCH_KEYWORDS: list[str] = [
        "AI产品经理",
        "大模型产品经理",
        "人工智能产品经理",
        "AI运营",
        "大模型运营",
        "AI产品运营",
        "数据产品经理",
        "提示词工程师",
        "AI训练师",
    ]

    TARGET_CITIES: list[str] = ["北京", "上海", "深圳", "杭州", "广州"]

    class Config:
        env_prefix = "AIJM_"


settings = Settings()
