import os
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

PMS_DIR = Path(__file__).resolve().parent.parent
HOTEL_TZ = ZoneInfo("America/Mexico_City")
FAILURE_MODES = ("none", "timeout", "error")
PLACEHOLDER_SECRET = "change-me-to-a-long-random-string"


@dataclass(frozen=True)
class Settings:
    tool_secret: str
    db_path: str
    failure_mode: str = "none"
    timeout_seconds: float = 5.0

    def __post_init__(self) -> None:
        if not self.tool_secret or self.tool_secret == PLACEHOLDER_SECRET:
            raise ValueError("Set TOOL_SECRET in .env.local to a long random string.")
        if self.failure_mode not in FAILURE_MODES:
            raise ValueError(f"PMS_FAILURE_MODE must be one of {FAILURE_MODES}.")


def load_settings() -> Settings:
    load_dotenv(PMS_DIR / ".env.local")
    db_path = Path(os.getenv("DB_PATH", "pms.sqlite3"))
    if not db_path.is_absolute():
        db_path = PMS_DIR / db_path
    return Settings(
        tool_secret=os.getenv("TOOL_SECRET", ""),
        db_path=str(db_path),
        failure_mode=os.getenv("PMS_FAILURE_MODE", "none").strip().lower(),
        timeout_seconds=float(os.getenv("PMS_TIMEOUT_SECONDS", "5")),
    )


def today_in_hotel() -> date:
    return datetime.now(HOTEL_TZ).date()
