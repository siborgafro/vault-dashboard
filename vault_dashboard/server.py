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
/* Accent: deep teal #0F766E (light) / #2DD4BF (dark). Display: Bricolage Grotesque, body: Inter; both used only
   if installed locally, since the CSP blocks external requests. */
:root{--bg:#F8FAFC;--card:#FFFFFF;--card2:#F1F5F9;--line:#E2E8F0;--text:#0F172A;--dim:#475569;--faint:#94A3B8;
--accent:#0F766E;--on-accent:#FFFFFF;--band:#1E293B;--band-text:#F8FAFC;--band-dim:#CBD5E1;
--green:#15803D;--red:#B91C1C;--warn:#B45309;--r-s:6px;--r-card:8px}
@media(prefers-color-scheme:dark){:root{--bg:#0F172A;--card:#172033;--card2:#1E293B;--line:#283548;--text:#F1F5F9;
--dim:#94A3B8;--faint:#475569;--accent:#2DD4BF;--on-accent:#0F172A;--band:#0B1120;--band-text:#F1F5F9;
--band-dim:#94A3B8;--green:#4ADE80;--red:#F87171;--warn:#FBBF24}}
*{box-sizing:border-box}html,body{overflow-x:hidden}
body{margin:0;background:var(--bg);color:var(--text);font:400 15px/1.55 Inter,"Segoe UI",system-ui,sans-serif}
b,strong{font-weight:600}
h1,h2,h3{font-family:"Bricolage Grotesque",Inter,"Segoe UI",sans-serif;font-weight:600;letter-spacing:-.01em}
a{color:var(--accent);text-decoration:none}a:hover{text-decoration:underline}
:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.band{background:var(--band);color:var(--band-text);border-bottom:1px solid var(--line)}
.band-in{max-width:1440px;margin:0 auto;padding:12px 24px;display:flex;gap:16px;align-items:center;flex-wrap:wrap}
.logo{font-family:"Bricolage Grotesque",Inter,sans-serif;font-weight:600;font-size:20px;color:var(--band-text);margin-right:8px}
.logo:hover{text-decoration:none}
nav{display:flex;gap:2px;flex-wrap:wrap}
nav a.t{color:var(--band-dim);padding:6px 10px;border-radius:var(--r-s);font-size:14px}
nav a.t:hover{color:var(--band-text);background:rgba(255,255,255,.08);text-decoration:none}
nav a.t.on{color:var(--band-text);box-shadow:inset 0 -2px 0 var(--accent)}
.right{margin-left:auto;display:flex;gap:8px;align-items:center}
.right input{font:inherit;font-size:14px;background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.16);
color:var(--band-text);padding:6px 10px;border-radius:var(--r-s);width:240px}
.right input::placeholder{color:var(--band-dim)}
.lang{border:1px solid rgba(255,255,255,.16);border-radius:var(--r-s);padding:5px 10px;color:var(--band-dim);font-size:13px;font-weight:500}
.lang:hover{color:var(--band-text);text-decoration:none;border-color:var(--accent)}
.sr{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap}
main{max-width:1280px;margin:0 auto;padding:24px 24px 48px}
main.narrow{max-width:880px}
h1{font-size:28px;margin:4px 0 18px}
h2{font-size:19px;margin:32px 0 12px}
.split{display:grid;grid-template-columns:minmax(0,1fr);gap:0 32px}
@media(min-width:1100px){.split{grid-template-columns:minmax(0,1.6fr) minmax(0,1fr)}}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(min(100%,320px),1fr));gap:10px}
.stack{display:flex;flex-direction:column;gap:10px}
.card{background:var(--card);border:1px solid var(--line);border-radius:var(--r-card);padding:14px 16px}
.card h3{margin:0 0 6px;font-size:16px;display:flex;gap:8px;align-items:center}.card p{margin:6px 0;color:var(--dim)}
.card h3 svg{flex:none;color:var(--dim)}
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:1px;background:var(--line);
border:1px solid var(--line);border-radius:var(--r-card);overflow:hidden}
.stat{background:var(--card);padding:14px 18px}
.stat b{display:block;font-size:32px;line-height:1.15;font-variant-numeric:tabular-nums}.stat span{color:var(--dim);font-size:13px}
.badge{display:inline-block;font-size:12px;font-weight:500;padding:1px 8px;border-radius:999px;background:var(--card2);
color:var(--dim);border:1px solid var(--line);margin:2px 4px 2px 0}
a.badge:hover{border-color:var(--accent);text-decoration:none}
.badge.g{color:var(--green)}.badge.a{color:var(--warn)}
.next{color:var(--text)!important;background:var(--card2);border-radius:var(--r-s);padding:6px 10px}
.tw{overflow-x:auto;border:1px solid var(--line);border-radius:var(--r-card)}
table{border-collapse:collapse;width:100%;background:var(--card)}
th,td{padding:8px 12px;border-top:1px solid var(--line);text-align:left;vertical-align:top}
th{color:var(--dim);font-weight:500;font-size:12px;background:var(--card2);border-top:0}
table.schedule td:first-child{white-space:nowrap}table.schedule td:nth-child(2){min-width:160px}
td.ok,td.no{position:relative}td.ok{color:var(--green);text-align:center}td.no{color:var(--faint);text-align:center}
.feed{border-left:2px solid var(--line);margin-left:4px}
.event{position:relative;padding:0 0 14px 18px}.event:before{content:"";position:absolute;left:-5px;top:7px;
width:8px;height:8px;border-radius:999px;background:var(--accent)}
.event small{color:var(--dim);font-variant-numeric:tabular-nums}.day{margin:20px 0 8px;color:var(--dim);font-weight:600}
.note{background:var(--card);border:1px solid var(--line);border-radius:var(--r-card);padding:8px 28px 24px}
.note h1{margin-top:16px}.note h2{font-size:20px}.note h3{font-size:16px}
.note p,.note li{max-width:75ch}
.note pre{background:var(--card2);padding:12px;border-radius:var(--r-s);overflow:auto}
.note blockquote{margin:8px 0;padding-left:12px;border-left:3px solid var(--line);color:var(--dim)}
code{background:var(--card2);padding:1px 5px;border-radius:4px;font:12.5px Consolas,"Cascadia Mono",ui-monospace,monospace}
.path{color:var(--dim);font-size:13px;margin:0 0 12px}
.bar{height:6px;background:var(--card2);border-radius:999px;overflow:hidden;margin-top:8px}
.bar i{display:block;height:100%;background:var(--accent)}
.filter{margin:0 0 14px;display:flex;gap:6px;flex-wrap:wrap}
footer{max-width:1280px;margin:0 auto;padding:16px 24px 28px;color:var(--dim);font-size:12px;border-top:1px solid var(--line)}
@media(max-width:640px){.band-in,main,footer{padding-left:16px;padding-right:16px}.right{margin-left:0;width:100%}
.right form{flex:1}.right input{width:100%}.note{padding:4px 16px 16px}}
@media(prefers-reduced-motion:no-preference){nav a.t,a.badge,.lang{transition:background-color 150ms,border-color 150ms,color 150ms}}
"""

FOLDER_SVG = ('<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
              'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
              '<path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/></svg>')
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


def layout(c: Ctx, title: str, body: str, active: str = "", narrow: bool = False) -> str:
    nav = "".join(f'<a class="t{" on" if href == active else ""}" href="{href}"'
                  f'{" aria-current=page" if href == active else ""}>{esc(label)}</a>'
                  for href, label, on in c.nav() if on)
    name = esc(c.cfg["dashboard"]["title"])
    other = "tr" if c.lang == "en" else "en"
    cls = ' class="narrow"' if narrow else ""
    return f"""<!doctype html><html lang="{c.lang}"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{esc(title)} · {name}</title>
