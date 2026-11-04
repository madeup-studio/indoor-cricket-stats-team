#!/usr/bin/env python3
"""Allowlist sanitiser for the coach letter's HTML — the Python twin of
viewer/sanitize.js (same rules, same test cases). Only bare formatting tags survive
(p b strong i em br ul ol li, no attributes); every other tag is dropped and any
other markup is escaped as text. Used where letters become HTML outside the app
(the PDF stat cards, printed by a headless browser).
"""
import re

ALLOWED = {"p", "b", "strong", "i", "em", "br", "ul", "ol", "li"}
TAG = re.compile(r"<(/?)([a-zA-Z][a-zA-Z0-9]*)\b[^>]*>")
ENTITY = re.compile(r"&(#\d+|#x[0-9a-fA-F]+|[a-zA-Z][a-zA-Z0-9]*);")


def _escape_text(s):
    out = []
    for i, c in enumerate(s):
        if c == "<":
            out.append("&lt;")
        elif c == ">":
            out.append("&gt;")
        elif c == "&":
            out.append("&" if ENTITY.match(s, i) else "&amp;")
        else:
            out.append(c)
    return "".join(out)


def safe_html(html):
    s = "" if html is None else str(html)
    out, last = [], 0
    for m in TAG.finditer(s):
        out.append(_escape_text(s[last:m.start()]))
        last = m.end()
        tag = m.group(2).lower()
        if tag not in ALLOWED:
            continue
        if tag == "br":
            if not m.group(1):
                out.append("<br>")
            continue
        out.append(f"<{m.group(1)}{tag}>")
    out.append(_escape_text(s[last:]))
    return "".join(out)
