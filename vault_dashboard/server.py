"""HTTP server and page rendering. GET/HEAD only; nothing is ever written."""
from __future__ import annotations

from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, quote, urlencode, urlparse

from . import __version__
from .data import Vault
from .i18n import MONTHS, tr
from .markdown import esc, inline, render

CSS = """
:root{color-scheme:dark light;--bg:#0f1115;--card:#171a21;--card2:#1d212a;--line:#2a2f3a;--text:#e6e8ec;
--dim:#8b93a3;--accent:#e0b04a;--green:#4cc38a;--red:#e5605a;--blue:#5aa2e5}
@media(prefers-color-scheme:light){:root{--bg:#f6f7f9;--card:#fff;--card2:#eef0f4;--line:#dcdfe6;--text:#1c2029;
--dim:#667085;--accent:#a56d00;--green:#13804f;--red:#c0362f;--blue:#1f6fbf}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);
font:14px/1.55 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
a{color:var(--blue);text-decoration:none}a:hover{text-decoration:underline}
.top{display:flex;gap:4px;align-items:center;padding:10px 20px;border-bottom:1px solid var(--line);
position:sticky;top:0;background:var(--bg);z-index:5;flex-wrap:wrap}
.logo{font-weight:700;margin-right:18px;color:var(--accent)}
.top a.t{color:var(--dim);padding:6px 12px;border-radius:8px}
.top a.t.on,.top a.t:hover{background:var(--card2);color:var(--text);text-decoration:none}
.right{margin-left:auto;display:flex;gap:8px;align-items:center}
.right input{background:var(--card);border:1px solid var(--line);color:var(--text);padding:6px 10px;
border-radius:8px;width:200px}
.lang{border:1px solid var(--line);border-radius:8px;padding:5px 10px;color:var(--dim)}
main{max-width:1200px;margin:0 auto;padding:22px 20px 60px}
h1{font-size:20px;margin:4px 0 18px}h2{font-size:15px;margin:26px 0 10px;color:var(--dim);
text-transform:uppercase;letter-spacing:.06em}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:12px}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px 16px}
.card h3{margin:0 0 6px;font-size:15px}.card p{margin:6px 0;color:var(--dim)}
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px}
.stat{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px 16px}
.stat b{display:block;font-size:26px}.stat span{color:var(--dim)}
.badge{display:inline-block;font-size:11px;padding:1px 8px;border-radius:99px;background:var(--card2);
color:var(--dim);border:1px solid var(--line);margin-right:4px}
.badge.g{color:var(--green)}.badge.a{color:var(--accent)}
.next{color:var(--text)!important;border-left:3px solid var(--accent);padding-left:8px}
.tw{overflow-x:auto}table{border-collapse:collapse;width:100%;background:var(--card);border-radius:12px;overflow:hidden}
th,td{padding:8px 12px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}
th{color:var(--dim);font-weight:600;font-size:12px;background:var(--card2)}
td.ok{color:var(--green);text-align:center}td.no{color:var(--dim);opacity:.5;text-align:center}
.feed{border-left:2px solid var(--line);margin-left:6px}
.event{position:relative;padding:0 0 14px 18px}.event:before{content:"";position:absolute;left:-6px;top:6px;
width:10px;height:10px;border-radius:50%;background:var(--accent)}
.event small{color:var(--dim)}.day{margin:18px 0 8px;color:var(--dim);font-weight:600}
.note{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:8px 24px 20px}
.note h2{color:var(--text);text-transform:none;letter-spacing:0;font-size:20px}
.note h3{font-size:16px}.note pre{background:var(--bg);padding:12px;border-radius:8px;overflow:auto}
.note blockquote{margin:8px 0;padding-left:12px;border-left:3px solid var(--line);color:var(--dim)}
code{background:var(--card2);padding:1px 5px;border-radius:4px;font-size:12.5px}
.path{color:var(--dim);font-size:12px;margin-bottom:10px}
.bar{height:6px;background:var(--card2);border-radius:3px;overflow:hidden;margin-top:8px}
.bar i{display:block;height:100%;background:var(--accent)}
.filter{margin:0 0 14px;display:flex;gap:6px;flex-wrap:wrap}
@media(max-width:640px){.right{margin-left:0;width:100%}.right input{width:100%}}
"""

LOOPBACK = {"127.0.0.1", "localhost", "::1", "[::1]"}


