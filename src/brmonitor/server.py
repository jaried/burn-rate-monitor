# src/brmonitor/server.py
from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse

from brmonitor.calculator import (
    aggregate_by_minute,
    calculate_burn_rate,
    calculate_stats,
    filter_entries_by_view,
)
from brmonitor.data_loader import load_all_entries

app = FastAPI(title="Burn Rate Monitor")


def _serialize_minute_data(d: dict) -> dict:
    """序列化MinuteData，将datetime转为ISO字符串"""
    result = d.copy()
    if "timestamp" in result:
        result["timestamp"] = result["timestamp"].isoformat()
    return result

PUBLIC_DIR = Path(__file__).parent / "public"


@app.get("/")
async def index() -> FileResponse:
    """返回前端页面"""
    response = FileResponse(PUBLIC_DIR / "index.html")
    return response


@app.get("/api/burn-rate")
async def get_burn_rate(view: str = "current") -> JSONResponse:
    """获取burn rate数据"""
    entries = load_all_entries()
    filtered = filter_entries_by_view(entries, view)
    data = aggregate_by_minute(filtered)
    current_rate = calculate_burn_rate(data)
    stats = calculate_stats(data)

    response_data = {
        "current_rate": current_rate,
        "data": [_serialize_minute_data(asdict(d)) for d in data],
        "stats": asdict(stats),
    }
    response = JSONResponse(content=response_data)
    return response


@app.get("/api/stats")
async def get_stats() -> JSONResponse:
    """获取统计摘要"""
    entries = load_all_entries()
    filtered = filter_entries_by_view(entries, "today")
    data = aggregate_by_minute(filtered)
    stats = calculate_stats(data)

    response = JSONResponse(content=asdict(stats))
    return response


def main() -> None:
    """启动服务器"""
    uvicorn.run(app, host="0.0.0.0", port=3001)
    return
