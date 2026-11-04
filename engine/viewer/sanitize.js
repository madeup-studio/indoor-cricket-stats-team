// Allowlist sanitiser for the coach letter's HTML (written by an AI from the team's
// data and notes). Only bare formatting tags survive — no attributes, no links, no
// media; every other tag is dropped and any other markup is escaped as text.
// String-level and pure (no DOM), so it is unit-tested and behaves the same everywhere.

const ALLOWED = new Set(["p", "b", "strong", "i", "em", "br", "ul", "ol", "li"]);
const TAG = /<(\/?)([a-zA-Z][a-zA-Z0-9]*)\b[^>]*>/g;
const ENTITY = /^&(#\d+|#x[0-9a-fA-F]+|[a-zA-Z][a-zA-Z0-9]*);/;

function escapeText(s) {
  let out = "";
  for (let i = 0; i < s.length; i++) {
    const c = s[i];
    if (c === "<") out += "&lt;";
    else if (c === ">") out += "&gt;";
    else if (c === "&") out += ENTITY.test(s.slice(i)) ? "&" : "&amp;";
    else out += c;
  }
  return out;
}

export function safeHtml(html) {
  const s = String(html ?? "");
  let out = "", last = 0, m;
  TAG.lastIndex = 0;
  while ((m = TAG.exec(s))) {
    out += escapeText(s.slice(last, m.index));
    last = TAG.lastIndex;
    const tag = m[2].toLowerCase();
    if (!ALLOWED.has(tag)) continue;
    if (tag === "br") { if (!m[1]) out += "<br>"; continue; }
    out += `<${m[1]}${tag}>`;
  }
  return out + escapeText(s.slice(last));
}