class Ctx:
    """One request: vault, language, current path/query."""

    def __init__(self, vault: Vault, lang: str, path: str, query: dict[str, str]):
        self.v, self.lang, self.path, self.q = vault, lang, path, query
        self.cfg = vault.cfg
        self.feat = vault.features()

    def t(self, key: str, **kw) -> str:
        return tr(self.lang, key, **kw)

    def date(self, z: datetime) -> str:
        return f"{z.day} {MONTHS[self.lang][z.month - 1]} {z.year}"

    def ago(self, z: datetime) -> str:
        d = datetime.now(z.tzinfo) - z
        if d.days >= 1:
            return self.t("ago_days", n=d.days)
        h = d.seconds // 3600
        return self.t("ago_hours", n=h) if h else self.t("just_now")

    def lang_url(self) -> str:
        q = dict(self.q)
        q["lang"] = "tr" if self.lang == "en" else "en"
        return self.path + "?" + urlencode(q)

    def nav(self) -> list[tuple[str, str, bool]]:
        pt = self.cfg["pipeline"]["title"] or self.t("nav_pipeline")
        return [
            ("/", self.t("nav_summary"), True), ("/topics", self.t("nav_topics"), self.feat["topics"]),
            ("/pipeline", pt, self.feat["pipeline"]), ("/projects", self.t("nav_projects"), self.feat["projects"]),
            ("/activity", self.t("nav_activity"), self.feat["receipts"]),
        ]


def note_link(path: str) -> str:
    return "/note?path=" + quote(path)


def folder_link(path: str) -> str:
    return "/folder?path=" + quote(path)


def layout(c: Ctx, title: str, body: str, active: str = "") -> str:
    nav = "".join(f'<a class="t{" on" if href == active else ""}" href="{href}">{esc(label)}</a>'
                  for href, label, on in c.nav() if on)
    name = esc(c.cfg["dashboard"]["title"])
    return f"""<!doctype html><html lang="{c.lang}"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{esc(title)} · {name}</title>
<style>{CSS}</style></head><body><div class="top"><span class="logo">◆ {name}</span>{nav}
<div class="right"><form action="/search"><input name="q" placeholder="{esc(c.t('search_ph'))}"></form>
<a class="lang" href="{esc(c.lang_url())}">{c.t('lang_other')}</a></div></div>
<main>{body}</main></body></html>"""


def table(rows: list[list[str]]) -> str:
    if not rows:
        return ""
    head = "".join(f"<th>{inline(h)}</th>" for h in rows[0])
    body = "".join("<tr>" + "".join(f"<td>{inline(h)}</td>" for h in r) + "</tr>" for r in rows[1:])
    return f'<div class="tw"><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'


def clip(s: str, n: int) -> str:
    return s[:n] + ("…" if len(s) > n else "")


# ---------------------------------------------------------------- pages
def topic_card(c: Ctx, k: dict) -> str:
    wait = f'<span class="badge a">{c.t("waiting")}</span>' if k["waiting"] else ""
    date = f'<span class="badge">{esc(k["date"])}</span>' if k["date"] else ""
    nxt = f'<p class="next">{c.t("next")}: {inline(clip(k["next"], 220))}</p>' if k["next"] else ""
    links = "".join(f'<a class="badge" href="{esc(note_link(x.split("|")[0].split("#")[0].strip()))}">'
                    f'{esc(x.split("|")[-1].split("/")[-1])}</a>' for x in k["links"][:4])
    return (f'<div class="card"><h3>{esc(k["title"])}</h3>{date}{wait}<p>{inline(clip(k["body"], 260))}</p>'
            f'{nxt}<div>{links}</div></div>')


