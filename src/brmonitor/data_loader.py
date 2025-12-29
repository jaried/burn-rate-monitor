# src/brmonitor/data_loader.py
from __future__ import annotations

import json
import os
import time
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from brmonitor.config import CONFIG

LITELLM_PRICING_URL = "https://raw.githubusercontent.com/BerriAI/litellm/main/model_prices_and_context_window.json"
_pricing_cache: dict[str, dict] = {}
_upstream_cache: list[tuple[datetime, str]] = []
_upstream_cache_time: float = 0
_pricing_history_cache: list[tuple[datetime, str, dict]] = []
_pricing_history_cache_time: float = 0
_rate_history_cache: list[tuple[datetime, str, float]] = []
_rate_history_cache_time: float = 0


@dataclass
class UsageEntry:
    """JSONL使用记录"""

    timestamp: datetime
    cost_usd: float
    original_cost_usd: float
    model: str
    input_tokens: int
    output_tokens: int
    cache_creation_tokens: int
    cache_read_tokens: int
    upstream: str


def get_claude_data_dirs() -> list[Path]:
    """获取Claude数据目录列表"""
    home = Path.home()
    candidates = [
        home / ".config" / "claude" / "projects",
        home / ".claude" / "projects",
    ]
    dirs = [d for d in candidates if d.exists()]
    return dirs


UPSTREAM_CACHE_TTL = 30


