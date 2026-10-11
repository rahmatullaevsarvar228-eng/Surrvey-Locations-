"""Sozlamalar: .env dan (BOT_TOKEN, ADMIN_IDS, TZ) va ixtiyoriy SUV_* o‘zgaruvchilar."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", env_file_encoding="utf-8", extra="ignore")

    bot_token: str = ""
    admin_ids: Annotated[list[int], NoDecode] = Field(default_factory=list)
    tz: str = "Asia/Tashkent"
    db_url: str = Field(default=f"sqlite:///{ROOT / 'data' / 'suv.sqlite3'}", alias="SUV_DB_URL")
    cache_dir: Path = Field(default=ROOT / "data" / "cache", alias="SUV_CACHE_DIR")
    weather_dir: Path = Field(default=ROOT / "data" / "weather", alias="SUV_WEATHER_DIR")
    web_dist: Path = Field(default=ROOT / "web" / "dist", alias="SUV_WEB_DIST")
    # Sintetik ob-havo (faqat sinov/skrinshot uchun). Yoqilsa, UI qizil ogohlantirish ko‘rsatadi.
    allow_synthetic: bool = Field(default=False, alias="SUV_ALLOW_SYNTHETIC")
    weather_ttl_s: int = 3 * 3600
    advice_hour: int = 7

    @field_validator("admin_ids", mode="before")
    @classmethod
    def _split_ids(cls, v: object) -> object:
        if isinstance(v, str):
            return [int(x) for x in v.replace(";", ",").split(",") if x.strip()]
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()