def page_summary(c: Ctx) -> tuple[int, str]:
    v, f = c.v, c.feat
    parts, stats = [], []
    if f["topics"]:
        stats.append((len(v.topics()[0]), c.t("stat_topics")))
    receipts = v.receipts() if f["receipts"] else []
    if f["receipts"]:
        week = datetime.now().astimezone().timestamp() - 7 * 86400
        stats.append((sum(1 for r in receipts if r["time"].timestamp() >= week), c.t("stat_week")))
    tasks = v.open_tasks() if f["tasks"] else []
    if f["tasks"]:
        stats.append((len(tasks), c.t("stat_tasks")))
    if f["pipeline"]:
        items = v.pipeline()[1]
        stats.append((f'{sum(1 for i in items if i["published"])}/{len(items)}', c.t("stat_published")))
    if stats:
        parts.append('<div class="stats">' + "".join(
            f'<div class="stat"><b>{n}</b><span>{esc(label)}</span></div>' for n, label in stats) + "</div>")
    if f["schedule"]:
        rows = v.upcoming_schedule()
        if rows:
            head = v.schedule()[0]
            parts.append(f'<h2>{c.t("sec_schedule")}</h2>' + table([head] + rows[:c.cfg["schedule"]["limit"]])
                         + f'<p class="path"><a href="{esc(note_link(c.cfg["schedule"]["file"]))}">{c.t("full_table")}</a></p>')
    if f["sessions"]:
        cards = "".join(f'<div class="card"><h3>{esc(h)}</h3><p>{inline(clip(b, 420))}</p></div>'
                        for h, b in v.sessions())
        if cards:
            parts.append(f'<h2>{c.t("sec_sessions")}</h2><div class="grid">{cards}</div>')
    if f["tasks"]:
        cards = "".join(
            f'<div class="card"><h3><a href="{esc(note_link(t["path"]))}">{esc(t["title"])}</a></h3>'
            + (f'<span class="badge">{esc(t["project"])}</span>' if t["project"] else "")
            + f'<span class="badge a">{esc(t["status"])}</span>'
            + (f'<span class="badge">{c.t("due")}: {esc(t["due"])}</span>' if t["due"] else "") + "</div>"
            for t in tasks) or f'<p class="path">{c.t("no_tasks")}</p>'
        parts.append(f'<h2>{c.t("sec_tasks")}</h2><div class="grid">{cards}</div>')
    if f["receipts"] and receipts:
        ev = "".join(f'<div class="event"><small>{c.date(r["time"])} {r["time"]:%H:%M}</small><br>'
                     f'{inline(clip(r["summary"], 240))}</div>' for r in receipts[:6])
        parts.append(f'<h2>{c.t("sec_recent")}</h2><div class="feed">{ev}</div>'
                     f'<p class="path"><a href="/activity">{c.t("all_activity")}</a></p>')
    return 200, layout(c, c.t("nav_summary"), f"<h1>{esc(c.cfg['dashboard']['title'])}</h1>" + "".join(parts), "/")


def page_topics(c: Ctx) -> tuple[int, str]:
    active, closed = c.v.topics()
    waiting = [k for k in active if k["waiting"]]
    going = sorted((k for k in active if not k["waiting"]), key=lambda k: k["date"], reverse=True)

    def grid(title: str, ks: list[dict]) -> str:
        return f'<h2>{title} ({len(ks)})</h2><div class="grid">{"".join(topic_card(c, k) for k in ks)}</div>' if ks else ""

    body = f'<h1>{c.t("nav_topics")}</h1>' + grid(c.t("topics_ongoing"), going) + grid(
        c.t("topics_waiting"), waiting) + grid(c.t("topics_closed"), closed)
    return 200, layout(c, c.t("nav_topics"), body, "/topics")


def page_pipeline(c: Ctx) -> tuple[int, str]:
    stages, items = c.v.pipeline()
    title = c.cfg["pipeline"]["title"] or c.t("nav_pipeline")
    head = "".join(f"<th>{esc(s)}</th>" for s in stages)
    rows = ""
    for i in items:
        cells = "".join(f'<td class="{"ok" if d else "no"}">{"●" if d else "○"}</td>' for d in i["done"])
        if i["published"] and i["published"].startswith("http"):
            st = f'<a class="badge g" href="{esc(i["published"])}" target="_blank" rel="noopener noreferrer">{c.t("published")}</a>'
        elif i["published"]:
            st = f'<span class="badge g">{c.t("published")}</span>'
        else:
            st = f'<span class="badge a">{c.t("in_progress")}</span>'
        pct = sum(i["done"]) / len(i["done"]) * 100 if i["done"] else 0
        rows += (f'<tr><td><a href="{esc(folder_link(i["path"]))}"><b>{esc(i["name"])}</b></a>'
                 f'<div class="bar"><i style="width:{pct:.0f}%"></i></div></td>{cells}<td>{st}</td></tr>')
    body = (f'<h1>{esc(title)}</h1><div class="tw"><table><thead><tr><th>{c.t("th_item")}</th>{head}'
            f'<th>{c.t("th_status")}</th></tr></thead><tbody>{rows}</tbody></table></div>'
            f'<p class="path">{c.t("pipeline_legend")}</p>')
    if c.feat["schedule"]:
        body += f'<h2>{c.t("sec_schedule")}</h2>' + table(c.v.schedule())
    return 200, layout(c, title, body, "/pipeline")


