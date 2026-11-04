#!/usr/bin/env python3
"""Validate the combined per-game files data/<date>.json. Prints PASS/FAIL for
every checksum, exits non-zero on any failure.

Per innings:
  A. each batsman's over-totals sum to their Runs Scored (RS) in the summary
  B. each over is internally consistent: remainder = total - (numeric_runs +
     wicket_runs*dismissals) is the over's extras, so it is never negative and is
     exactly 0 when the over holds no w/nb cell (best-guessed balls are fine as long
     as the over total holds); every ball token is canonical
  C. each bowler's over-totals sum to their Runs Conceded (RC), and dismissal
     symbols count to their Wickets (Wkts), checked vs the bowling team's summary
  D. over_seq (delivery order, when present): 16 overs per innings, each over's
     per-batter projection reproduces that batter's balls list exactly
  E. ball counts: every over block holds exactly balls_per_over cells (a wide/no-ball
     IS one of the over's balls — nothing is re-bowled); the LAST over of a skin may
     hold one more when extra_ball_last_over allows the optional extra ball, so with
     the default rules a skin is 24 or 25.
     A game's meta may carry `ball_count_exceptions` ([{innings, skin, balls,
     reason}]) for user-adjudicated card oddities (e.g. an umpire allowing a
     second extra ball) — that skin is then held to its recorded count instead
  S. each skin's pair RS sums to that team's entry in the card's skins table
Also checks each team's RS sums to the team total (top-of-card authority).

The scoring constants come from the rules (scripts/rules.py): the team's
team.yaml -> rules, overridden by the game's own meta.rules snapshot.
Test hook: WICKET_RUNS_OVERRIDE=<int> forces the wicket value for every game
(used by the test suite to prove the value is read, never needed in real use).
"""
import json, glob, os, sys
import paths, rules

DISM = {"R", "C", "B", "S", "L", "H", "M"}   # each worth rules.wicket_runs
STAGES = ("league", "playoff", "semi-final", "final")
EXTRA_TOKENS = {"w", "nb"}
TOKENS = DISM | EXTRA_TOKENS                 # only canonical tokens allowed


def numeric_and_wkts(balls):
    runs = sum(b for b in balls if isinstance(b, int))
    wkts = sum(1 for b in balls if isinstance(b, str) and b in DISM)
    return runs, wkts


def bad_tokens(balls):
    return [b for b in balls if not isinstance(b, int) and b not in TOKENS]


def check_overseq(inn):
    """Yield (ok, message) per over_seq check for one innings; nothing if absent."""
    seqs = inn.get("over_seq")
    if seqs is None:
        return
    byskin = {}
    for bat in inn["batting"]:
        byskin.setdefault(bat["skin"], []).append(bat)
    n_overs = sum(len(b["overs"]) for b in inn["batting"]) // 2
    yield len(seqs) == n_overs, f"over_seq has {len(seqs)} overs, expected {n_overs}"
    per_skin = {}
    for e in seqs:
        per_skin.setdefault(e["skin"], []).append(e)
    for sk, bats in sorted(byskin.items()):
        for i, e in enumerate(per_skin.get(sk, [])):
            msg = []
            for bat in bats:
                if i >= len(bat["overs"]) or e["bowler"] != bat["overs"][i]["bowler"]:
                    msg.append(f"bowler {e['bowler']} != over {i+1} bowler in batter lists")
                    continue
                proj = [b for n, b in e["seq"] if n == bat["name"]]
                if proj != bat["overs"][i]["balls"]:
                    msg.append(f"{bat['name']}: seq projects {proj} != recorded {bat['overs'][i]['balls']}")
            unknown = {n for n, _ in e["seq"]} - {b["name"] for b in bats}
            if unknown:
                msg.append(f"unknown batters {sorted(unknown)}")
            yield not msg, f"skin {sk} over {i+1} vs {e['bowler']}: " + "; ".join(msg)


