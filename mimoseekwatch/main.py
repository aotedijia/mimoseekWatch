from __future__ import annotations

import os
import sys
from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .database import Database


ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))
STATIC = ROOT / "static"
DATA_DIR = Path(os.getenv("MIMOSEEKWATCH_DATA_DIR", Path(os.getenv("LOCALAPPDATA", ROOT)) / "mimoseekWatch"))
DB = Database(Path(os.getenv("MIMOSEEKWATCH_DB", DATA_DIR / "mimoseekwatch.db")))
app = FastAPI(title="mimoseekWatch", version="1.0.0", docs_url="/api/docs")
app.mount("/static", StaticFiles(directory=STATIC), name="static")


class SettingsUpdate(BaseModel):
    warning_balance: float = Field(ge=0, le=1_000_000_000)


@app.get("/", include_in_schema=False)
async def dashboard() -> FileResponse:
    return FileResponse(STATIC / "index.html")


@app.get("/health")
async def health() -> dict:
    return {"ok": True, "version": app.version}


@app.get("/api/summary")
async def get_summary() -> dict:
    data = DB.summary()
    data["settings"] = {
        "warning_balance": float(DB.get_setting("warning_balance", "10")),
    }
    data["web_import"] = {
        "last_success": DB.get_setting("last_web_import", ""),
        "last_error": DB.get_setting("last_web_import_error", ""),
        "status": DB.get_setting("web_login_status", "等待网页登录后同步"),
        "balance_status": DB.get_setting("web_balance_status", "等待网页登录后同步"),
        "mimo_last_success": DB.get_setting("mimo_last_sync", ""),
        "mimo_last_error": DB.get_setting("mimo_last_error", ""),
        "mimo_status": DB.get_setting("mimo_web_status", "等待网页登录后同步"),
    }
    return data


@app.put("/api/settings")
async def update_settings(settings: SettingsUpdate) -> dict:
    values = {
        "warning_balance": str(settings.warning_balance),
    }
    DB.set_settings(values)
    return {"ok": True}
