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


def get_claude_data_dirs() -> list[Path]:
    """获取Claude数据目录列表"""
    home = Path.home()
    candidates = [
        home / ".config" / "claude" / "projects",
        home / ".claude" / "projects",
    ]
    dirs = [d for d in candidates if d.exists()]
    return dirs


def parse_jsonl_line(line: str) -> UsageEntry | None:
    """解析单行JSONL"""
    try:
        data = json.loads(line)
        timestamp_str = data.get("timestamp")
        cost_usd = data.get("costUSD", 0.0)
        model = data.get("model", "")
        input_tokens = data.get("inputTokens", 0)
        output_tokens = data.get("outputTokens", 0)

        if not timestamp_str:
            return None

        timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
        entry = UsageEntry(
            timestamp=timestamp,
            cost_usd=cost_usd,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
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
