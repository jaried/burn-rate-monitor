# src/brmonitor/calculator.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from brmonitor.data_loader import UsageEntry


@dataclass
class MinuteData:
    """分钟聚合数据"""
    minute: str
    timestamp: datetime
    cost_usd: float
    input_tokens: int
    output_tokens: int
    count: int


@dataclass
class Stats:
    """统计信息"""
    total_cost: float
    total_input_tokens: int
    total_output_tokens: int
    average_rate: float
    peak_rate: float
    peak_tokens: int
    duration_minutes: int


@dataclass
class BurnRateResponse:
    """API响应数据"""
    current_rate: float
    data: list[MinuteData]
    stats: Stats


def aggregate_by_minute(entries: list[UsageEntry]) -> list[MinuteData]:
    """按分钟聚合数据"""
    if not entries:
        return []

    minute_map: dict[str, MinuteData] = {}

    for entry in entries:
        minute_key = entry.timestamp.strftime("%Y-%m-%d %H:%M")
        if minute_key in minute_map:
            minute_map[minute_key].cost_usd += entry.cost_usd
            minute_map[minute_key].input_tokens += entry.input_tokens
            minute_map[minute_key].output_tokens += entry.output_tokens
            minute_map[minute_key].count += 1
        else:
            minute_data = MinuteData(
                minute=entry.timestamp.strftime("%H:%M"),
                timestamp=entry.timestamp.replace(second=0, microsecond=0),
                cost_usd=entry.cost_usd,
                input_tokens=entry.input_tokens,
                output_tokens=entry.output_tokens,
                count=1,
            )
            minute_map[minute_key] = minute_data

    result = list(minute_map.values())
    result.sort(key=lambda x: x.timestamp)
    return result


def calculate_burn_rate(data: list[MinuteData]) -> float:
    """计算当前burn rate（最近一分钟）"""
    if not data:
        return 0.0
    result = data[-1].cost_usd
    return result


def calculate_stats(data: list[MinuteData]) -> Stats:
    """计算统计信息"""
    if not data:
        stats = Stats(
            total_cost=0.0,
            total_input_tokens=0,
            total_output_tokens=0,
            average_rate=0.0,
            peak_rate=0.0,
            peak_tokens=0,
            duration_minutes=0,
        )
        return stats

    total_cost = sum(d.cost_usd for d in data)
    total_input_tokens = sum(d.input_tokens for d in data)
    total_output_tokens = sum(d.output_tokens for d in data)
    duration_minutes = len(data)
    average_rate = total_cost / duration_minutes if duration_minutes > 0 else 0.0
    peak_rate = max(d.cost_usd for d in data)
    peak_tokens = max(d.input_tokens + d.output_tokens for d in data)

    stats = Stats(
        total_cost=total_cost,
        total_input_tokens=total_input_tokens,
        total_output_tokens=total_output_tokens,
        average_rate=average_rate,
        peak_rate=peak_rate,
        peak_tokens=peak_tokens,
        duration_minutes=duration_minutes,
    )
    return stats


SESSION_DURATION_HOURS = 5


def _floor_to_hour(dt: datetime) -> datetime:
    """向下取整到小时"""
    result = dt.replace(minute=0, second=0, microsecond=0)
    return result


def _find_current_block_start(entries: list[UsageEntry]) -> datetime | None:
    """找到当前活跃block的开始时间"""
    if not entries:
        return None

    session_duration = timedelta(hours=SESSION_DURATION_HOURS)
    sorted_entries = sorted(entries, key=lambda e: e.timestamp)
    now = datetime.now()

    current_block_start: datetime | None = None
    last_entry_time: datetime | None = None

    for entry in sorted_entries:
        entry_time = entry.timestamp

        if current_block_start is None:
            current_block_start = _floor_to_hour(entry_time)
            last_entry_time = entry_time
            continue

        time_since_block_start = entry_time - current_block_start
        time_since_last_entry = entry_time - last_entry_time if last_entry_time else timedelta(0)

        if time_since_block_start > session_duration or time_since_last_entry > session_duration:
            current_block_start = _floor_to_hour(entry_time)

        last_entry_time = entry_time

    if current_block_start is None:
        return None

    block_end = current_block_start + session_duration
    if now > block_end:
        return None

    return current_block_start


def filter_entries_by_view(
    entries: list[UsageEntry],
    view: str,
) -> list[UsageEntry]:
    """根据视图过滤数据"""
    if not entries:
        return []

    now = datetime.now()

    if view == "today":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif view == "24h":
        start = now - timedelta(hours=24)
    else:
        block_start = _find_current_block_start(entries)
        if block_start is None:
            return []
        start = block_start

    result = [e for e in entries if e.timestamp >= start]
    return result
