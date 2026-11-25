"""A tiny, safe Markdown-to-HTML renderer (everything is escaped first)."""
from __future__ import annotations

import html
import re
from urllib.parse import quote

FRONTMATTER = re.compile(r"\A---\n(.*?)\n---\n?(.*)", re.S)


def esc(s: str) -> str:
    return html.escape(s, quote=True)


def wikilink_url(target: str) -> str:
    target = target.split("|")[0].split("#")[0].strip()
    if not target.endswith(".md"):
        target += ".md"
    return "/note?path=" + quote(target)


def inline(s: str) -> str:
    s = esc(s)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    s = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", s)
    s = re.sub(r"(?<![\w*])\*([^*\n]+)\*(?!\w)", r"<i>\1</i>", s)

    def wl(m: re.Match) -> str:
        raw = html.unescape(m.group(1))
        name = raw.split("|")[-1].split("/")[-1]
        return f'<a class="wl" href="{esc(wikilink_url(raw))}">{esc(name)}</a>'

    s = re.sub(r"\[\[([^\]]+)\]\]", wl, s)
    s = re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", r'<a href="\2" target="_blank" rel="noopener noreferrer">\1</a>', s)
    s = re.sub(r'(?<!["=>])(https?://[^\s<)]+)', r'<a href="\1" target="_blank" rel="noopener noreferrer">\1</a>', s)
    return s


def table_cells(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def table_rows(lines: list[str]) -> list[list[str]]:
    return [table_cells(s) for s in lines if not re.match(r"^\|[\s:|-]+\|$", s.strip())]


def table_html(lines: list[str]) -> str:
    rows = table_rows(lines)
    if not rows:
        return ""
    head = "".join(f"<th>{inline(c)}</th>" for c in rows[0])
    body = "".join("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>" for r in rows[1:])
    return f'<div class="tw"><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'


def render(md: str) -> str:
    md = FRONTMATTER.sub("", md, count=1) if md.startswith("---\n") else md
    out: list[str] = []
    in_list, table, code = False, [], None
    for line in md.splitlines():
        if code is not None:
            if line.startswith("```"):
                out.append("<pre>" + esc("\n".join(code)) + "</pre>")
                code = None
            else:
                code.append(line)
            continue
        if line.startswith("```"):
            code = []
            continue
        if line.strip().startswith("|"):
            table.append(line.strip())
            continue
        if table:
            out.append(table_html(table))
            table = []
        m = re.match(r"^\s*[-*] (.*)", line) or re.match(r"^\s*\d+\. (.*)", line)
        if m:
            if not in_list:
                out.append("<ul>")
                in_list = True
            item = re.sub(r"^\[( |x|X)\] ", lambda c: "☐ " if c.group(1) == " " else "☑ ", m.group(1))
            out.append("<li>" + inline(item) + "</li>")
            continue
        if in_list:
            out.append("</ul>")
            in_list = False
        h = re.match(r"^(#{1,4}) (.*)", line)
        if h:
            n = len(h.group(1))
            out.append(f"<h{n + 1}>{inline(h.group(2))}</h{n + 1}>")
        elif re.match(r"^(-{3,}|\*{3,})\s*$", line):
            out.append("<hr>")
        elif line.startswith(">"):
            out.append("<blockquote>" + inline(line.lstrip("> ")) + "</blockquote>")
        elif line.strip():
            out.append("<p>" + inline(line) + "</p>")
    if in_list:
        out.append("</ul>")
    if table:
        out.append(table_html(table))
    if code is not None:
        out.append("<pre>" + esc("\n".join(code)) + "</pre>")
    return "\n".join(out)