def _load_pricing_history() -> list[tuple[datetime, str, dict]]:
    """加载模型定价历史记录"""
    global _pricing_history_cache, _pricing_history_cache_time
    now = time.time()
    if (
        _pricing_history_cache
        and (now - _pricing_history_cache_time) < UPSTREAM_CACHE_TTL
    ):
        return _pricing_history_cache

    log_path = Path(CONFIG.pricing_history_log)
    if not log_path.exists():
        return []

    records: list[tuple[datetime, str, dict]] = []
    with open(log_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split(",")
            if len(parts) >= 6:
                datetime_str = parts[0].strip()
                model = parts[1].strip()
                try:
                    dt = datetime.strptime(datetime_str, "%Y-%m-%d %H:%M:%S")
                    pricing = {
                        "input": float(parts[2].strip()),
                        "output": float(parts[3].strip()),
                        "cache_creation": float(parts[4].strip()),
                        "cache_read": float(parts[5].strip()),
                    }
                    records.append((dt, model, pricing))
                except ValueError:
                    continue

    records.sort(key=lambda x: x[0])
    _pricing_history_cache = records
    _pricing_history_cache_time = now
    return records


def _load_rate_history() -> list[tuple[datetime, str, float]]:
    """加载渠道倍率历史记录"""
    global _rate_history_cache, _rate_history_cache_time
    now = time.time()
    if _rate_history_cache and (now - _rate_history_cache_time) < UPSTREAM_CACHE_TTL:
        return _rate_history_cache

    log_path = Path(CONFIG.upstream_rate_history_log)
    if not log_path.exists():
        return []

    records: list[tuple[datetime, str, float]] = []
    with open(log_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split(",")
            if len(parts) >= 3:
                datetime_str = parts[0].strip()
                upstream = parts[1].strip()
                try:
                    dt = datetime.strptime(datetime_str, "%Y-%m-%d %H:%M:%S")
                    rate = float(parts[2].strip())
                    records.append((dt, upstream, rate))
                except ValueError:
                    continue

    records.sort(key=lambda x: x[0])
    _rate_history_cache = records
    _rate_history_cache_time = now
    return records


def _get_pricing_at_time(model: str, timestamp: datetime) -> dict | None:
    """根据时间获取当时的模型定价"""
    records = _load_pricing_history()
    if not records:
        return None

    pricing = None
    for dt, m, p in records:
        if m == model and dt <= timestamp:
            pricing = p
        elif m == model and dt > timestamp:
            break
    return pricing


def _get_rate_at_time(upstream: str, timestamp: datetime) -> float | None:
    """根据时间获取当时的渠道倍率"""
    records = _load_rate_history()
    if not records:
        return None

    rate = None
    for dt, u, r in records:
        if u == upstream and dt <= timestamp:
            rate = r
        elif u == upstream and dt > timestamp:
            break
    return rate


def _load_upstream_log() -> list[tuple[datetime, str]]:
    """加载upstream切换日志"""
    global _upstream_cache, _upstream_cache_time
    now = time.time()
    if _upstream_cache and (now - _upstream_cache_time) < UPSTREAM_CACHE_TTL:
        return _upstream_cache

    log_path = Path(CONFIG.upstream_log)
    if not log_path.exists():
        return []

    records: list[tuple[datetime, str]] = []
    with open(log_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split(",")
            if len(parts) >= 3:
                datetime_str = parts[0].strip()
                upstream = parts[-1].strip()
                try:
                    dt = datetime.strptime(datetime_str, "%Y-%m-%d %H:%M:%S")
                    records.append((dt, upstream))
                except ValueError:
                    continue

    records.sort(key=lambda x: x[0])
    _upstream_cache = records
    _upstream_cache_time = now
    return records


def _get_upstream_at_time(timestamp: datetime) -> str:
    """根据时间获取当时使用的upstream"""
    records = _load_upstream_log()
    if not records:
        return "official"

    upstream = "official"
    for dt, name in records:
        if dt <= timestamp:
            upstream = name
        else:
            break
    return upstream


def _fetch_litellm_pricing() -> dict[str, dict]:
    """从LiteLLM获取定价数据"""
    global _pricing_cache
    if _pricing_cache:
        return _pricing_cache

    try:
        with urllib.request.urlopen(LITELLM_PRICING_URL, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            _pricing_cache = data
            return data
    except Exception:
        return {}


def _get_model_pricing(model: str) -> dict:
    """获取模型定价，优先从LiteLLM获取"""
    litellm_data = _fetch_litellm_pricing()

    if model in litellm_data:
        p = litellm_data[model]
        return {
            "input": p.get("input_cost_per_token", 0) * 1_000_000,
            "output": p.get("output_cost_per_token", 0) * 1_000_000,
            "cache_creation": p.get("cache_creation_input_token_cost", 0) * 1_000_000,
            "cache_read": p.get("cache_read_input_token_cost", 0) * 1_000_000,
        }

    if model in CONFIG.model_pricing:
        return dict(CONFIG.model_pricing[model])

    return {"input": 3.0, "output": 15.0, "cache_creation": 3.75, "cache_read": 0.3}


def _calculate_cost(
    model: str,
    input_tokens: int,
    output_tokens: int,
    cache_creation_tokens: int = 0,
    cache_read_tokens: int = 0,
    timestamp: datetime | None = None,
) -> float:
    """根据模型和token数计算成本，优先使用历史价格"""
    pricing = None
    if timestamp:
        pricing = _get_pricing_at_time(model, timestamp)
    if not pricing:
        pricing = _get_model_pricing(model)
    cost = (
        input_tokens * pricing["input"]
        + output_tokens * pricing["output"]
        + cache_creation_tokens * pricing.get("cache_creation", 0)
        + cache_read_tokens * pricing.get("cache_read", 0)
    ) / 1_000_000
    return cost


def parse_jsonl_line(line: str) -> UsageEntry | None:
    """解析单行JSONL"""
    try:
        data = json.loads(line)
        timestamp_str = data.get("timestamp")
        if not timestamp_str:
            return None

        message = data.get("message", {})
        usage = message.get("usage", {})
        input_tokens = usage.get("input_tokens", 0)
        output_tokens = usage.get("output_tokens", 0)
        cache_creation_tokens = usage.get("cache_creation_input_tokens", 0)
        cache_read_tokens = usage.get("cache_read_input_tokens", 0)

        if input_tokens == 0 and output_tokens == 0:
            return None

        model = message.get("model", "")

        utc_time = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
        timestamp = utc_time.astimezone().replace(tzinfo=None)

        cost_usd = data.get("costUSD")
        if cost_usd is None:
            cost_usd = _calculate_cost(
                model,
                input_tokens,
                output_tokens,
                cache_creation_tokens,
                cache_read_tokens,
                timestamp,
            )

        upstream = _get_upstream_at_time(timestamp)
        rate = _get_rate_at_time(upstream, timestamp)
        if rate is None:
            rate = CONFIG.upstreams.get(upstream, {}).get("rate", 1.0)
        actual_cost = cost_usd * rate

        entry = UsageEntry(
            timestamp=timestamp,
            cost_usd=actual_cost,
            original_cost_usd=cost_usd,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_creation_tokens=cache_creation_tokens,
            cache_read_tokens=cache_read_tokens,
            upstream=upstream,
        )
        return entry
    except (json.JSONDecodeError, ValueError, KeyError):
        return None


def load_jsonl_files(dirs: list[Path]) -> list[UsageEntry]:
    """加载所有JSONL文件"""
    entries: list[UsageEntry] = []

    for dir_path in dirs:
        for root, _, files in os.walk(dir_path):
            for filename in files:
                if not filename.endswith(".jsonl"):
                    continue
                file_path = Path(root) / filename
                file_entries = _load_single_file(file_path)
                entries.extend(file_entries)

    entries.sort(key=lambda e: e.timestamp)
    return entries


def _load_single_file(file_path: Path) -> list[UsageEntry]:
    """加载单个JSONL文件"""
    entries: list[UsageEntry] = []
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                entry = parse_jsonl_line(line)
                if entry:
                    entries.append(entry)
    except (OSError, IOError):
        pass
    return entries


def load_all_entries() -> list[UsageEntry]:
    """加载所有使用记录的便捷函数"""
    dirs = get_claude_data_dirs()
    entries = load_jsonl_files(dirs)
    return entries