<style>{CSS}</style></head><body><header class="band"><div class="band-in"><a class="logo" href="/">{name}</a>
<nav aria-label="{esc(c.t('nav_label'))}">{nav}</nav>
<div class="right"><form action="/search" role="search"><label class="sr" for="q">{esc(c.t('search'))}</label>
<input id="q" name="q" placeholder="{esc(c.t('search_ph'))}"></form>
<a class="lang" href="{esc(c.lang_url())}" hreflang="{other}" aria-label="{esc(c.t('lang_label'))}">{c.t('lang_other')}</a></div></div></header>
<main{cls}>{body}</main>
<footer>{esc(c.t('footer'))} · vault-dashboard {__version__}</footer></body></html>"""


def table(rows: list[list[str]], cls: str = "") -> str:
    if not rows:
        return ""
    head = "".join(f"<th>{inline(h)}</th>" for h in rows[0])
    body = "".join("<tr>" + "".join(f"<td>{inline(h)}</td>" for h in r) + "</tr>" for r in rows[1:])
    attr = f' class="{cls}"' if cls else ""
    return f'<div class="tw"><table{attr}><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'


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
    main_col, side = [], []
    if f["schedule"]:
        rows = v.upcoming_schedule()
        if rows:
            head = v.schedule()[0]
            main_col.append(f'<h2>{c.t("sec_schedule")}</h2>' + table([head] + rows[:c.cfg["schedule"]["limit"]], "schedule")
                         + f'<p class="path"><a href="{esc(note_link(c.cfg["schedule"]["file"]))}">{c.t("full_table")}</a></p>')
    if f["sessions"]:
        cards = "".join(f'<div class="card"><h3>{esc(h)}</h3><p>{inline(clip(b, 420))}</p></div>'
                        for h, b in v.sessions())
        if cards:
            main_col.append(f'<h2>{c.t("sec_sessions")}</h2><div class="stack">{cards}</div>')
    if f["tasks"]:
        cards = "".join(
            f'<div class="card"><h3><a href="{esc(note_link(t["path"]))}">{esc(t["title"])}</a></h3>'
            + (f'<span class="badge">{esc(t["project"])}</span>' if t["project"] else "")
            + f'<span class="badge a">{esc(t["status"])}</span>'
            + (f'<span class="badge">{c.t("due")}: {esc(t["due"])}</span>' if t["due"] else "") + "</div>"
            for t in tasks) or f'<p class="path">{c.t("no_tasks")}</p>'
        side.append(f'<h2>{c.t("sec_tasks")}</h2><div class="stack">{cards}</div>')
    if f["receipts"] and receipts:
        ev = "".join(f'<div class="event"><small>{c.date(r["time"])} {r["time"]:%H:%M}</small><br>'
                     f'{inline(clip(r["summary"], 240))}</div>' for r in receipts[:6])
        side.append(f'<h2>{c.t("sec_recent")}</h2><div class="feed">{ev}</div>'
                     f'<p class="path"><a href="/activity">{c.t("all_activity")}</a></p>')
    if main_col and side:
        parts.append(f'<div class="split"><div>{"".join(main_col)}</div>'
                     f'<aside aria-label="{esc(c.t("aside_label"))}">{"".join(side)}</aside></div>')
    else:
        parts.extend(main_col + side)
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
        cells = "".join(
            f'<td class="{"ok" if d else "no"}" title="{esc(s)}: {c.t("stage_yes" if d else "stage_no")}">'
            f'<span aria-hidden="true">{"●" if d else "○"}</span><span class="sr">{c.t("stage_yes" if d else "stage_no")}</span></td>'
            for s, d in zip(stages, i["done"]))
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
        body += f'<h2>{c.t("sec_schedule")}</h2>' + table(c.v.schedule(), "schedule")
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
                       f'<p class="path">{c.t("records", n=len(rs))}</p>{html}', "/activity", narrow=True)


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
                       f'<div class="note">{render(c.v.read(p))}</div>', narrow=True)


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
            cards += f'<div class="card"><h3>{FOLDER_SVG}<a href="{esc(folder_link(r))}">{esc(o.name)}</a></h3></div>'
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
