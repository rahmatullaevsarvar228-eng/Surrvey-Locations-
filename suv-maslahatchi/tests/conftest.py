from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from app.core.config import Settings

FIX = Path(__file__).parent / "fixtures" / "sintetik_2025.json"


@pytest.fixture
def real_like_cache(tmp_path: Path) -> Path:
    """Sintetik faylning nusxasi, lekin «haqiqiy» kabi belgilangan — faqat kesh yuklovchini sinash uchun."""
    d = tmp_path / "cache"
    d.mkdir()
    js = json.loads(FIX.read_text(encoding="utf-8"))
    js["meta"].update(id="test_2025", place="Test", synthetic=False)
    (d / "test_2025.json").write_text(json.dumps(js), encoding="utf-8")
    # data/cache ga tushib qolgan sintetik fayl e’tiborsiz qolishi kerak
    shutil.copy(FIX, d / "sintetik_kopiya.json")
    return d


@pytest.fixture
def settings(tmp_path: Path, real_like_cache: Path) -> Settings:
    return Settings(SUV_CACHE_DIR=real_like_cache, SUV_WEATHER_DIR=tmp_path / "w",
                    SUV_DB_URL=f"sqlite:///{tmp_path / 'db.sqlite3'}", SUV_WEB_DIST=tmp_path / "nodist",
                    SUV_ALLOW_SYNTHETIC=True, bot_token="", admin_ids="1,2")