def page_projects(c: Ctx) -> tuple[int, str]:
    cards = ""
    for p in c.v.projects(c.v.receipts() if c.feat["receipts"] else []):
        cards += (f'<div class="card"><h3><a href="{esc(folder_link(p["path"]))}">{esc(p["name"])}</a></h3>'
                  f'<span class="badge">{c.t("n_notes", n=p["files"])}</span>'
                  + (f'<span class="badge">{c.t("n_jobs", n=p["jobs"])}</span>' if c.feat["receipts"] else "")
                  + f'<p>{c.t("last_move")}: {c.date(p["last"])} · {c.ago(p["last"])}</p></div>')
    return 200, layout(c, c.t("nav_projects"), f'<h1>{c.t("nav_projects")}</h1><div class="grid">{cards}</div>', "/projects")


def page_activity(c: Ctx) -> tuple[int, str]:
    project = c.q.get("project", "")
    rs = c.v.receipts()
    names = sorted({c.v.project_of(x) for r in rs for x in r["refs"]} - {""})
    if project:
        rs = [r for r in rs if any(c.v.project_of(x) == project for x in r["refs"])]
    flt = f'<a class="badge{" a" if not project else ""}" href="/activity">{c.t("all_projects")}</a>' + "".join(
        f'<a class="badge{" a" if n == project else ""}" href="/activity?project={quote(n)}">{esc(n)}</a>' for n in names)
    html, day = "", None
    for r in rs[:c.cfg["receipts"]["limit"]]:
        d = c.date(r["time"])
        if d != day:
            html += ("</div>" if day else "") + f'<div class="day">{d}</div><div class="feed">'
            day = d
        refs = " ".join(f'<a class="badge" href="{esc(note_link(x))}">{esc(x.split("/")[-1])}</a>'
                        for x in r["refs"][:4] if x.endswith(".md"))
        html += f'<div class="event"><small>{r["time"]:%H:%M}</small><br>{inline(clip(r["summary"], 500))}<div>{refs}</div></div>'
    html += "</div>" if day else ""
    title = f'{c.t("activity")} · {project}' if project else c.t("activity")
    return 200, layout(c, title, f'<h1>{esc(title)}</h1><div class="filter">{flt}</div>'
                       f'<p class="path">{c.t("records", n=len(rs))}</p>{html}', "/activity")


def page_note(c: Ctx) -> tuple[int, str]:
    rel = c.q.get("path", "")
    status, p = c.v.resolve_note(rel)
    if status == "forbidden":
        return 403, layout(c, c.t("not_found"), f'<h1>403</h1><p>{c.t("forbidden")}</p>')
    if p is None:
        return 404, layout(c, c.t("not_found"), f'<h1>{c.t("note_not_found")}</h1><p>{esc(rel)}</p>')
    r = c.v.rel(p)
    up = "/".join(r.split("/")[:-1])
    crumb = f'<a href="{esc(folder_link(up))}">{esc(up)}</a> / ' if up else ""
    project = c.v.project_of(r)
    feed = (f' · <a href="/activity?project={quote(project)}">{c.t("project_activity")}</a>'
            if project and c.feat["receipts"] else "")
    return 200, layout(c, p.stem, f'<div class="path">{crumb}{esc(p.name)}{feed}</div>'
                       f'<div class="note">{render(c.v.read(p))}</div>')


def page_folder(c: Ctx) -> tuple[int, str]:
    rel = c.q.get("path", "")
    p = c.v.safe_path(rel)
    if p is None or c.v.hidden(p):
        return 403, layout(c, c.t("not_found"), f'<h1>403</h1><p>{c.t("forbidden")}</p>')
    if not p.is_dir():
        return 404, layout(c, c.t("not_found"), f'<h1>{c.t("folder_not_found")}</h1>')
    cards = ""
    for o in sorted(p.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower())):
        if o.name.startswith("."):
            continue
        r = c.v.rel(o)
        if o.is_dir():
            cards += f'<div class="card"><h3>▸ <a href="{esc(folder_link(r))}">{esc(o.name)}</a></h3></div>'
        elif o.suffix.lower() == ".md":
            first = next((s[2:] for s in c.v.read(o).splitlines() if s.startswith("# ")), "")
            cards += f'<div class="card"><h3><a href="{esc(note_link(r))}">{esc(o.stem)}</a></h3><p>{esc(first)}</p></div>'
    r = c.v.rel(p)
    project = c.v.project_of(r + "/x")
    feed = (f'<p class="path"><a href="/activity?project={quote(project)}">{c.t("all_activity")}</a></p>'
            if project and c.feat["receipts"] else "")
    return 200, layout(c, p.name or "/", f'<h1>{esc(p.name or "/")}</h1>{feed}<div class="grid">{cards}</div>')