def rules_for(g):
    R = rules.game_rules(g, paths.RULES)
    if os.environ.get("WICKET_RUNS_OVERRIDE"):
        R = dict(R, wicket_runs=int(os.environ["WICKET_RUNS_OVERRIDE"]))
    return R


def main():
    fails = total = 0
    games = []          # (path, game) across season folders, sorted within each
    for sd in paths.season_dirs():
        seen = {}       # (date, opponent) -> first basename in this season folder
        for jf in sorted(glob.glob(os.path.join(paths.data_dir(sd), "*.json")),
                         key=os.path.basename):
            g = json.load(open(jf, encoding="utf-8"))
            games.append((jf, g))
            key = (str(g["date"]), g["opponent"].strip().casefold())
            first = seen.setdefault(key, os.path.basename(jf))
            if first != os.path.basename(jf):
                print(f"!! duplicate game: {first} and {os.path.basename(jf)} "
                      f"both record {key[0]} vs {g['opponent']}")
                total += 1; fails += 1
    for jf, g in games:
        R = rules_for(g)
        summaries = g["summaries"]
        sum_by = {t: {r["name"]: r for r in rows} for t, rows in summaries.items()}
        print(f"\n=== {g['date']}  {g['team']} vs {g['opponent']} ({os.path.basename(jf)}) ===")
        stage = g.get("meta", {}).get("stage")
        if stage and stage not in STAGES:
            print(f"  [M] meta.stage '{stage}' not one of league/playoff/semi-final/final  FAIL")
            total += 1; fails += 1

        # team totals (top-of-card authority): RS sums to team_total
        res = g["result"]
        for team, key in [(g["team"], "team_total"), (g["opponent"], "opponent_total")]:
            rs = sum(r["rs"] for r in summaries[team])
            ok = rs == res[key]; total += 1; fails += not ok
            print(f"  [T] {team:<18} RS sum {rs:>4} vs total {res[key]:>4}  {'PASS' if ok else 'FAIL'}")

        for inn in g["innings"]:
            bt = inn["batting_team"]
            bowl_team = g["opponent"] if bt == g["team"] else g["team"]
            bat_sum, bowl_sum = sum_by[bt], sum_by[bowl_team]
            print(f"  -- innings {inn['order']}: {bt} batting --")
            bowler_runs, bowler_wkts = {}, {}
            # a short-handed team may send one batter out twice (two skins):
            # their entries' over-totals together make up their single summary RS
            bat_overs = {}
            for bat in inn["batting"]:
                bat_overs[bat["name"]] = (bat_overs.get(bat["name"], 0)
                                          + sum(o["total"] for o in bat["overs"]))
            for name, over_sum in bat_overs.items():
                rs = bat_sum[name]["rs"]
                ok = over_sum == rs; total += 1; fails += not ok
                print(f"    [A] {name:<18} over-totals={over_sum:>4}  RS={rs:>4}  {'PASS' if ok else 'FAIL'}")
            for bat in inn["batting"]:
                for o in bat["overs"]:
                    runs, wkts = numeric_and_wkts(o["balls"])
                    extras = o["total"] - (runs + R["wicket_runs"] * wkts)
                    has_extra = any(b in EXTRA_TOKENS for b in o["balls"] if isinstance(b, str))
                    if extras < 0 or (extras and not has_extra):
                        total += 1; fails += 1
                        print(f"        [B] FAIL vs {o['bowler']}: total={o['total']} balls={o['balls']} "
                              f"(wicket = {R['wicket_runs']})")
                    bad = bad_tokens(o["balls"])
                    if bad:
                        total += 1; fails += 1
                        print(f"        [B] FAIL vs {o['bowler']}: non-canonical tokens {bad}")
                    bowler_runs[o["bowler"]] = bowler_runs.get(o["bowler"], 0) + o["total"]
                    bowler_wkts[o["bowler"]] = bowler_wkts.get(o["bowler"], 0) + wkts
            # [E] every over block = balls_per_over cells; the last over of a skin may
            # hold one more (optional extra ball), so a skin totals 24 or 25 balls with
            # the default rules — unless a user-adjudicated exception in
            # meta.ball_count_exceptions says otherwise
            exc = {(e["innings"], e["skin"]): e["balls"]
                   for e in g.get("meta", {}).get("ball_count_exceptions", [])}
            e_byskin = {}
            for bat in inn["batting"]:
                e_byskin.setdefault(bat["skin"], []).append(bat)
            e_fails = e_total = 0
            for sk, bats in sorted(e_byskin.items()):
                n_overs = len(bats[0]["overs"])
                skin_cells = 0
                excepted = exc.get((inn["order"], sk))
                for i in range(n_overs):
                    cells = sum(len(x["overs"][i]["balls"]) for x in bats)
                    skin_cells += cells
                    bpo, last_max = R["balls_per_over"], rules.max_cells_last_over(R)
                    ok = (cells == bpo or (i == n_overs - 1
                          and (cells == last_max or (excepted is not None and cells <= bpo + 2))))
                    total += 1; fails += not ok; e_total += 1; e_fails += not ok
                    if not ok:
                        print(f"    [E] skin {sk} over {i+1} vs {bats[0]['overs'][i]['bowler']}: "
                              f"{cells} cells  FAIL")
                allowed = rules.skin_ball_counts(R)
                ok = skin_cells in allowed or skin_cells == excepted
                total += 1; fails += not ok; e_total += 1; e_fails += not ok
                if not ok:
                    want = "/".join(str(n) for n in sorted(allowed))
                    print(f"    [E] skin {sk}: {skin_cells} balls, expected {want}  FAIL")
            print(f"    [E] ball counts: {e_total - e_fails}/{e_total} "
                  f"{'PASS' if not e_fails else 'FAIL'}")
            # [S] each skin's pair RS sums to the card's skins table
            skins = res["team_skins" if bt == g["team"] else "opponent_skins"]
            # (uses each entry's own over-totals; [A] ties those to the summary RS)
            per_skin_rs = {}
            for bat in inn["batting"]:
                per_skin_rs[bat["skin"]] = (per_skin_rs.get(bat["skin"], 0)
                                            + sum(o["total"] for o in bat["overs"]))
            s_fails = 0
            for k in sorted(per_skin_rs):
                ok = 1 <= k <= len(skins) and per_skin_rs[k] == skins[k - 1]
                total += 1; fails += not ok; s_fails += not ok
                if not ok:
                    card = skins[k - 1] if 1 <= k <= len(skins) else "?"
                    print(f"    [S] skin {k}: pair RS {per_skin_rs[k]} vs card {card}  FAIL")
            print(f"    [S] skin totals vs card: {len(per_skin_rs) - s_fails}/{len(per_skin_rs)} "
                  f"{'PASS' if not s_fails else 'FAIL'}")
            seq_fails = seq_total = 0
            for ok, msg in check_overseq(inn):
                total += 1; seq_total += 1
                if not ok:
                    fails += 1; seq_fails += 1
                    print(f"    [D] {msg}  FAIL")
            if seq_total:
                print(f"    [D] over_seq: {seq_total - seq_fails}/{seq_total} checks "
                      f"{'PASS' if not seq_fails else 'FAIL'}")
            for name, runs in sorted(bowler_runs.items()):
                row = bowl_sum.get(name)
                if not row:
                    total += 1; fails += 1
                    print(f"    [C] {name:<18} NOT in {bowl_team} summary  FAIL"); continue
                rc_ok = runs == row["rc"]; wk_ok = bowler_wkts[name] == row["wkts"]
                total += 2; fails += (not rc_ok) + (not wk_ok)
                print(f"    [C] {name:<18} RC {runs:>4} vs {row['rc']:>4} {'PASS' if rc_ok else 'FAIL'} | "
                      f"Wkts {bowler_wkts[name]} vs {row['wkts']} {'PASS' if wk_ok else 'FAIL'}")

    print(f"\n{'='*50}\n{total - fails}/{total} checks passed"
          + (f"  ({fails} FAILED)" if fails else "  -- ALL RECONCILE"))
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
