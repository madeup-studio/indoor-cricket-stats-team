#!/usr/bin/env python3
"""Generate the shareable team season stats report (Markdown + HTML) from the
verified scorecards in .scorecards/. Run:  python scripts/generate_stats.py
Outputs stats/<season-slug>.md and .html (one pair per season)."""
import os, sys, re, datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import stats_core as S
import paths

TN = paths.TEAM_NAME   # our team, exactly as printed on the scorecards

SHOT_VALUES = [0, 1, 2, 3, 4, 5, 6, 7]
WKT_ORDER = ["caught", "bowled", "run out", "stumped", "lbw", "hit wicket", "mankad"]


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def big_hits(p):      # 5s + 7s (the bonus-zone shots)
    return p["shots"].get(5, 0) + p["shots"].get(7, 0)


def boundaries(p):    # 4s + 6s
    return p["shots"].get(4, 0) + p["shots"].get(6, 0)


def total_outs(p):
    return sum(p["outs"].values())


def stamp():
    # Date.now-free: use a fixed generation note; real date passed via env if set
    return os.environ.get("REPORT_DATE", datetime.date.today().isoformat())


# ─────────────────────────── Markdown ───────────────────────────
def render_md(season, s):
    t = s["team"]
    ours = S.player_rows(s["ours"])
    opps = S.player_rows(s["opp"])
    L = []
    L.append(f"# {TN} — {season} — Season Stats")
    L.append("")
    L.append(f"_Generated {stamp()} from {len(s['matches'])} scorecard(s). "
             f"Every figure reconciles to the official skin/run totals (ball-by-ball verified)._")
    L.append("")
    # glance
    rec = f"{t['w']}–{t['l']}" + (f"–{t['t']}" if t['t'] else "")
    L.append("## Season at a glance")
    L.append("")
    L.append(f"- **Record:** {rec} (W–L{'–T' if t['t'] else ''}) over {len(s['matches'])} matches")
    L.append(f"- **Skins:** {t['skins_for']} won / {t['skins_against']} lost")
    L.append(f"- **Runs:** {t['runs_for']} for / {t['runs_against']} against "
             f"({'+' if t['runs_for']>=t['runs_against'] else ''}{t['runs_for']-t['runs_against']} diff)")
    L.append("")
    # results
    L.append("## Match results")
    L.append("")
    L.append("| Date | Opponent | Result | Score | Skins | Player of the Match |")
    L.append("|------|----------|--------|-------|-------|---------------------|")
    for m in s["matches"]:
        res = {"win": "✅ Won", "loss": "❌ Lost", "tie": "➖ Tie"}[m["outcome"]]
        pom = f"{m['pom_display']} ({m['team'] if m['player_of_match_team']==m['team'] else m['opponent']})"
        L.append(f"| {m['date']} | {m['opponent']} | {res} | "
                 f"{m['team_total']}–{m['opponent_total']} | "
                 f"{m['team_skins_won']}–{m['opponent_skins_won']} | {pom} |")
    L.append("")
    # leaderboard
    L.append(f"## {TN} leaderboard — by contribution (RS − RC)")
    L.append("")
    L.append("| # | Player | M | RS | Wkts | RC | Econ | Contribution | Avg/match | POM |")
    L.append("|--:|--------|--:|---:|-----:|---:|-----:|-------------:|----------:|----:|")
    for i, (name, p) in enumerate(ours, 1):
        mp = len(p["matches"])
        avg = p["c"] / mp if mp else 0.0
        L.append(f"| {i} | {name} | {mp} | {p['rs']} | {p['wkts']} | {p['rc']} | "
                 f"{S.econ(p)} | {p['c']:+d} | {avg:+.1f} | {p['pom'] or ''} |")
    L.append("")
    # award leaders
    L.append("## Award leaders")
    L.append("")
    for label, key in [("🏆 Most valuable (contribution)", lambda p: p["c"]),
                       ("🏏 Top run scorer", lambda p: p["rs"]),
                       ("🎯 Top wicket-taker", lambda p: p["wkts"]),
                       ("💥 Biggest hitter (5s+7s)", big_hits)]:
        best = max(ours, key=lambda kv: key(kv[1]))
        val = key(best[1])
        L.append(f"- **{label}:** {best[0]} ({val})")
    thrifty = min([kv for kv in ours if kv[1]["ob"]], key=lambda kv: S.econ(kv[1]))
    L.append(f"- **🧤 Best economy:** {thrifty[0]} ({S.econ(thrifty[1])} runs/over)")
    ht = [(n, p) for n, p in ours if p["hattricks"]]
    if ht:
        L.append("- **🎩 Hattricks:** " + ", ".join(f"{n} ({p['hattricks']})" for n, p in ht))
    L.append("")
    # batting shot distribution
    L.append("## Batting — shot distribution")
    L.append("")
    L.append("_Count of scoring shots by value. 5s & 7s are the bonus-zone big hits._")
    L.append("")
    L.append("| Player | Balls faced | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | Boundaries (4/6) | Big hits (5/7) | Dismissals |")
    L.append("|--------|----:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|----|")
    for name, p in ours:
        cells = " | ".join(str(p["shots"].get(v, 0)) for v in SHOT_VALUES)
        outs = ", ".join(f"{v}×{k}" for k, v in p["outs"].most_common()) or "—"
        L.append(f"| {name} | {p['balls_faced']} | {cells} | {boundaries(p)} | {big_hits(p)} | {outs} |")
    L.append("")
    # bowling breakdown
    L.append("## Bowling — wickets & run breakdown")
    L.append("")
    L.append("_Wicket types credited to the bowler, and the runs they conceded per ball._")
    L.append("")
    L.append("| Player | Overs | RC | Wkts | caught | bowled | run out | stumped | dots | 1s | 2s | 3s+ | 4/6 | 5/7 | extras |")
    L.append("|--------|----:|---:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|")
    for name, p in ours:
        c = p["conceded"]
        threeplus = sum(v for k, v in c.items() if k >= 3 and k not in (4, 5, 6, 7))
        fb = c.get(4, 0) + c.get(6, 0)
        big = c.get(5, 0) + c.get(7, 0)
        wt = [p["wkt_types"].get(w, 0) for w in ["caught", "bowled", "run out", "stumped"]]
        L.append(f"| {name} | {p['ob']} | {p['rc']} | {p['wkts']} | "
                 f"{wt[0]} | {wt[1]} | {wt[2]} | {wt[3]} | "
                 f"{c.get(0,0)} | {c.get(1,0)} | {c.get(2,0)} | {threeplus} | {fb} | {big} | {p['extras_conceded']} |")
    L.append("")
    # hattricks
    ours_ht, opp_ht = S.all_hattricks(s["ours"]), S.all_hattricks(s["opp"])
    if ours_ht or opp_ht:
        L.append("## 🎩 Hattricks")
        L.append("")
        L.append("_3+ wickets on strictly consecutive deliveries by one bowler — any ball "
                 "in between, including a wide or no-ball, breaks the run. Marked when the "
                 "run spans the bowler's two overs, which are bowled at different times._")
        L.append("")
        for ev in ours_ht:
            L.append(f"- **{ev['date']}** — **{ev['bowler']}** ({TN}) vs {ev['opp']}: "
                     f"{'·'.join(ev['balls'])} — {', '.join(ev['victims'])}"
                     + (" _(across both overs)_" if ev["spans_overs"] else "")
                     + (f" — **{ev['n']} in {ev['n']}!**" if ev["n"] > 3 else ""))
        for ev in opp_ht:
            L.append(f"- {ev['date']} — {ev['bowler']} ({ev['opp']}) vs {TN}: "
                     f"{'·'.join(ev['balls'])} — {', '.join(ev['victims'])}"
                     + (" _(across both overs)_" if ev["spans_overs"] else ""))
        L.append("")
    # opponents to watch
    L.append("## 👀 Opponents to watch")
    L.append("")
    L.append("_Standout players we've faced, ranked by total contribution — know the danger men._")
    L.append("")
    L.append("| Player | Team(s) | M | RS | Wkts | Contribution | Big hits | POM |")
    L.append("|--------|---------|--:|---:|-----:|-------------:|---------:|----:|")
    for name, p in opps[:12]:
        teams = ", ".join(sorted(p.get("teams", [])))
        L.append(f"| {name} | {teams} | {len(p['matches'])} | {p['rs']} | {p['wkts']} | "
                 f"{p['c']:+d} | {big_hits(p)} | {p['pom'] or ''} |")
    L.append("")
    L.append("---")
    L.append("_Contribution (C) = Runs Scored − Runs Conceded, the game's own value metric. "
             "Dismissals cost the batting team 5 runs, so negative economy / conceded is elite bowling._")
    L.append("")
    return "\n".join(L)


