#!/usr/bin/env python3
"""Assemble a self-contained <season>/scorecards/<date>-<team>-vs-<opp>.md (meta + summary +
embedded verified ball-by-ball + human-readable body) from the single combined
per-game source file data/<date>.json.

data/<date>.json is the SOURCE OF TRUTH per game (both teams, both innings in
batting order). Re-run this after editing it:  python scripts/build_scorecards.py
"""
import json, glob, os, re
import paths, rules


def q(s):
    return '"%s"' % str(s).replace('"', '\\"')

def num(v):
    if v is None: return "null"
    if isinstance(v, float) and v.is_integer(): return str(v)
    return str(v)

def ball_tok(b):
    return str(b) if isinstance(b, int) else q(b)

def fmt_over(o):
    balls = ", ".join(ball_tok(b) for b in o["balls"])
    return "{bowler: %s, balls: [%s], total: %d}" % (q(o["bowler"]), balls, o["total"])

def fmt_summary(r):
    return ("{name: %s, skin: %s, rs: %d, ob: %d, rc: %d, wkts: %d, econ: %s, c: %d}"
            % (q(r["name"]), r.get("skin"), r["rs"], r["ob"], r["rc"],
               r["wkts"], num(r["econ"]), r["c"]))

def fmt_seqover(e):
    seq = ", ".join("[%s, %s]" % (q(n), ball_tok(b)) for n, b in e["seq"])
    return "{skin: %d, bowler: %s, seq: [%s]}" % (e["skin"], q(e["bowler"]), seq)


def seq_yaml(over_seq):
    return "\n".join("    - %s" % fmt_seqover(e) for e in over_seq)


def render_seq_lines(inn):
    """Per-skin delivery order; the pair's second-listed batter shown in italics."""
    first_of_skin = {}
    for bat in inn["batting"]:
        first_of_skin.setdefault(bat["skin"], bat["name"])
    lines = []
    cur_skin = None
    for e in inn["over_seq"]:
        if e["skin"] != cur_skin:
            cur_skin = e["skin"]
            pair = [b["name"] for b in inn["batting"] if b["skin"] == cur_skin]
            lines.append("- **Skin %d** — %s / *%s*" % (cur_skin, pair[0], pair[1] if len(pair) > 1 else "?"))
        balls = " ".join(str(b) if n == first_of_skin[e["skin"]] else "*%s*" % b
                         for n, b in e["seq"])
        lines.append("  - %s: %s" % (e["bowler"], balls))
    return "\n".join(lines)


def batting_yaml(batting):
    out = []
    for bat in batting:
        out.append("    - name: %s" % q(bat["name"]))
        out.append("      skin: %d" % bat["skin"])
        out.append("      rs: %d" % bat["rs"])
        out.append("      overs:")
        for o in bat["overs"]:
            out.append("        - %s" % fmt_over(o))
    return "\n".join(out)

def order_summary(summary, batting):
    """Reorder/re-skin summary rows to match the ball-by-ball batting order."""
    skin_of = {b["name"]: b["skin"] for b in batting}
    order = {b["name"]: i for i, b in enumerate(batting)}
    rows = [dict(r) for r in summary]
    for r in rows:
        if r["name"] in skin_of:
            r["skin"] = skin_of[r["name"]]
    rows.sort(key=lambda r: order.get(r["name"], 99))
    return rows

def render_bbb_lines(batting):
    lines = []
    for bat in batting:
        overs = "  ".join(
            "%s [%s]=%d" % (o["bowler"], ", ".join(str(b) for b in o["balls"]), o["total"])
            for o in bat["overs"])
        lines.append("- **%s** (%d): %s" % (bat["name"], bat["rs"], overs))
    return "\n".join(lines)

