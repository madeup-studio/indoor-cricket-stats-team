#!/usr/bin/env python3
"""Aggregate the team's stats for the PDF dashboard.

Produces, for a given list of match dicts (already name-resolved at render time):
  team        - record, avg scores, high/low team score
  batting     - per-player batting incl. avg per 12 balls (2 overs)
  bowling     - per-player bowling incl. econ, wicket types, best figures
  allround    - per-player avg contribution (RS - RC) per game
  partnerships- 2-batsman skin partnerships (avg combined runs)
  opponents   - 'against us' records: top/bottom team scores, best opp bat & bowl figures
  records     - single-game bests for the batting / bowling pages

Two scopes are built by the renderer: current season and all-time.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from collections import defaultdict, Counter
import stats_core as S
import roster, paths

DISM = S.DISM  # {"R":"run out", "C":"caught", ...}
MIN_GAMES = 3       # ranked partnerships (games together) + season all-rounders
MIN_AR_ALLTIME = 10  # all-time all-rounder ranking needs a bigger sample
MIN_BALLS = 24  # ~4 overs faced before an avg/12 qualifies for the record


def _balls_shots_outs(overs):
    """Balls faced, scoring-shot counter, dismissals BY TYPE, extras faced.
    EVERY cell on the card is one delivery of a 6-ball over — wides/no-balls are
    NOT re-bowled in action cricket, so they count as balls faced (user-confirmed
    2026-09-22: a pair faces 24 balls per skin, 25 with the optional extra ball)."""
    balls = ext = 0
    shots, outs = Counter(), Counter()
    for ov in overs:
        for b in ov["balls"]:
            balls += 1
            if isinstance(b, int):
                shots[b] += 1
            elif b in DISM:
                outs[DISM[b]] += 1
            else:
                ext += 1
    return balls, shots, outs, ext


def build(matches, R, alltime=False, _nested=False):
    """_nested guards the one-level recursion used for prev_ranks (stats rebuilt
    without the newest game, so the coach notes can spot rank movement)."""
    rz = lambda n: roster.resolve(n, R)
    min_ar = MIN_AR_ALLTIME if alltime else MIN_GAMES   # all-rounder ranking threshold
    # Official batting/bowling list needs a minimum sample: 3 games in a season,
    # 10 across a career (all-time). Below that a player is shown but not ranked.
    min_rank = MIN_AR_ALLTIME if alltime else MIN_GAMES

    team = dict(played=0, won=0, lost=0, drawn=0, runs_for=0, runs_against=0,
                skins_for=0, skins_against=0, skins_drawn=0, games=[])
    bat = defaultdict(lambda: dict(name="", games=0, rs=0, balls=0, outs=0, ext_faced=0,
                                   shots=Counter(), outs_by_type=Counter(), hs=None, ls=None))
    bowl = defaultdict(lambda: dict(name="", games=0, ob=0, rc=0, wkts=0,
                                    wkt_types=Counter(), best=None, balls_bowled=0,
                                    extras=Counter(), hattricks=0))
    allr = defaultdict(lambda: dict(name="", games=0, c=0))
    partners = defaultdict(lambda: dict(games=0, total=0, best=None, skins_won=0))
    opp_team, opp_bat, opp_bowl = [], [], []
    game_contribs = []    # (contribution, name, opp, date) for every one of our player-games
    partner_games = []    # (combined runs, nameA, nameB, opp, date) per skin partnership
    score_games = []      # (rs, times_out, name, opp, date)  single-game batting scores
    seven_games = []      # (count of 7s, name, opp, date)     per game
    runout_games = []     # (count of run-outs, name, opp, date) per game
    skin_defence = []     # (opp skin score, opp, date, [(bowler, wkts, rc), ...]) per skin
    hattricks = []        # every hat-trick event, chronological (bowler, n, victims, opp, date)
    glog = defaultdict(list)  # per-player chronological game log (feeds player pages)

    for m in matches:
        date, opp = str(m["date"]), m["opponent"]
        oc = m["outcome"]
        team["played"] += 1
        team["won"] += oc == "win"
        team["lost"] += oc == "loss"
        team["drawn"] += oc == "tie"
        tf, ta = m["team_total"], m["opponent_total"]
        team["runs_for"] += tf
        team["runs_against"] += ta
        # Skins W-L-D by actual per-skin score (a level skin = draw, even though the
        # arena awards a tied skin to one side on wickets — see 2026-03-05 skin 2 = 21-21).
        for a, o in zip(m.get("team_skins") or [], m.get("opponent_skins") or []):
            if a > o:
                team["skins_for"] += 1
            elif a < o:
                team["skins_against"] += 1
            else:
                team["skins_drawn"] += 1
        # actual player of the match (either side) + our top contributor of the game —
        # both feed the coach notes ("the award vs what the spreadsheet says")
        pom_raw = m.get("player_of_match")
        top = max(m["team_summary"], key=lambda r: r["c"], default=None)
        team["games"].append(dict(date=date, opp=opp, total=tf, against=ta, outcome=oc,
                                  skins=m["team_skins_won"], oskins=m["opponent_skins_won"],
                                  skin_scores=list(zip(m.get("team_skins") or [],
                                                       m.get("opponent_skins") or [])),
                                  pom=rz(pom_raw) if pom_raw else None,
                                  pom_ours=m.get("player_of_match_team") == m.get("team"),
                                  top_c=(rz(top["name"]), top["c"]) if top else None))
        opp_team.append((ta, opp, date))

        # ---- ball-by-ball detail (verified) ----
        bbb = m.get("ball_by_ball", {})
        detail = {}
        ext_game = Counter()   # bowler -> wides+no-balls this game (feeds the game log)
        if bbb.get("status") == "verified":
            for bt in bbb.get("team_batting", []):
                b, sh, o, ex = _balls_shots_outs(bt["overs"])
                detail[rz(bt["name"])] = (b, sh, o, ex)
            # our bowlers' wicket types live in the opponents' batting overs
            for bt in bbb.get("opponent_batting", []):
                for ov in bt["overs"]:
                    nb = rz(ov["bowler"])
                    for b in ov["balls"]:
                        bowl[nb]["balls_bowled"] += 1   # every cell is one delivery
                        if b in DISM:
                            bowl[nb]["wkt_types"][DISM[b]] += 1
                        elif b in S.EXTRAS:                 # wides / no balls conceded
                            bowl[nb]["extras"][S.EXTRAS[b]] += 1
                            ext_game[nb] += 1
            # hat-tricks: 3+ wickets on consecutive deliveries (needs the delivery seq)
            for ev in S.find_hattricks(bbb.get("opponent_batting_seq") or []):
                nb = rz(ev["bowler"])
                bowl[nb]["hattricks"] += 1
                hattricks.append(dict(bowler=nb, n=ev["n"], opp=opp, date=date,
                                      victims=[rz(v) for v in ev["victims"]],
                                      spans_overs=ev["spans_overs"]))
            # per-skin defence: the opponent's score in each skin, plus each of our bowlers'
            # figures for that skin (wkts, net runs conceded). Feeds the 'best skin' record.
            opp_by_skin = defaultdict(list)
            for bt in bbb.get("opponent_batting", []):
                opp_by_skin[bt.get("skin")].append(bt)
            for sk, bats in opp_by_skin.items():
                if sk is None:
                    continue
                skin_score = sum(bt.get("rs", 0) for bt in bats)
                figs = defaultdict(lambda: [0, 0])   # bowler -> [wkts, runs conceded]
                for bt in bats:
                    for ov in bt["overs"]:
                        nb = rz(ov["bowler"])
                        figs[nb][1] += ov.get("total", 0)
                        for b in ov["balls"]:
                            if b in DISM:
                                figs[nb][0] += 1
                fig_list = sorted(((nm, wr[0], wr[1]) for nm, wr in figs.items()),
                                  key=lambda t: (-t[1], t[2]))   # most wkts, then fewest runs
                skin_defence.append((skin_score, opp, date, fig_list))
            # partnerships: two of our batters sharing a skin
            team_sk, opp_sk = m.get("team_skins") or [], m.get("opponent_skins") or []
            byskin = defaultdict(list)
            for bt in bbb.get("team_batting", []):
                byskin[bt.get("skin")].append((rz(bt["name"]), bt.get("rs", 0)))
            for sk, mem in byskin.items():
                if len(mem) >= 2:
                    mem = sorted(mem)[:2]
                    key = (mem[0][0], mem[1][0])
                    combined = mem[0][1] + mem[1][1]
                    p = partners[key]
                    p["games"] += 1
                    p["total"] += combined
                    # skin won if our pair outscored the opponent pair in that same skin
                    if isinstance(sk, int) and 1 <= sk <= len(team_sk) and sk <= len(opp_sk):
                        if team_sk[sk - 1] > opp_sk[sk - 1]:
                            p["skins_won"] += 1
                    if p["best"] is None or combined > p["best"][0]:
                        p["best"] = (combined, opp, date)
                    partner_games.append((combined, key[0], key[1], opp, date))

        # ---- summaries (authoritative) ----
        for row in m["team_summary"]:
            nm = rz(row["name"])
            b = bat[nm]
            b["name"] = nm
            b["games"] += 1
            b["rs"] += row["rs"]
            g_outs = g_balls = g_ro = g_dot = 0
            if nm in detail:
                nb, sh, oc, ex = detail[nm]
                b["balls"] += nb
                b["ext_faced"] += ex
                b["shots"] += sh
                b["outs_by_type"] += oc
                g_outs = sum(oc.values())
                g_balls = nb
                g_ro = oc.get("run out", 0)
                g_dot = sh.get(0, 0)
                b["outs"] += g_outs
                seven_games.append((sh.get(7, 0), nm, opp, date))
                runout_games.append((oc.get("run out", 0), nm, opp, date))
            score_games.append((row["rs"], g_outs, g_balls, nm, opp, date))
            if b["hs"] is None or row["rs"] > b["hs"][0]:
                b["hs"] = (row["rs"], g_outs, g_balls, opp, date)
            if b["ls"] is None or row["rs"] < b["ls"][0]:
                b["ls"] = (row["rs"], g_outs, g_balls, opp, date)

            w = bowl[nm]
            w["name"] = nm
            w["games"] += 1
            w["ob"] += row["ob"]
            w["rc"] += row["rc"]
            w["wkts"] += row["wkts"]
            fig = (row["wkts"], -row["rc"])   # more wkts, then fewer runs
            if w["best"] is None or fig > w["best"][0]:
                w["best"] = (fig, row["wkts"], row["rc"], opp, date)

            a = allr[nm]
            a["name"] = nm
            a["games"] += 1
            a["c"] += row["c"]
            game_contribs.append((row["c"], nm, opp, date))
            glog[nm].append(dict(date=date, opp=opp, rs=row["rs"], outs=g_outs,
                                 balls=g_balls, ro=g_ro, dot=g_dot, ob=row["ob"],
                                 rc=row["rc"], wkts=row["wkts"], c=row["c"],
                                 ext=ext_game.get(nm, 0)))

        for row in m["opponent_summary"]:
            opp_bat.append((row["rs"], rz(row["name"]), opp, date))
            opp_bowl.append((row["wkts"], row["rc"], rz(row["name"]), opp, date))

    # ---- finalize team ----
    n = team["played"] or 1
    team["avg_for"] = team["runs_for"] / n
    team["avg_against"] = team["runs_against"] / n
    team["avg_margin"] = team["avg_for"] - team["avg_against"]
    team["win_pct"] = 100.0 * team["won"] / n
    gs = team["games"]
    team["high_score"] = max(gs, key=lambda g: g["total"]) if gs else None
    team["low_score"] = min(gs, key=lambda g: g["total"]) if gs else None

    # ---- batting ----
    batting = []
    for b in bat.values():
        avg12 = (b["rs"] / b["balls"] * 12) if b["balls"] else 0.0
        sr = (b["rs"] / b["balls"] * 100) if b["balls"] else 0.0   # runs per 100 balls
        batting.append(dict(name=b["name"], games=b["games"], rs=b["rs"], balls=b["balls"],
                            ext=b["ext_faced"],
                            avg12=avg12, sr=sr, outs=b["outs"], shots=b["shots"],
                            outs_by_type=b["outs_by_type"],
                            s5=b["shots"].get(5, 0), s7=b["shots"].get(7, 0),
                            s4=b["shots"].get(4, 0), s6=b["shots"].get(6, 0),
                            hs=b["hs"], ls=b["ls"]))
    # Rank by Avg/12 (best first). Sub-threshold players (< min_rank games) sink to
    # the bottom, grouped by games desc (…2-game then 1-game), each still by avg.
    for b in batting:
        b["ranked"] = b["games"] >= min_rank
    batting.sort(key=lambda x: (not x["ranked"],
                                (-x["games"] if not x["ranked"] else 0),
                                -x["avg12"], -x["rs"]))

    # ---- bowling ----
    bowling = []
    for w in bowl.values():
        econ = (w["rc"] / w["ob"]) if w["ob"] else 0.0
        # bowling strike rate = balls bowled per wicket (every cell = one delivery)
        sr = (w["balls_bowled"] / w["wkts"]) if w["wkts"] and w["balls_bowled"] else None
        bowling.append(dict(name=w["name"], games=w["games"], ob=w["ob"], rc=w["rc"],
                            wkts=w["wkts"], econ=econ, balls_bowled=w["balls_bowled"], sr=sr,
                            wkt_types=w["wkt_types"], best=w["best"],
                            extras=w["extras"], hattricks=w["hattricks"]))
    # Rank by economy (lowest/most-negative first), wickets as tiebreak. Sub-threshold
    # bowlers (< min_rank games) sink below, grouped by games desc; non-bowlers last.
    for b in bowling:
        b["ranked"] = b["games"] >= min_rank and b["ob"] > 0
    bowling.sort(key=lambda x: (x["ob"] == 0, not x["ranked"],
                                (-x["games"] if not x["ranked"] else 0),
                                x["econ"], -x["wkts"]))

    # ---- all-rounders ----
    allround = [dict(name=a["name"], games=a["games"], c=a["c"],
                     avgc=a["c"] / a["games"] if a["games"] else 0.0) for a in allr.values()]
    # Ranked all-rounders (>= min_ar games) first by avg C; sub-threshold players sink
    # below, grouped by games desc. This is also the player-profile page order.
    for a in allround:
        a["ranked"] = a["games"] >= min_ar
    allround.sort(key=lambda x: (not x["ranked"],
                                 (-x["games"] if not x["ranked"] else 0),
                                 -x["avgc"]))

    # ---- partnerships ----
    parts = [dict(pair=k, games=p["games"], total=p["total"],
                  avg=p["total"] / p["games"] if p["games"] else 0.0, best=p["best"],
                  skins_won=p["skins_won"],
                  skin_pct=100.0 * p["skins_won"] / p["games"] if p["games"] else 0.0)
             for k, p in partners.items()]
    parts.sort(key=lambda x: -x["avg"])

    # ---- opponent 'against us' (team scores kept full; renderer slices) ----
    opp_highest = sorted(opp_team, key=lambda x: -x[0])
    opp_lowest = sorted(opp_team, key=lambda x: x[0])
    opp_batting = sorted(opp_bat, key=lambda x: -x[0])[:5]
    opp_bowling = sorted(opp_bowl, key=lambda x: (-x[0], x[1]))[:5]

    # ---- single-game records (ours) ----
    records = dict(
        bat_high=max(score_games, key=lambda x: x[0], default=None),     # (rs, outs, balls, name, opp, date)
        bat_low=min(score_games, key=lambda x: x[0], default=None),
        bat_most_sevens=max(seven_games, key=lambda x: x[0], default=None),   # (count, name, opp, date)
        bat_most_runouts=max(runout_games, key=lambda x: x[0], default=None),
        bowl_best=max(((w["best"], w["name"]) for w in bowl.values() if w["best"]),
                      key=lambda t: t[0][0], default=None),
        bowl_most_wkts=max(bowling, key=lambda x: x["wkts"], default=None),
        bowl_best_econ=min([x for x in bowling if x["ob"] >= 4], key=lambda x: x["econ"], default=None),
        best_skin=min(skin_defence, key=lambda x: x[0], default=None),   # fewest opp runs in a skin
    )

    contrib_high = sorted(game_contribs, key=lambda x: -x[0])[:5]
    contrib_low = sorted(game_contribs, key=lambda x: x[0])[:5]
    partnership_high = sorted(partner_games, key=lambda x: -x[0])[:5]

    # ---- rank movement: where everyone stood BEFORE the newest game ----
    prev_ranks = None
    if not _nested and len(matches) > 1:
        prev = build(matches[:-1], R, alltime, _nested=True)
        prev_ranks = {cat: {x["name"]: i + 1
                            for i, x in enumerate(y for y in prev[cat] if y["ranked"])}
                      for cat in ("batting", "bowling", "allround")}

    return dict(team=team, batting=batting, bowling=bowling, allround=allround,
                partnerships=parts, opp_highest=opp_highest, opp_lowest=opp_lowest,
                opp_batting=opp_batting, opp_bowling=opp_bowling, records=records,
                contrib_high=contrib_high, contrib_low=contrib_low,
                partnership_high=partnership_high, gamelog=dict(glog),
                hattricks=hattricks, prev_ranks=prev_ranks,
                min_games=MIN_GAMES, min_ar_games=min_ar, min_rank_games=min_rank,
                min_balls=MIN_BALLS)


def season_awards(d):
    """Season awards from build()'s lists: the first `ranked` entry of each
    (batting by avg12, bowling by econ, allround by avgc); None when nobody is ranked."""
    def first(key, field):
        for x in d[key]:
            if x["ranked"]:
                return {"name": x["name"], "value": x[field]}
        return None
    return {"batter": first("batting", "avg12"),
            "bowler": first("bowling", "econ"),
            "player": first("allround", "avgc")}


def load_scoped():
    """Return (current_matches, alltime_matches, current_label)."""
    R = roster.load()
    sdirs = paths.season_dirs()  # sorted YYYY-MM-DD folders
    alltime = []
    per_season = []
    for sd in sdirs:
        ms = S.load_matches(paths.cards_dir(sd))
        per_season.append((sd, ms))
        alltime += ms
    current_dir, current_ms = per_season[-1]
    label = current_ms[0]["season"] if current_ms else os.path.basename(current_dir)
    return current_ms, alltime, label, current_dir, R


def load_all():
    """Return (seasons, alltime, R) where seasons = [(season_dir, label, matches), ...]
    in chronological order (last = current). Every season + the combined all-time set
    are aggregated by the SAME build() so all reports are deterministic and consistent."""
    R = roster.load()
    seasons, alltime = [], []
    for sd in paths.season_dirs():
        ms = S.load_matches(paths.cards_dir(sd))
        if not ms:
            continue
        label = ms[0]["season"]
        seasons.append((sd, label, ms))
        alltime += ms
    return seasons, alltime, R


if __name__ == "__main__":
    seasons, allm, R = load_all()
    scopes = [(label, ms) for _, label, ms in seasons] + [("ALL-TIME", allm)]
    for scope, ms in scopes:
        d = build(ms, R)
        t = d["team"]
        print(f"\n== {scope} ==  {t['played']} games  {t['won']}-{t['lost']}-{t['drawn']}"
              f"  avg {t['avg_for']:.1f}/{t['avg_against']:.1f}")
        print("  top bat:", ", ".join(f"{b['name']} {b['rs']}({b['avg12']:.1f}/12)" for b in d["batting"][:3]))
        print("  top bowl:", ", ".join(f"{b['name']} {b['wkts']}w" for b in d["bowling"][:3]))
        print("  all-round:", ", ".join(f"{a['name']} {a['avgc']:+.1f}({a['games']}g)" for a in d["allround"][:3]))
        qp = [p for p in d["partnerships"] if p["games"] >= d["min_games"]][:3]
        print("  partnerships>=3g:", ", ".join(f"{'+'.join(p['pair'])} {p['avg']:.0f}({p['games']}g)" for p in qp) or "(none yet)")