# ─────────────────────────── HTML ───────────────────────────
WKT_COLOR = {"caught": "var(--s1)", "bowled": "var(--s2)", "run out": "var(--s3)",
             "stumped": "var(--s5)", "lbw": "var(--s6)", "hit wicket": "var(--s8)",
             "mankad": "var(--s7)"}


def shot_color(v):
    if v == 0: return "var(--muted)"
    if v in (1, 2, 3): return "var(--s1)"
    if v in (4, 6): return "var(--s2)"
    return "var(--s8)"   # 5, 7 big hits


def bar(pct, color):
    return (f'<span class="bar"><span class="fill" style="width:{pct:.0f}%;'
            f'background:{color}"></span></span>')


def diverging(c, maxabs):
    """Contribution bar diverging from a centre line."""
    if maxabs == 0: maxabs = 1
    pct = min(abs(c) / maxabs * 50, 50)
    side = "right" if c >= 0 else "left"
    color = "var(--good)" if c >= 0 else "var(--s6)"
    return (f'<span class="dv"><span class="dvfill" style="{side}:50%;width:{pct:.0f}%;'
            f'background:{color}"></span></span><span class="dvnum">{c:+d}</span>')


def esc(x):
    return str(x).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def render_html(season, s):
    t = s["team"]
    ours = S.player_rows(s["ours"])
    opps = S.player_rows(s["opp"])
    rec = f"{t['w']}–{t['l']}" + (f"–{t['t']}" if t['t'] else "")
    maxc = max((abs(p["c"]) for _, p in ours), default=1)
    max_shot = max((max(p["shots"].values(), default=0) for _, p in ours), default=1) or 1

    H = []
    H.append("<!doctype html><html lang='en'><head><meta charset='utf-8'>")
    H.append("<meta name='viewport' content='width=device-width, initial-scale=1'>")
    H.append(f"<title>{esc(TN)} — {esc(season)} stats</title>")
    H.append("<style>" + CSS + "</style></head><body><div class='wrap'>")
    # header
    H.append(f"<header><div><div class='eyebrow'>{esc(TN)} · {esc(paths.ARENA or 'Action Cricket')}</div>"
             f"<h1>{esc(season)}</h1></div>"
             f"<div class='rec'><span class='recnum'>{rec}</span>"
             f"<span class='reclbl'>W–L record</span></div></header>")
    # KPI tiles
    tiles = [("Matches", len(s["matches"]), ""),
             ("Skins", f"{t['skins_for']}–{t['skins_against']}", "won / lost"),
             ("Runs for", t["runs_for"], "scored"),
             ("Runs against", t["runs_against"], "conceded"),
             ("Run diff", f"{t['runs_for']-t['runs_against']:+d}", "")]
    H.append("<section class='tiles'>")
    for lbl, val, sub in tiles:
        H.append(f"<div class='tile'><div class='tval'>{esc(val)}</div>"
                 f"<div class='tlbl'>{esc(lbl)}</div><div class='tsub'>{esc(sub)}</div></div>")
    H.append("</section>")
    H.append(f"<p class='note'>Generated {esc(stamp())}. Every figure reconciles to the "
             "official skin totals — ball-by-ball verified.</p>")

    # results
    H.append("<h2>Match results</h2><div class='scroll'><table><thead><tr>"
             "<th>Date</th><th>Opponent</th><th>Result</th><th>Score</th><th>Skins</th>"
             "<th>Player of the Match</th></tr></thead><tbody>")
    for m in s["matches"]:
        cls = {"win": "win", "loss": "loss", "tie": "tie"}[m["outcome"]]
        res = {"win": "Won", "loss": "Lost", "tie": "Tie"}[m["outcome"]]
        pomteam = m["team"] if m["player_of_match_team"] == m["team"] else m["opponent"]
        H.append(f"<tr><td>{esc(m['date'])}</td><td>{esc(m['opponent'])}</td>"
                 f"<td><span class='pill {cls}'>{res}</span></td>"
                 f"<td class='num'>{m['team_total']}–{m['opponent_total']}</td>"
                 f"<td class='num'>{m['team_skins_won']}–{m['opponent_skins_won']}</td>"
                 f"<td>{esc(m['pom_display'])} <span class='muted'>({esc(pomteam)})</span></td></tr>")
    H.append("</tbody></table></div>")

    # award chips
    def leader(fn):
        b = max(ours, key=lambda kv: fn(kv[1])); return b[0], fn(b[1])
    thrifty = min([kv for kv in ours if kv[1]["ob"]], key=lambda kv: S.econ(kv[1]))
    awards = [("🏆", "Most valuable", *leader(lambda p: p["c"])),
              ("🏏", "Top run scorer", *leader(lambda p: p["rs"])),
              ("🎯", "Top wicket-taker", *leader(lambda p: p["wkts"])),
              ("💥", "Biggest hitter (5s+7s)", *leader(big_hits)),
              ("🧤", "Best economy", thrifty[0], f"{S.econ(thrifty[1])}/ov")]
    ht_takers = [(n, p) for n, p in ours if p["hattricks"]]
    if ht_takers:
        awards.append(("🎩", "Hattricks",
                       ", ".join(n for n, _ in ht_takers),
                       sum(p["hattricks"] for _, p in ht_takers)))
    H.append("<h2>Award leaders</h2><section class='awards'>")
    for emo, lbl, who, val in awards:
        H.append(f"<div class='award'><div class='aemo'>{emo}</div><div>"
                 f"<div class='awho'>{esc(who)}</div><div class='albl'>{esc(lbl)} · <b>{esc(val)}</b></div></div></div>")
    H.append("</section>")

    # leaderboard
    H.append(f"<h2>{esc(TN)} leaderboard</h2><p class='sub'>Ranked by contribution "
             "(Runs Scored − Runs Conceded).</p><div class='scroll'>"
             "<table><thead><tr><th>#</th><th>Player</th><th class='num'>M</th>"
             "<th class='num'>RS</th><th class='num'>Wkts</th><th class='num'>RC</th>"
             "<th class='num'>Econ</th><th>Contribution</th><th class='num'>POM</th></tr></thead><tbody>")
    for i, (name, p) in enumerate(ours, 1):
        H.append(f"<tr><td class='muted'>{i}</td><td class='pname'>{esc(name)}</td>"
                 f"<td class='num'>{len(p['matches'])}</td><td class='num'>{p['rs']}</td>"
                 f"<td class='num'>{p['wkts']}</td><td class='num'>{p['rc']}</td>"
                 f"<td class='num'>{S.econ(p)}</td><td class='dvcell'>{diverging(p['c'], maxc)}</td>"
                 f"<td class='num'>{'⭐'*p['pom']}</td></tr>")
    H.append("</tbody></table></div>")

    # batting shot distribution
    H.append("<h2>Batting — shot distribution</h2>"
             "<p class='sub'>Scoring shots by value. "
             "<span class='key'><i style='background:var(--s1)'></i>1–3</span>"
             "<span class='key'><i style='background:var(--s2)'></i>4/6</span>"
             "<span class='key'><i style='background:var(--s8)'></i>5/7 big hits</span>"
             "<span class='key'><i style='background:var(--muted)'></i>dot</span></p>")
    H.append("<section class='cards'>")
    for name, p in ours:
        if p["balls_faced"] == 0 and not p["outs"]:
            continue
        H.append(f"<div class='pcard'><div class='pcardhd'><b>{esc(name)}</b>"
                 f"<span class='muted'>{p['rs']} runs · {p['balls_faced']} balls</span></div>")
        H.append("<div class='shots'>")
        for v in SHOT_VALUES:
            n = p["shots"].get(v, 0)
            H.append(f"<div class='shotrow'><span class='sv'>{v}</span>"
                     f"{bar(n/max_shot*100, shot_color(v))}<span class='sn'>{n}</span></div>")
        H.append("</div>")
        outs = ", ".join(f"{v}× {k}" for k, v in p["outs"].most_common()) or "—"
        H.append(f"<div class='outs'><span class='muted'>Out:</span> {esc(outs)}</div></div>")
    H.append("</section>")

    # bowling
    H.append("<h2>Bowling — wickets & run breakdown</h2>"
             "<p class='sub'>Wicket types credited, and runs conceded per ball.</p><div class='scroll'>"
             "<table><thead><tr><th>Player</th><th class='num'>Ov</th><th class='num'>RC</th>"
             "<th class='num'>Wkts</th><th>Wicket types</th><th class='num'>dots</th>"
             "<th class='num'>1s</th><th class='num'>2s</th><th class='num'>3+</th>"
             "<th class='num'>4/6</th><th class='num'>5/7</th><th class='num'>xtr</th></tr></thead><tbody>")
    for name, p in ours:
        c = p["conceded"]
        threeplus = sum(v for k, v in c.items() if k >= 3 and k not in (4, 5, 6, 7))
        chips = "".join(
            f"<span class='wchip'><i style='background:{WKT_COLOR[w]}'></i>{p['wkt_types'][w]} {w}</span>"
            for w in WKT_ORDER if p["wkt_types"].get(w))
        H.append(f"<tr><td class='pname'>{esc(name)}</td><td class='num'>{p['ob']}</td>"
                 f"<td class='num'>{p['rc']}</td><td class='num'>{p['wkts']}</td>"
                 f"<td class='chips'>{chips or '—'}</td>"
                 f"<td class='num'>{c.get(0,0)}</td><td class='num'>{c.get(1,0)}</td>"
                 f"<td class='num'>{c.get(2,0)}</td><td class='num'>{threeplus}</td>"
                 f"<td class='num'>{c.get(4,0)+c.get(6,0)}</td><td class='num'>{c.get(5,0)+c.get(7,0)}</td>"
                 f"<td class='num'>{p['extras_conceded']}</td></tr>")
    H.append("</tbody></table></div>")

    # hattricks
    ours_ht, opp_ht = S.all_hattricks(s["ours"]), S.all_hattricks(s["opp"])
    if ours_ht or opp_ht:
        H.append("<h2>🎩 Hattricks</h2><p class='sub'>3+ wickets on strictly consecutive "
                 "deliveries by one bowler — any ball in between, including a wide or "
                 "no-ball, breaks the run. "
                 "&ldquo;across both overs&rdquo; = the run spans the bowler's two overs.</p>"
                 "<div class='scroll'><table><thead><tr><th>Date</th><th>Bowler</th>"
                 "<th>For</th><th>vs</th><th>Balls</th><th>Victims</th></tr></thead><tbody>")
        rows = [(ev, TN, ev["opp"]) for ev in ours_ht] + \
               [(ev, ev["opp"], TN) for ev in opp_ht]
        for ev, team, vs in sorted(rows, key=lambda r: r[0]["date"]):
            balls = "·".join(ev["balls"]) + (f" <b>({ev['n']} in {ev['n']}!)</b>" if ev["n"] > 3 else "")
            if ev["spans_overs"]:
                balls += " <span class='muted'>(across both overs)</span>"
            H.append(f"<tr><td>{esc(ev['date'])}</td><td class='pname'>{esc(ev['bowler'])}</td>"
                     f"<td>{esc(team)}</td><td>{esc(vs)}</td><td>{balls}</td>"
                     f"<td class='muted'>{esc(', '.join(ev['victims']))}</td></tr>")
        H.append("</tbody></table></div>")

    # opponents
    H.append("<h2>👀 Opponents to watch</h2><p class='sub'>Danger men we've faced, "
             "ranked by total contribution.</p><div class='scroll'>"
             "<table><thead><tr><th>Player</th><th>Team(s)</th><th class='num'>M</th>"
             "<th class='num'>RS</th><th class='num'>Wkts</th><th class='num'>Contribution</th>"
             "<th class='num'>Big hits</th><th class='num'>POM</th></tr></thead><tbody>")
    for name, p in opps[:12]:
        teams = ", ".join(sorted(p.get("teams", [])))
        H.append(f"<tr><td class='pname'>{esc(name)}</td><td class='muted'>{esc(teams)}</td>"
                 f"<td class='num'>{len(p['matches'])}</td><td class='num'>{p['rs']}</td>"
                 f"<td class='num'>{p['wkts']}</td><td class='num'><b>{p['c']:+d}</b></td>"
                 f"<td class='num'>{big_hits(p)}</td><td class='num'>{'⭐'*p['pom']}</td></tr>")
    H.append("</tbody></table></div>")

    H.append("<footer>Contribution = Runs Scored − Runs Conceded. A dismissal costs the "
             "batting team 5 runs, so a negative economy means elite bowling. "
             f"Generated by <code>generate_stats.py</code> from {len(s['matches'])} verified scorecards.</footer>")
    H.append("</div></body></html>")
    return "\n".join(H)


