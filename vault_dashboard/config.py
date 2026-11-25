"""Configuration: built-in defaults merged with an optional TOML file."""
from __future__ import annotations

import copy
import tomllib
from pathlib import Path

DEFAULTS: dict = {
    "dashboard": {"title": "Vault dashboard", "language": "en", "host": "127.0.0.1", "port": 8767},
    # Active topics file: bullets under "Active" / "Closed" headings.
    "threads": {
        "file": "Threads.md",
        "active_headings": ["Active"],
        "closed_headings": ["Closed", "Done"],
        "waiting_keywords": ["waiting", "blocked", "on hold"],
        "next_markers": ["Next", "Open", "Remaining"],
    },
    # Last-session file: one "## heading" block per session, newest first.
    "sessions": {"file": "Last-Session.md", "limit": 3},
    # Tasks: one Markdown file per task with front matter (JSON or simple key: value).
    "tasks": {"folder": "tasks", "done_statuses": ["done", "cancelled", "canceled", "closed"]},
    # Receipts / log: one Markdown file per event with a timestamp and refs in front matter.
    "receipts": {"folder": "receipts", "time_key": "created_at", "refs_key": "refs", "limit": 300},
    # Schedule: the first table under a heading in one file. Empty file = tab section off.
    "schedule": {"file": "", "heading": "Schedule", "limit": 6},
    # Pipeline: every sub-folder of `root` is one item; a stage is done when its file exists.
    "pipeline": {
        "root": "",
        "title": "",
        "stages": {
            "Research": "Sources.md",
            "Script": "Script.md",
            "Visuals": "Visuals.md",
            "Edit": ["Edit.md", "*.mp4"],
            "Shorts": "Shorts.md",
            "Package": "Package.md",
        },
        "published_keywords": ["published", "live"],
        "published_url_regex": "",
        "published_sources": [],
    },
    "projects": {"folder": "projects"},
    "search": {"exclude": ["receipts", "Archive", ".git", ".obsidian"], "max_results": 80},
}

# Tables whose user value replaces the default instead of merging with it.
_REPLACE = {"stages"}


def _merge(base: dict, user: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in user.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict) and k not in _REPLACE:
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


def load_config(path: Path | None) -> dict:
    user: dict = {}
    if path is not None:
        with open(path, "rb") as f:
            user = tomllib.load(f)
    cfg = _merge(DEFAULTS, user)
    d = cfg["dashboard"]
    d["port"] = int(d["port"])
    if d["language"] not in ("en", "tr"):
        d["language"] = "en"
    return cfg