def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def build(game, out_dir):
    d, meta, res = game["date"], game["meta"], game["result"]
    team, opp = game["team"], game["opponent"]
    ours_inn = next(i for i in game["innings"] if i["batting_team"] == team)
    opp_inn = next(i for i in game["innings"] if i["batting_team"] == opp)
    ours_sum = order_summary(game["summaries"][team], ours_inn["batting"])
    opp_sum = order_summary(game["summaries"][opp], opp_inn["batting"])
    outcome_word = {"win": "won", "loss": "lost", "tie": "tied"}[res["outcome"]]
    wr = rules.game_rules(game, paths.RULES)["wicket_runs"]      # this game's dismissal value
    wr_txt = ("−%d" % -wr) if wr < 0 else "%+d" % wr        # e.g. −5 (typographic minus)
    # arena = the venue that runs the leagues (e.g. Example Arena);
    # league = the ability tier, e.g. "Mens E" (promotion/relegation between them).
    if "arena" in meta:
        arena, league = meta["arena"], meta["league"]
    else:   # older files: league held the arena name, division the tier
        arena, league = meta["league"], meta["division"]

    F = ["---", "# Match meta", "date: %s" % d, "time: %s" % q(meta["time"]),
         "season: %s" % q(meta["season"]), "arena: %s" % arena,
         "league: %s" % league, "umpire: %s" % meta["umpire"],
         "court: %s" % (q(meta["court"]) if meta.get("court") else "null"),
         "venue: %s" % (q(meta["venue"]) if meta.get("venue") else "null"),
         "source_image: %s" % meta["source_image"],
         *(["stage: %s" % meta["stage"]] if meta.get("stage") else []), "",
         "# Teams & result (innings order: 1=%s batted first)" % game["innings"][0]["batting_team"],
         "team: %s" % team, "opponent: %s" % q(opp), "outcome: %s" % res["outcome"]]
    for k in ["team_total", "team_skins_won", "opponent_total", "opponent_skins_won"]:
        F.append("%s: %d" % (k, res[k]))
    F.append("team_skins: [%s]" % ", ".join(map(str, res["team_skins"])))
    F.append("opponent_skins: [%s]" % ", ".join(map(str, res["opponent_skins"])))
    F.append("player_of_match: %s" % q(res["player_of_match"]))
    F.append("player_of_match_team: %s" % q(res["player_of_match_team"]))
    F.append("")
    F.append("# Clean summary stats (VALIDATED to team/skin totals; C = RS - RC)")
    F.append("team_summary:")
    F += ["  - %s" % fmt_summary(r) for r in ours_sum]
    F.append("opponent_summary:")
    F += ["  - %s" % fmt_summary(r) for r in opp_sum]
    F.append("")
    F.append("# Ball-by-ball (VERIFIED: checksums reconcile). balls: int=runs off bat,")
    F.append("# R/C/B/S/L/H/M = dismissal (%d): run out/caught/bowled/stumped/lbw/hit wkt/mankad; w/nb = extras." % wr)
    F.append("# *_batting_seq (when present) = exact delivery order per over: [batter, ball] pairs.")
    F += ["ball_by_ball:", "  status: verified", "  team_batting:",
          batting_yaml(ours_inn["batting"]), "  opponent_batting:",
          batting_yaml(opp_inn["batting"])]
    if ours_inn.get("over_seq"):
        F += ["  team_batting_seq:", seq_yaml(ours_inn["over_seq"])]
    if opp_inn.get("over_seq"):
        F += ["  opponent_batting_seq:", seq_yaml(opp_inn["over_seq"])]
    F.append("---")

    B = ["", "# %s vs %s — %s" % (team, opp, d), "",
         "**Result:** %s %s **%d–%d** (%d skins to %d) · **Player of the Match:** %s (%s)"
         % (team, outcome_word, res["team_total"], res["opponent_total"], res["team_skins_won"],
            res["opponent_skins_won"], res["player_of_match"], res["player_of_match_team"]),
         "Arena: %s · League: %s · %s · Umpire: %s" % (arena, league, meta["season"], meta["umpire"]), "",
         "## Skins", "",
         "| Team | Skin 1 | Skin 2 | Skin 3 | Skin 4 | Total | Skins |",
         "|------|-------:|-------:|-------:|-------:|------:|------:|",
         "| **%s** | %s | **%d** | **%d** |" % (team, " | ".join(map(str, res["team_skins"])),
                                                 res["team_total"], res["team_skins_won"]),
         "| %s | %s | %d | %d |" % (opp, " | ".join(map(str, res["opponent_skins"])),
                                    res["opponent_total"], res["opponent_skins_won"]), ""]
    for title, rows in [("%s players" % team, ours_sum), ("%s players" % opp, opp_sum)]:
        B += ["## %s" % title, "",
              "| # | Player | Skin | RS | OB | RC | Wkts | Econ | Contribution |",
              "|--:|--------|-----:|---:|---:|---:|-----:|-----:|-------------:|"]
        for i, r in enumerate(rows, 1):
            B.append("| %d | %s | %s | %d | %d | %d | %d | %s | %d |"
                     % (i, r["name"], r.get("skin", ""), r["rs"], r["ob"], r["rc"],
                        r["wkts"], num(r["econ"]), r["c"]))
        B.append("")
    B += ["## Ball-by-ball", "",
          "_Format: `Bowler [balls]=over total`. Dismissals worth %s: "
          "R=run out, C=caught, B=bowled, S=stumped, L=lbw, H=hit wicket, M=mankad; w/nb=extras._" % wr_txt, "",
          "**%s batting**" % team, "", render_bbb_lines(ours_inn["batting"]), "",
          "**%s batting**" % opp, "", render_bbb_lines(opp_inn["batting"]), ""]
    for label, inn in [(team, ours_inn), (opp, opp_inn)]:
        if inn.get("over_seq"):
            B += ["## %s delivery sequence" % label, "",
                  "_Every ball in the order bowled; the pair's second batter in italics._", "",
                  render_seq_lines(inn), ""]

    fname = "%s-%s-vs-%s.md" % (d, slug(team), slug(opp))
    path = os.path.join(out_dir, fname)
    open(path, "w", encoding="utf-8").write("\n".join(F) + "\n" + "\n".join(B))
    print("built", os.path.relpath(path, paths.ROOT),
          "| team", len(ours_sum), "opp", len(opp_sum),
          "| innings", [i["batting_team"] for i in game["innings"]])


if __name__ == "__main__":
    for sd in paths.season_dirs():
        out = paths.cards_dir(sd)
        os.makedirs(out, exist_ok=True)
        for jf in sorted(glob.glob(os.path.join(paths.data_dir(sd), "*.json"))):
            build(json.load(open(jf, encoding="utf-8")), out)
