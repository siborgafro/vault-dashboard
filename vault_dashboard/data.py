"""Read-only data access: every function only reads files under the vault."""
from __future__ import annotations

import fnmatch
import json
import os
import re
from datetime import datetime
from pathlib import Path

from .i18n import MONTHS
from .markdown import FRONTMATTER, table_rows

MAX_READ = 2_000_000  # bytes; larger files are skipped
MONTH_NUMBERS = {m.lower(): i + 1 for names in MONTHS.values() for i, m in enumerate(names)}


def split_frontmatter(text: str) -> tuple[dict | None, str]:
    """Front matter as JSON or as simple `key: value` / `key: [a, b]` / `- item` lines."""
    m = FRONTMATTER.match(text)
    if not m:
        return None, text
    raw, body = m.group(1), m.group(2)
    try:
        meta = json.loads(raw)
        if isinstance(meta, dict):
            return meta, body
    except ValueError:
        pass
    meta, key = {}, None
    for line in raw.splitlines():
        if re.match(r"^\s*-\s+", line) and key:
            if isinstance(meta.setdefault(key, []), list):
                meta[key].append(re.sub(r"^\s*-\s+", "", line).strip().strip("'\""))
            continue
        kv = re.match(r"^([\w.-]+):\s*(.*)$", line)
        if not kv:
            continue
        key, val = kv.group(1), kv.group(2).strip()
        if val.startswith("[") and val.endswith("]"):
            meta[key] = [v.strip().strip("'\"") for v in val[1:-1].split(",") if v.strip()]
        elif val:
            meta[key] = val.strip("'\"")
    return meta, body