def page_search(c: Ctx) -> tuple[int, str]:
    q = c.q.get("q", "").strip()
    if not q:
        return 200, layout(c, c.t("search"), f'<h1>{c.t("search")}</h1>')
    hits = c.v.search(q)
    cards = "".join(
        f'<div class="card"><h3><a href="{esc(note_link(c.v.rel(p)))}">{esc(p.stem)}</a></h3>'
        f'<div class="path">{esc(c.v.rel(p))}</div><p>{inline(clip(line, 240))}</p></div>' for p, line in hits)
    return 200, layout(c, c.t("search"), f'<h1>“{esc(q)}” · {c.t("n_results", n=len(hits))}</h1><div class="grid">{cards}</div>')


ROUTES = {
    "/": (page_summary, None), "/topics": (page_topics, "topics"), "/pipeline": (page_pipeline, "pipeline"),
    "/projects": (page_projects, "projects"), "/activity": (page_activity, "receipts"),
    "/note": (page_note, None), "/folder": (page_folder, None), "/search": (page_search, None),
}


class Handler(BaseHTTPRequestHandler):
    server_version = f"vault-dashboard/{__version__}"
    vault: Vault

    def _host_ok(self) -> bool:
        # Guard against DNS rebinding when listening on loopback only.
        if self.server.server_address[0] not in LOOPBACK:
            return True
        raw = self.headers.get("Host") or ""
        host = raw[: raw.find("]") + 1] if raw.startswith("[") else raw.rsplit(":", 1)[0]
        return host in LOOPBACK

    def _send(self, code: int, body: bytes, extra: list[tuple[str, str]] | None = None, head: bool = False):
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Content-Security-Policy",
                         "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; base-uri 'none'")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cache-Control", "no-store")
        for k, val in extra or []:
            self.send_header(k, val)
        self.end_headers()
        if not head:
            self.wfile.write(body)

    def _handle(self, head: bool = False):
        if not self._host_ok():
            return self._send(403, b"forbidden host", head=head)
        u = urlparse(self.path)
        q = {k: val[0] for k, val in parse_qs(u.query).items()}
        default = self.vault.cfg["dashboard"]["language"]
        cookie = {}
        for part in (self.headers.get("Cookie") or "").split(";"):
            if "=" in part:
                a, b = part.strip().split("=", 1)
                cookie[a] = b
        lang = q.get("lang") or cookie.get("vd_lang") or default
        if lang not in ("en", "tr"):
            lang = default
        extra = [("Set-Cookie", f"vd_lang={lang}; Path=/; SameSite=Strict; Max-Age=31536000")] if "lang" in q else []
        route = ROUTES.get(u.path)
        c = Ctx(self.vault, lang, u.path, {k: val for k, val in q.items() if k != "lang"})
        if route is None:
            code, html = 404, layout(c, "404", f'<h1>404</h1><p>{c.t("not_found")}</p>')
        elif route[1] and not c.feat[route[1]]:
            code, html = 404, layout(c, "404", f'<h1>404</h1><p>{c.t("not_available")}</p>')
        else:
            try:
                code, html = route[0](c)
            except Exception as e:  # keep the server alive if a page breaks
                code, html = 500, layout(c, c.t("error"), f'<h1>{c.t("error")}</h1><pre>{esc(repr(e))}</pre>')
        self._send(code, html.encode("utf-8"), extra, head)

    def do_GET(self):
        self._handle()

    def do_HEAD(self):
        self._handle(head=True)

    def _no(self):
        self._send(405, b"read-only", [("Allow", "GET, HEAD")])

    do_POST = do_PUT = do_DELETE = do_PATCH = _no

    def log_message(self, *a):
        pass


def make_server(vault: Vault, host: str, port: int) -> ThreadingHTTPServer:
    handler = type("BoundHandler", (Handler,), {"vault": vault})
    return ThreadingHTTPServer((host, port), handler)
