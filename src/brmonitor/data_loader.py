# src/brmonitor/data_loader.py
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass
class UsageEntry:
    """JSONL使用记录"""
    timestamp: datetime
    cost_usd: float
    model: str
    input_tokens: int
    output_tokens: int
    cache_creation_tokens: int
    cache_read_tokens: int


def get_claude_data_dirs() -> list[Path]:
    """获取Claude数据目录列表"""
    home = Path.home()
    candidates = [
        home / ".config" / "claude" / "projects",
        home / ".claude" / "projects",
    ]
    dirs = [d for d in candidates if d.exists()]
    return dirs


MODEL_PRICING = {
    "claude-opus-4-5-20251101": {
        "input": 15.0, "output": 75.0,
        "cache_creation": 18.75, "cache_read": 1.5,
    },
    "claude-sonnet-4-20250514": {
        "input": 3.0, "output": 15.0,
        "cache_creation": 3.75, "cache_read": 0.3,
    },
    "claude-3-5-sonnet-20241022": {
        "input": 3.0, "output": 15.0,
        "cache_creation": 3.75, "cache_read": 0.3,
    },
    "claude-3-5-haiku-20241022": {
        "input": 0.8, "output": 4.0,
        "cache_creation": 1.0, "cache_read": 0.08,
    },
}


def _calculate_cost(
    model: str,
    input_tokens: int,
    output_tokens: int,
    cache_creation_tokens: int = 0,
    cache_read_tokens: int = 0,
) -> float:
    """根据模型和token数计算成本"""
    default_pricing = {"input": 3.0, "output": 15.0, "cache_creation": 3.75, "cache_read": 0.3}
    pricing = MODEL_PRICING.get(model, default_pricing)
    cost = (
        input_tokens * pricing["input"]
        + output_tokens * pricing["output"]
        + cache_creation_tokens * pricing.get("cache_creation", pricing["input"] * 1.25)
        + cache_read_tokens * pricing.get("cache_read", pricing["input"] * 0.1)
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
        cost_usd = data.get("costUSD")
        if cost_usd is None:
            cost_usd = _calculate_cost(
                model, input_tokens, output_tokens,
                cache_creation_tokens, cache_read_tokens,
            )

        utc_time = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
        timestamp = utc_time.astimezone().replace(tzinfo=None)
        entry = UsageEntry(
            timestamp=timestamp,
            cost_usd=cost_usd,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_creation_tokens=cache_creation_tokens,
            cache_read_tokens=cache_read_tokens,
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