class Vault:
    def __init__(self, root: Path, cfg: dict):
        self.root = root.resolve()
        self.cfg = cfg

    # ------------------------------------------------------------ files
    def p(self, rel: str) -> Path | None:
        return (self.root / rel) if rel else None

    def read(self, p: Path | None) -> str:
        try:
            if p is None or p.stat().st_size > MAX_READ:
                return ""
            return p.read_text(encoding="utf-8").replace("\r\n", "\n")
        except (OSError, UnicodeDecodeError):
            return ""

    def rel(self, p: Path) -> str:
        return p.resolve().relative_to(self.root).as_posix()

    def features(self) -> dict[str, bool]:
        c = self.cfg

        def isfile(sec: str, key: str) -> bool:
            p = self.p(c[sec][key])
            return bool(p and p.is_file())

        def isdir(sec: str, key: str) -> bool:
            p = self.p(c[sec][key])
            return bool(p and p.is_dir())

        return {
            "topics": isfile("threads", "file"), "sessions": isfile("sessions", "file"),
            "tasks": isdir("tasks", "folder"), "receipts": isdir("receipts", "folder"),
            "schedule": isfile("schedule", "file"), "pipeline": isdir("pipeline", "root"),
            "projects": isdir("projects", "folder"),
        }

    # ------------------------------------------------------------ safety
    def safe_path(self, rel: str) -> Path | None:
        """Resolve `rel` against the vault; None if it escapes the vault."""
        if "\x00" in rel:
            return None
        try:
            p = (self.root / rel).resolve()
        except (OSError, ValueError):
            return None
        return p if p.is_relative_to(self.root) else None

    def hidden(self, p: Path) -> bool:
        try:
            return any(part.startswith(".") for part in p.relative_to(self.root).parts)
        except ValueError:
            return True

    def resolve_note(self, rel: str) -> tuple[str, Path | None]:
        """Return ("ok", path) | ("forbidden", None) | ("missing", None). Only .md files."""
        p = self.safe_path(rel)
        if p is None or self.hidden(p):
            return "forbidden", None
        if p.is_file():
            return ("ok", p) if p.suffix.lower() == ".md" else ("forbidden", None)
        if p.exists():
            return "forbidden", None
        # Obsidian-style: a bare note name matches a note anywhere in the vault.
        if ".." not in Path(rel).parts and not Path(rel).is_absolute():
            want = Path(rel).name.lower()
            want = want if want.endswith(".md") else want + ".md"
            for cand in self.walk_md():
                if cand.name.lower() == want:
                    c2 = self.safe_path(str(cand.relative_to(self.root)))
                    if c2 and c2.is_file():
                        return "ok", c2
        return "missing", None

    def walk_md(self, exclude: set[str] | None = None):
        exclude = exclude or set()
        for dirpath, dirs, files in os.walk(self.root):
            dirs[:] = sorted(d for d in dirs if not d.startswith(".") and d not in exclude)
            for fn in sorted(files):
                if fn.lower().endswith(".md"):
                    yield Path(dirpath, fn)

    # ------------------------------------------------------------ topics
    def topics(self) -> tuple[list[dict], list[dict]]:
        c = self.cfg["threads"]
        text = self.read(self.p(c["file"]))
        act = [h.lower() for h in c["active_headings"]]
        clo = [h.lower() for h in c["closed_headings"]]
        wait = [w.lower() for w in c["waiting_keywords"]]
        markers = "|".join(re.escape(x) for x in c["next_markers"]) or "Next"
        next_re = re.compile(rf"(?:{markers})[^:]*:\s*(.+?)(?:\[\[|$)", re.I)
        active, closed, section = [], [], None
        for line in text.splitlines():
            if re.match(r"^#{1,3} ", line):
                low = line.lower()
                section = "a" if any(h in low for h in act) else "c" if any(h in low for h in clo) else None
                continue
            if not section:
                continue
            m = re.match(r"^- \*\*(.+?):?\*\*:?\s*(.*)", line)
            if m:
                title, body = m.group(1).rstrip(":"), m.group(2)
            else:
                m = re.match(r"^- (.+)", line)
                if not m:
                    continue
                title, body = m.group(1)[:80], m.group(1)
            dates = re.findall(r"\d{4}-\d{2}-\d{2}", body)
            nm = next_re.search(body)
            topic = {
                "title": title, "body": body, "date": max(dates) if dates else "",
                "next": nm.group(1).strip().rstrip(".") if nm else "",
                "waiting": any(w in (title + " " + body).lower() for w in wait),
                "links": re.findall(r"\[\[([^\]]+)\]\]", body),
            }
            (active if section == "a" else closed).append(topic)
        return active, closed

    # ------------------------------------------------------------ sessions
    def sessions(self, n: int | None = None) -> list[tuple[str, str]]:
        n = n or self.cfg["sessions"]["limit"]
        text = self.read(self.p(self.cfg["sessions"]["file"]))
        parts = re.split(r"^## ", text, flags=re.M)[1:]
        return [(p.split("\n", 1)[0], p.split("\n", 1)[1].strip() if "\n" in p else "") for p in parts[:n]]

    # ------------------------------------------------------------ tasks
    def tasks(self) -> list[dict]:
        folder = self.p(self.cfg["tasks"]["folder"])
        out = []
        if not folder or not folder.is_dir():
            return out
        for p in sorted(folder.glob("*.md")):
            meta, body = split_frontmatter(self.read(p))
            meta = meta or {}
            title = meta.get("title") or next((l[2:] for l in body.splitlines() if l.startswith("# ")), p.stem)
            out.append({
                "title": str(title), "status": str(meta.get("status", "open")),
                "project": str(meta.get("project", "")),
                "due": str(meta.get("due") or meta.get("due_at") or ""),
                "path": self.rel(p),
            })
        return out

    def open_tasks(self) -> list[dict]:
        done = {s.lower() for s in self.cfg["tasks"]["done_statuses"]}
        return [t for t in self.tasks() if t["status"].lower() not in done]

    # ------------------------------------------------------------ receipts
    def receipts(self) -> list[dict]:
        c = self.cfg["receipts"]
        folder = self.p(c["folder"])
        out = []
        if not folder or not folder.is_dir():
            return out
        for p in folder.glob("*.md"):
            meta, body = split_frontmatter(self.read(p))
            if meta is None:
                continue
            try:
                when = datetime.fromisoformat(str(meta.get(c["time_key"], ""))).astimezone()
            except ValueError:
                continue
            refs = meta.get(c["refs_key"], [])
            if isinstance(refs, str):
                refs = [refs]
            out.append({"time": when, "summary": body.strip(), "refs": [str(r) for r in refs]})
        out.sort(key=lambda r: r["time"], reverse=True)
        return out

    def project_of(self, ref: str) -> str:
        root = self.cfg["projects"]["folder"].strip("/")
        parts = ref.split("/")
        if root and parts[0] == root and len(parts) > 2:
            return parts[1]
        return ""

    def projects(self, receipts: list[dict]) -> list[dict]:
        folder = self.p(self.cfg["projects"]["folder"])
        last: dict[str, datetime] = {}
        count: dict[str, int] = {}
        for r in receipts:
            for name in {self.project_of(x) for x in r["refs"]} - {""}:
                last.setdefault(name, r["time"])
                count[name] = count.get(name, 0) + 1
        out = []
        for d in sorted(folder.iterdir()) if folder and folder.is_dir() else []:
            if not d.is_dir() or d.name.startswith("."):
                continue
            files = list(d.rglob("*.md"))
            mt = max((f.stat().st_mtime for f in files), default=d.stat().st_mtime)
            out.append({
                "name": d.name, "files": len(files), "jobs": count.get(d.name, 0),
                "last": last.get(d.name) or datetime.fromtimestamp(mt).astimezone(),
                "path": self.rel(d),
            })
        out.sort(key=lambda x: x["last"], reverse=True)
        return out

    # ------------------------------------------------------------ schedule
    def schedule(self) -> list[list[str]]:
        """Rows of the first table under the configured heading (header row first)."""
        c = self.cfg["schedule"]
        text = self.read(self.p(c["file"]))
        pattern = r"^#+ +" + re.escape(c["heading"]) + r"[^\n]*\n(.*?)(?=\n#+ |\Z)"
        for m in re.finditer(pattern, text, flags=re.S | re.M):
            lines = [x for x in m.group(1).splitlines() if x.strip().startswith("|")]
            if lines:
                return table_rows(lines)
        return []

    def schedule_last_day(self, cell: str) -> datetime | None:
        """Last date in a cell: ISO dates, or "Mon 30 Nov · Wed 2 · Fri 4 Dec 17:00" (en/tr months)."""
        now = datetime.now().astimezone()
        try:
            iso = re.findall(r"(\d{4})-(\d{2})-(\d{2})", cell)
            if iso:
                y, mo, d = map(int, iso[-1])
                return datetime(y, mo, d, tzinfo=now.tzinfo)
            clean = re.sub(r"\d{1,2}:\d{2}", "", cell.replace("*", ""))
            clean = re.sub(r"\b\d{4}\b", "", clean)
            months = [MONTH_NUMBERS[w[:3].lower()] for w in re.findall(r"[^\W\d_]{3,}", clean)
                      if w[:3].lower() in MONTH_NUMBERS]
            days = re.findall(r"\b(\d{1,2})\b", clean)
            if not months or not days:
                return None
            mo = months[-1]
            year = now.year + (1 if mo < now.month - 6 else 0) - (1 if mo > now.month + 6 else 0)
            return datetime(year, mo, int(days[-1]), tzinfo=now.tzinfo)
        except ValueError:
            return None

    def upcoming_schedule(self) -> list[list[str]]:
        """Data rows (no header) whose last date is today or later; undated rows are kept."""
        today = datetime.now().astimezone().replace(hour=0, minute=0, second=0, microsecond=0)
        out = []
        for row in self.schedule()[1:]:
            day = self.schedule_last_day(row[0]) if row else None
            if day is None or day >= today:
                out.append(row)
        return out

    # ------------------------------------------------------------ pipeline
    def pipeline(self) -> tuple[list[str], list[dict]]:
        c = self.cfg["pipeline"]
        root = self.p(c["root"])
        stages = {k: ([v] if isinstance(v, str) else list(v)) for k, v in c["stages"].items()}
        if not root or not root.is_dir():
            return list(stages), []
        sources = [self.p(s) for s in c["published_sources"]] or [
            self.p(self.cfg["threads"]["file"]), self.p(self.cfg["schedule"]["file"]),
            *sorted(root.glob("*.md"))]
        text = "\n".join(self.read(s) for s in sources if s)
        kw = [k.lower() for k in c["published_keywords"]]
        url_re = re.compile(c["published_url_regex"]) if c["published_url_regex"] else None
        items = []
        for d in sorted(root.iterdir()):
            if not d.is_dir() or d.name.startswith("."):
                continue
            names = [f.name.lower() for f in d.iterdir()]
            done = [any(fnmatch.fnmatch(n, pat.lower()) for pat in pats for n in names) for pats in stages.values()]
            published = None
            bare = re.sub(r"^\d+[-_ ]+", "", d.name).lower()
            for line in text.splitlines():
                low = line.lower()
                if d.name.lower() in low or (bare and bare in low):
                    um = url_re.search(line) if url_re else None
                    if um or any(k in low for k in kw):
                        published = um.group(0) if um else "yes"
                        break
            items.append({"name": d.name, "done": done, "published": published, "path": self.rel(d)})
        return list(stages), items

    # ------------------------------------------------------------ search
    def search(self, q: str) -> list[tuple[Path, str]]:
        ql = q.lower()
        out = []
        for p in self.walk_md(set(self.cfg["search"]["exclude"])):
            hit = p.stem if ql in p.stem.lower() else None
            for line in self.read(p).splitlines():
                if ql in line.lower():
                    hit = line.strip()
                    break
            if hit:
                out.append((p, hit))
            if len(out) >= self.cfg["search"]["max_results"]:
                break
        return out
