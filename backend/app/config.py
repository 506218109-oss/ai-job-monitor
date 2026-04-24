from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent
    DATABASE_URL: str = f"sqlite:///{PROJECT_ROOT}/data/jobs.db"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Ensure data directory exists (needed for fresh deploys)
        (self.PROJECT_ROOT / "data").mkdir(parents=True, exist_ok=True)
    SCRAPE_INTERVAL_HOURS: int = 24
    SCRAPE_TIME_HOUR: int = 9
    SCRAPE_TIME_MINUTE: int = 0

    DEFAULT_PLATFORM: str = "tencent"

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
