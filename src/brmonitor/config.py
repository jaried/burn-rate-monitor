# src/brmonitor/config.py
from __future__ import annotations

from dot_dict import DotDict

CONFIG = DotDict(
    {
        "upstream_log": "C:/Users/Tony/.claude/upstream.log",
        "upstreams": {
            "official": {"rate": 1.0, "name": "官网"},
            "claude": {"rate": 6.0, "name": "中转官方"},
            "azure": {"rate": 4.0, "name": "中转azure"},
            "2api": {"rate": 0.6, "name": "2api"},
            "droid": {"rate": 0.25, "name": "aws-droid"},
        },
        "model_pricing": {
            "claude-opus-4-5-20251101": {
                "input": 5.0,
                "output": 25.0,
                "cache_creation": 6.25,
                "cache_read": 0.5,
            },
            "claude-sonnet-4-5-20250929": {
                "input": 3.0,
                "output": 15.0,
                "cache_creation": 3.75,
                "cache_read": 0.3,
            },
            "claude-sonnet-4-20250514": {
                "input": 3.0,
                "output": 15.0,
                "cache_creation": 3.75,
                "cache_read": 0.3,
            },
            "claude-3-5-sonnet-20241022": {
                "input": 3.0,
                "output": 15.0,
                "cache_creation": 3.75,
                "cache_read": 0.3,
            },
            "claude-haiku-4-5-20251001": {
                "input": 1.0,
                "output": 5.0,
                "cache_creation": 1.25,
                "cache_read": 0.1,
            },
        },
    }
)
