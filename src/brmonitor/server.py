# src/brmonitor/server.py
from __future__ import annotations

import asyncio
import threading
from dataclasses import asdict
from pathlib import Path
from typing import Any

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

_cache: dict[str, dict[str, Any]] = {}
_cache_lock = threading.Lock()


def _build_response_data(view: str) -> dict[str, Any]:
    """构建响应数据"""
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
    return response_data


def _refresh_cache() -> None:
    """刷新所有视图缓存"""
    views = ["current", "today", "24h"]
    for view in views:
        response_data = _build_response_data(view)
        with _cache_lock:
            _cache[view] = response_data
    return


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
    """获取burn rate数据（从缓存读取）"""
    with _cache_lock:
        if view in _cache:
            response = JSONResponse(content=_cache[view])
            return response

    response_data = _build_response_data(view)
    with _cache_lock:
        _cache[view] = response_data
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


async def _background_refresh_task() -> None:
    """后台定时刷新缓存"""
    while True:
        await asyncio.sleep(30)
        _refresh_cache()
    return


@app.on_event("startup")
async def startup_event() -> None:
    """启动时初始化缓存并启动后台任务"""
    _refresh_cache()
    asyncio.create_task(_background_refresh_task())
    return


def main() -> None:
    """启动服务器"""
    uvicorn.run(app, host="0.0.0.0", port=3001)
    return
