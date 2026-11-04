#!/usr/bin/env python3
"""Read .scorecards/*.md and aggregate the team's season stats + opponent watchlist.
Shared by generate_stats.py (Markdown + HTML renderers)."""
import glob, os, re
from collections import Counter, defaultdict
from itertools import groupby
import yaml
import roster, paths

DISM = {"R": "run out", "C": "caught", "B": "bowled", "S": "stumped",
        "L": "lbw", "H": "hit wicket", "M": "mankad"}
EXTRAS = {"w": "wide", "nb": "no ball"}


def norm_ball(b):
    """Canonical ball token: ints untouched, dismissals upper, extras lower."""
    if isinstance(b, int):
        return b
    return b.upper() if b.upper() in DISM else b.lower()   # "w" is a wide, not a dismissal


def load_frontmatter(path):
    txt = open(path, encoding="utf-8").read()
    m = re.match(r"^---\n(.*?)\n---", txt, re.S)
    return yaml.safe_load(m.group(1))


def load_matches(cards_dir):
    ms = [load_frontmatter(p) for p in sorted(glob.glob(os.path.join(cards_dir, "*.md")))]
    return sorted(ms, key=lambda m: str(m["date"]))


def _new_player():
    return dict(matches=set(), rs=0, wkts=0, rc=0, c=0, ob=0, pom=0,
                best_c=None, worst_c=None,
                shots=Counter(), outs=Counter(), balls_faced=0,
                wkt_types=Counter(), conceded=Counter(),
                extras_conceded=0, balls_bowled=0,
                hattricks=0, hattrick_list=[])


def find_hattricks(over_seqs):
    """Hattrick events in one innings' delivery sequences (*_batting_seq):
    3+ wickets on consecutive deliveries by the same bowler. ANY other
    delivery in between — a scoring ball, dot, wide or no-ball — breaks the
    run; it may span the bowler's two overs, which in this format are
    separated in match time — flagged as spans_overs."""
    by_bowler = {}
    for e in over_seqs:
        by_bowler.setdefault(e["bowler"], []).append(e)
    events = []
    for bowler, overs in by_bowler.items():
        stream = [(norm_ball(b), name, i)
                  for i, e in enumerate(overs) for name, b in e["seq"]]
        for is_wkt, grp in groupby(stream,
                                   key=lambda t: isinstance(t[0], str) and t[0] in DISM):
            grp = list(grp)
            if is_wkt and len(grp) >= 3:
                events.append(dict(bowler=bowler, n=len(grp),
                                   balls=[t[0] for t in grp],
                                   victims=[t[1] for t in grp],
                                   spans_overs=len({t[2] for t in grp}) > 1))
    return events


def all_hattricks(pool):
    """Every hattrick event in a player pool, chronological."""
    return sorted((ev for _, p in pool.items() for ev in p["hattrick_list"]),
                  key=lambda e: e["date"])


def aggregate(matches):
    """Return (seasons -> {ours, opponents, team, matches})."""
    R = roster.load()          # {raw: confirmed name or None}
    rz = lambda n: roster.resolve(n, R)   # display/merge key = confirmed name or raw
    seasons = defaultdict(lambda: dict(
        ours=defaultdict(_new_player), opp=defaultdict(_new_player),
        matches=[], team=dict(w=0, l=0, t=0, skins_for=0, skins_against=0,
                              runs_for=0, runs_against=0)))

    for m in matches:
        s = seasons[m["season"]]
        s["matches"].append(m)
        date, opp_name = str(m["date"]), m["opponent"]

        # team record
        t = s["team"]
        t["w"] += m["outcome"] == "win"
        t["l"] += m["outcome"] == "loss"
        t["t"] += m["outcome"] == "tie"
        t["skins_for"] += m["team_skins_won"]
        t["skins_against"] += m["opponent_skins_won"]
        t["runs_for"] += m["team_total"]
        t["runs_against"] += m["opponent_total"]

        # summary rows -> our team & opponents
        for row in m["team_summary"]:
            _accum_summary(s["ours"][rz(row["name"])], row, date, opp_name)
        for row in m["opponent_summary"]:
            _accum_summary(s["opp"][rz(row["name"])], row, date, m["team"])
            s["opp"][rz(row["name"])].setdefault("teams", set()).add(opp_name)

        # player of match
        m["pom_display"] = rz(m["player_of_match"])   # confirmed name for display
        if m["player_of_match_team"] == m["team"]:
            s["ours"][rz(m["player_of_match"])]["pom"] += 1
        else:
            s["opp"][rz(m["player_of_match"])]["pom"] += 1

        bbb = m.get("ball_by_ball", {})
        if bbb.get("status") != "verified":
            continue
        # batting detail
        _accum_batting(s["ours"], bbb.get("team_batting", []), rz)
        _accum_batting(s["opp"], bbb.get("opponent_batting", []), rz)
        # bowling detail: our bowlers appear in opponent_batting overs
        _accum_bowling(s["ours"], bbb.get("opponent_batting", []), rz)
        _accum_bowling(s["opp"], bbb.get("team_batting", []), rz)
        # hattricks (needs the delivery sequences)
        for seq_key, pool in [("opponent_batting_seq", s["ours"]),
                              ("team_batting_seq", s["opp"])]:
            for ev in find_hattricks(bbb.get(seq_key) or []):
                p = pool[rz(ev["bowler"])]
                p["hattricks"] += 1
                p["hattrick_list"] = p["hattrick_list"] + [dict(
                    ev, bowler=rz(ev["bowler"]), date=date, opp=opp_name,
                    victims=[rz(v) for v in ev["victims"]])]

    return seasons


def _accum_summary(p, row, date, opp):
    p["matches"].add(date)
    for k in ("rs", "wkts", "rc", "c", "ob"):
        p[k] += row[k]
    tag = (row["c"], date, opp)
    if p["best_c"] is None or row["c"] > p["best_c"][0]:
        p["best_c"] = tag
    if p["worst_c"] is None or row["c"] < p["worst_c"][0]:
        p["worst_c"] = tag


def _accum_batting(pool, batting, rz=lambda n: n):
    for bat in batting:
        p = pool[rz(bat["name"])]
        for over in bat["overs"]:
            for b in map(norm_ball, over["balls"]):
                p["balls_faced"] += 1   # every cell = one delivery (extras included)
                if isinstance(b, int):
                    p["shots"][b] += 1
                elif b in DISM:
                    p["outs"][DISM[b]] += 1


def _accum_bowling(pool, batting, rz=lambda n: n):
    for bat in batting:
        for over in bat["overs"]:
            p = pool[rz(over["bowler"])]
            for b in map(norm_ball, over["balls"]):
                p["balls_bowled"] += 1   # every cell = one delivery (extras included)
                if isinstance(b, int):
                    p["conceded"][b] += 1
                elif b in DISM:
                    p["wkt_types"][DISM[b]] += 1
                elif b in EXTRAS:
                    p["extras_conceded"] += 1


def player_rows(pool):
    """Sorted list of (name, p) for a pool, best contribution first."""
    return sorted(pool.items(), key=lambda kv: (-kv[1]["c"], -kv[1]["rs"]))


def econ(p):
    return round(p["rc"] / p["ob"], 2) if p["ob"] else 0.0