CSS = """
:root{--bg:#f9f9f7;--surface:#fcfcfb;--tp:#0b0b0b;--ts:#52514e;--muted:#898781;
--grid:#e1e0d9;--baseline:#c3c2b7;--border:rgba(11,11,11,.10);--good:#006300;
--s1:#2a78d6;--s2:#1baf7a;--s3:#eda100;--s5:#4a3aa7;--s6:#e34948;--s7:#e87ba4;--s8:#eb6834;}
@media(prefers-color-scheme:dark){:root{--bg:#0d0d0d;--surface:#1a1a19;--tp:#fff;
--ts:#c3c2b7;--muted:#898781;--grid:#2c2c2a;--baseline:#383835;--border:rgba(255,255,255,.10);
--good:#0ca30c;--s1:#3987e5;--s2:#199e70;--s3:#c98500;--s5:#9085e9;--s6:#e66767;--s7:#d55181;--s8:#d95926;}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--tp);
font-family:system-ui,-apple-system,"Segoe UI",sans-serif;line-height:1.5;font-size:15px}
.wrap{max-width:1000px;margin:0 auto;padding:28px 20px 60px}
header{display:flex;justify-content:space-between;align-items:flex-end;gap:16px;
border-bottom:2px solid var(--tp);padding-bottom:16px;margin-bottom:24px;flex-wrap:wrap}
.eyebrow{font-size:12px;letter-spacing:.08em;text-transform:uppercase;color:var(--muted);font-weight:600}
h1{margin:.1em 0 0;font-size:30px;letter-spacing:-.02em}
h2{margin:36px 0 6px;font-size:20px;letter-spacing:-.01em}
.rec{text-align:right}.recnum{font-size:34px;font-weight:700;display:block;line-height:1;font-variant-numeric:tabular-nums}
.reclbl{font-size:11px;text-transform:uppercase;letter-spacing:.06em;color:var(--muted)}
.sub{color:var(--ts);margin:.2em 0 12px;font-size:13.5px}
.note{color:var(--muted);font-size:12.5px;margin:14px 0 0}
.tiles{display:grid;grid-template-columns:repeat(5,1fr);gap:10px;margin:8px 0}
@media(max-width:640px){.tiles{grid-template-columns:repeat(2,1fr)}}
.tile{background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:14px}
.tval{font-size:24px;font-weight:700;font-variant-numeric:tabular-nums;letter-spacing:-.02em}
.tlbl{font-size:12px;font-weight:600;margin-top:2px}.tsub{font-size:11px;color:var(--muted)}
.scroll{overflow-x:auto;margin:6px 0}
table{border-collapse:collapse;width:100%;font-size:13.5px;background:var(--surface);
border:1px solid var(--border);border-radius:10px;overflow:hidden}
th,td{padding:8px 10px;text-align:left;border-bottom:1px solid var(--grid);white-space:nowrap}
thead th{background:color-mix(in srgb,var(--surface) 92%,var(--tp));font-size:11.5px;
text-transform:uppercase;letter-spacing:.04em;color:var(--ts);font-weight:700}
tbody tr:last-child td{border-bottom:none}
.num{text-align:right;font-variant-numeric:tabular-nums}
.pname{font-weight:600}.muted{color:var(--muted)}
.pill{display:inline-block;padding:2px 9px;border-radius:20px;font-size:11.5px;font-weight:700}
.pill.win{background:color-mix(in srgb,var(--good) 20%,transparent);color:var(--good)}
.pill.loss{background:color-mix(in srgb,var(--s6) 20%,transparent);color:var(--s6)}
.pill.tie{background:color-mix(in srgb,var(--muted) 22%,transparent);color:var(--ts)}
.dvcell{min-width:150px}.dv{position:relative;display:inline-block;width:120px;height:14px;
background:linear-gradient(var(--grid),var(--grid)) center/1px 100% no-repeat;vertical-align:middle}
.dvfill{position:absolute;top:2px;height:10px;border-radius:3px}
.dvnum{font-variant-numeric:tabular-nums;font-weight:600;margin-left:8px;font-size:12.5px}
.awards{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:10px}
.award{display:flex;gap:10px;align-items:center;background:var(--surface);
border:1px solid var(--border);border-radius:10px;padding:11px 13px}
.aemo{font-size:22px}.awho{font-weight:700}.albl{font-size:12px;color:var(--ts)}
.cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:12px}
.pcard{background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:12px 14px}
.pcardhd{display:flex;justify-content:space-between;align-items:baseline;gap:8px;
margin-bottom:8px;font-size:14px}.pcardhd .muted{font-size:11.5px}
.shots{display:flex;flex-direction:column;gap:3px}
.shotrow{display:flex;align-items:center;gap:7px}
.sv{width:12px;color:var(--muted);font-size:12px;text-align:right;font-variant-numeric:tabular-nums}
.sn{width:16px;font-size:12px;font-variant-numeric:tabular-nums}
.bar{flex:1;height:9px;background:color-mix(in srgb,var(--grid) 60%,transparent);border-radius:5px;overflow:hidden}
.fill{display:block;height:100%;border-radius:5px;min-width:2px}
.outs{margin-top:9px;font-size:12px;color:var(--ts);border-top:1px solid var(--grid);padding-top:7px}
.key{display:inline-flex;align-items:center;gap:4px;margin-left:10px;font-size:12px}
.key i{width:10px;height:10px;border-radius:3px;display:inline-block}
.chips{white-space:normal;min-width:200px}
.wchip{display:inline-flex;align-items:center;gap:5px;
background:color-mix(in srgb,var(--grid) 45%,transparent);color:var(--ts);
font-size:11px;font-weight:600;padding:2px 8px;border-radius:20px;margin:2px 3px 2px 0}
.wchip i{width:9px;height:9px;border-radius:50%;display:inline-block;flex:none}
footer{margin-top:40px;padding-top:16px;border-top:1px solid var(--grid);
color:var(--muted);font-size:12px}
code{background:color-mix(in srgb,var(--grid) 50%,transparent);padding:1px 5px;border-radius:4px;font-size:12px}
"""


def main():
    any_season = False
    for sd in paths.season_dirs():
        matches = S.load_matches(paths.cards_dir(sd))
        if not matches:
            continue
        any_season = True
        out = paths.stats_dir(sd)
        os.makedirs(out, exist_ok=True)
        for season, s in S.aggregate(matches).items():
            sl = slug(season)
            open(os.path.join(out, sl + ".md"), "w", encoding="utf-8").write(render_md(season, s))
            open(os.path.join(out, sl + ".html"), "w", encoding="utf-8").write(render_html(season, s))
            rel = os.path.relpath(out, paths.ROOT)
            print(f"wrote {rel}/{sl}.md and .html  ({len(s['matches'])} matches)")
    if not any_season:
        print("no transcribed scorecards found for team", paths.TEAM)


if __name__ == "__main__":
    main()
