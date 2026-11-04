#!/usr/bin/env python3
"""Build the static site the team opens on their phones.

  python scripts/build_site.py [--out site]

Writes into OUT (default: site/ at the repo root):
  index.html, app.js, … functions/   the viewer (copied from viewer/, tests left out)
  data/index.json                    [{slug, name, badge, colours}] — one per team
  data/<team-slug>.json              everything the viewer shows for that team:
                                     per-season + all-time stats (report_data.build),
                                     records, every game with its coach letter
  photos/<team-slug>/…               player photos

Every team folder under Teams/ is built (no TEAM env var needed). The viewer never
computes stats: everything it shows comes from these files.
"""
import argparse, json, math, os, re, shutil, sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
_had_optional = "ACS_TEAM_OPTIONAL" in os.environ
os.environ.setdefault("ACS_TEAM_OPTIONAL", "1")     # import paths without picking a team
import paths, rules, coach, roster, stats_core
import report_data as RD
import season_meta, team_settings
if not _had_optional:
    del os.environ["ACS_TEAM_OPTIONAL"]

from coach import slug

VIEWER_DIR = os.path.join(paths.ENGINE_ROOT, "viewer")
SEASON_RE = re.compile(r"\d{4}-\d{2}-\d{2}$")
PHOTO_EXTS = (".jpg", ".jpeg", ".png", ".webp")
DISM = stats_core.DISM
EXTRA_TOKENS = set(stats_core.EXTRAS)


def jsonable(obj):
    """Plain JSON data: dicts get str keys, tuples/sets become lists, NaN/inf -> None."""
    if isinstance(obj, float):
        return None if (math.isnan(obj) or math.isinf(obj)) else obj
    if isinstance(obj, dict):
        return {(k if isinstance(k, str) else str(k)): jsonable(v) for k, v in obj.items()}
    if isinstance(obj, set):
        try:
            obj = sorted(obj)
        except TypeError:
            obj = list(obj)
    if isinstance(obj, (list, tuple)):
        return [jsonable(v) for v in obj]
    return obj


# ---------------------------------------------------------------- records

def _best(items, better):
    """First item (chronological) that no later item beats: `better(a, b)` is True
    when a is strictly better than b."""
    best = None
    for it in items:
        if best is None or better(it, best):
            best = it
    return best


def _streak(games, outcome):
    best, cur, start = (0, None, None), 0, None
    for g in games:
        if g["outcome"] == outcome:
            cur, start = cur + 1, start if cur else g["key"]
            if cur > best[0]:
                best = (cur, start, g["key"])
        else:
            cur, start = 0, None
    return {"value": best[0], "from": best[1], "to": best[2]}


def derive_records(d, games):
    """Team and individual records for one scope. `d` = report_data.build() for the
    scope, `games` = the scope's payload games (chronological). A record is
    {"value", "name"?/"names"?, "opp", "date", "key"} or None."""
    keyof = {(g["date"], g["opp"]): g["key"] for g in games}

    def rec(value, opp, date, **who):
        return {"value": value, **who, "opp": opp, "date": date, "key": keyof.get((date, opp))}

    def grec(g, value):
        return rec(value, g["opp"], g["date"])

    hi = _best(games, lambda a, b: a["total"] > b["total"])
    lo = _best(games, lambda a, b: a["total"] < b["total"])
    margin = lambda g: g["total"] - g["against"]
    win = _best([g for g in games if g["outcome"] == "win"], lambda a, b: margin(a) > margin(b))
    loss = _best([g for g in games if g["outcome"] == "loss"], lambda a, b: margin(a) < margin(b))
    wk = _best(games, lambda a, b: a["team_wkts"] > b["team_wkts"])
    ver = [g for g in games if g["extras"] is not None]
    fx = _best(ver, lambda a, b: a["extras"] < b["extras"])
    bs = d["records"].get("best_skin")
    team = dict(
        high_total=grec(hi, hi["total"]) if hi else None,
        low_total=grec(lo, lo["total"]) if lo else None,
        biggest_win=grec(win, margin(win)) if win else None,
        heaviest_loss=grec(loss, margin(loss)) if loss else None,
        best_skin=rec(bs[0], bs[1], bs[2]) if bs else None,
        most_wkts_game=grec(wk, wk["team_wkts"]) if wk else None,
        fewest_extras_game=grec(fx, fx["extras"]) if fx else None,
        longest_win_streak=_streak(games, "win"),
        longest_loss_streak=_streak(games, "loss"),
    )

    # one row per (player, game), chronological by game then name
    order = {g["key"]: i for i, g in enumerate(games)}
    rows = sorted(((name, e) for name, log in d["gamelog"].items() for e in log),
                  key=lambda ne: (order.get(keyof.get((ne[1]["date"], ne[1]["opp"])), 0), ne[0]))

    def prec(row, value):
        name, e = row
        return rec(value, e["opp"], e["date"], name=name)

    runs = _best(rows, lambda a, b: a[1]["rs"] > b[1]["rs"])
    wkts = _best([r for r in rows if r[1]["wkts"] > 0], lambda a, b: a[1]["wkts"] > b[1]["wkts"])
    econ = lambda r: r[1]["rc"] / r[1]["ob"]
    eco = _best([r for r in rows if r[1]["ob"] > 0], lambda a, b: econ(a) < econ(b))
    ch = d["contrib_high"][0] if d["contrib_high"] else None          # (c, name, opp, date)
    ph = d["partnership_high"][0] if d["partnership_high"] else None  # (runs, a, b, opp, date)
    ro = _best([(n, c, g) for g in games for n, c in sorted(g["runouts_created"].items()) if c > 0],
               lambda a, b: a[1] > b[1])
    individual = dict(
        best_contribution=rec(ch[0], ch[2], ch[3], name=ch[1]) if ch else None,
        most_runs_game=prec(runs, runs[1]["rs"]) if runs else None,
        most_wkts_game=prec(wkts, wkts[1]["wkts"]) if wkts else None,
        best_econ=prec(eco, round(econ(eco), 2)) if eco else None,
        best_partnership=rec(ph[0], ph[3], ph[4], names=[ph[1], ph[2]]) if ph else None,
        hattricks=[rec(h["n"], h["opp"], h["date"], name=h["bowler"], victims=h["victims"])
                   for h in d["hattricks"]],
        most_runouts_created=rec(ro[1], ro[2]["opp"], ro[2]["date"], name=ro[0]) if ro else None,
    )
    return {"team": team, "individual": individual}


# ---------------------------------------------------------------- one team

def _load_cfg(team_dir):
    p = os.path.join(team_dir, "team.yaml")
    if not os.path.exists(p):
        return {}
    import yaml
    with open(p, encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def _load_seasons(team_dir):
    out = []
    for n in sorted(os.listdir(team_dir)):
        sd = os.path.join(team_dir, n)
        if SEASON_RE.match(n) and os.path.isdir(sd):
            ms = stats_core.load_matches(os.path.join(sd, "scorecards"))
            if ms:
                out.append((n, ms[0]["season"], ms))
    return out


def _bowling_detail(m, rz):
    """(extras bowled by us, {bowler: run outs off their bowling}) for a verified
    game; (None, {}) when the ball-by-ball is not verified."""
    bbb = m.get("ball_by_ball") or {}
    if bbb.get("status") != "verified":
        return None, {}
    extras, ro = 0, defaultdict(int)
    for bat in bbb.get("opponent_batting") or []:
        for ov in bat["overs"]:
            for b in ov["balls"]:          # canonical tokens (the validator enforces them)
                if b in EXTRA_TOKENS:
                    extras += 1
                elif b == "R":
                    ro[rz(ov["bowler"])] += 1
    return extras, dict(ro)


def _summary_rows(rows, rz):
    return [dict(name=rz(r["name"]), skin=r.get("skin"), rs=r["rs"], ob=r["ob"], rc=r["rc"],
                 wkts=r["wkts"], econ=r.get("econ"), c=r["c"]) for r in rows]


def _photo(team_dir, team_slug, name):
    pdir = os.path.join(team_dir, "photos")
    if not os.path.isdir(pdir):
        return None
    want = slug(name)
    for f in sorted(os.listdir(pdir)):
        stem, ext = os.path.splitext(f)
        if stem.lower() == want and ext.lower() in PHOTO_EXTS:
            return f"photos/{team_slug}/{f}"
    return None


def _player_entry(team_dir, tslug, n, awards):
    e = {"slug": slug(n), "photo": _photo(team_dir, tslug, n)}
    if awards and any(awards.values()):
        e["awards"] = dict(awards)
    return e


def team_payload(team_dir, R):
    """Everything the viewer shows for one team, built only from `team_dir`."""
    cfg = _load_cfg(team_dir)
    name = cfg.get("name") or os.path.basename(team_dir)
    tslug = slug(name)
    R = R if R is not None else roster.load(os.path.join(team_dir, "players.yaml"))
    rz = lambda n: roster.resolve(n, R)
    coach_cfg = {"enabled": True, "tone": "banter", **(cfg.get("coach") or {})}
    letters = coach.load_letters(team_dir) if coach_cfg["enabled"] else {}

    seasons = _load_seasons(team_dir)
    history = [m for _, _, ms in seasons for m in ms]
    folder_of = [folder for folder, _, ms in seasons for _ in ms]
    keys = coach.game_keys(history)
    alltime = RD.build(history, R, alltime=True) if history else None

    games = []
    for i, (m, g) in enumerate(zip(history, alltime["team"]["games"] if alltime else [])):
        extras, ro = _bowling_detail(m, rz)
        letter = letters.get(keys[i])
        games.append(dict(
            key=keys[i], season=folder_of[i], stage=m.get("stage"), date=g["date"], opp=g["opp"],
            outcome=g["outcome"], total=g["total"], against=g["against"],
            skins=g["skins"], oskins=g["oskins"], skin_scores=g["skin_scores"],
            pom=g["pom"], pom_ours=g["pom_ours"], top_c=g["top_c"],
            team_wkts=sum(r["wkts"] for r in m["team_summary"]),
            verified=extras is not None, extras=extras, runouts_created=ro,
            letter={"sections": letter["sections"], "players": letter["players"]} if letter else None,
            summaries={"ours": _summary_rows(m["team_summary"], rz),
                       "theirs": _summary_rows(m["opponent_summary"], rz)}))

    season_out, start = [], 0
    award_counts = defaultdict(lambda: {"player": 0, "batter": 0, "bowler": 0})
    for i, (folder, label, ms) in enumerate(seasons):
        sg = games[start:start + len(ms)]
        start += len(ms)
        d = RD.build(ms, R)
        meta = season_meta.load(os.path.join(team_dir, folder))
        finished = season_meta.is_finished(i, len(seasons), meta)
        awards = RD.season_awards(d) if finished else None
        for kind, a in (awards or {}).items():
            if a:
                award_counts[a["name"]][kind] += 1
        season_out.append(dict(key=folder, label=label, games=[g["key"] for g in sg],
                               stats=jsonable(d), records=jsonable(derive_records(d, sg)),
                               medal=meta["medal"], finish=meta["finish"],
                               finished=finished, awards=awards))

    names = [a["name"] for a in alltime["allround"]] if alltime else []
    return {
        "team": dict(slug=tslug, name=name, badge=cfg.get("badge") or name[:4],
                     arena=cfg.get("arena") or "", league=cfg.get("league") or "",
                     colours=cfg.get("colours") or {},
                     coach={"enabled": bool(coach_cfg["enabled"]), "tone": coach_cfg["tone"]},
                     rules=rules.load_rules(cfg), gate=cfg.get("gate") or "pin",
                     show=team_settings.merge_show(cfg)),
        "seasons": season_out,
        "alltime": dict(stats=jsonable(alltime) if alltime else None,
                        records=jsonable(derive_records(alltime, games)) if alltime else None),
        "games": jsonable(games),
        "players": {n: _player_entry(team_dir, tslug, n, award_counts.get(n)) for n in names},
        # data as of the newest game: keeps rebuilds byte-identical when nothing changed
        "generated": games[-1]["date"] if games else "",
    }


# ---------------------------------------------------------------- the site

def _write_json(path, obj, written):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(obj, fh, ensure_ascii=False, separators=(",", ":"))
    written.append(path)


def _copy_viewer(out_dir, written):
    for dirpath, dirnames, filenames in os.walk(VIEWER_DIR):
        dirnames[:] = [d for d in dirnames if d != "tests" and d != "node_modules"]
        for f in filenames:
            if f.endswith(".test.js") or (f == "package.json" and dirpath == VIEWER_DIR):
                continue                    # tests and the dev-only package.json stay out
            src = os.path.join(dirpath, f)
            dst = os.path.join(out_dir, os.path.relpath(src, VIEWER_DIR))
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(src, dst)
            written.append(dst)


def build(out_dir):
    """Build the whole site into out_dir; returns the files written."""
    written = []
    for sub in ("data", "photos"):
        shutil.rmtree(os.path.join(out_dir, sub), ignore_errors=True)
    os.makedirs(os.path.join(out_dir, "data"), exist_ok=True)
    _copy_viewer(out_dir, written)
    index = []
    for folder in paths.team_folders():
        team_dir = os.path.join(paths.TEAMS_DIR, folder)
        p = team_payload(team_dir, None)
        s = p["team"]["slug"]
        _write_json(os.path.join(out_dir, "data", f"{s}.json"), p, written)
        pdir = os.path.join(team_dir, "photos")
        for f in sorted(os.listdir(pdir)) if os.path.isdir(pdir) else []:
            if os.path.splitext(f)[1].lower() in PHOTO_EXTS:
                dst = os.path.join(out_dir, "photos", s, f)
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copy2(os.path.join(pdir, f), dst)
                written.append(dst)
        index.append({"slug": s, "name": p["team"]["name"], "badge": p["team"]["badge"],
                      "colours": p["team"]["colours"]})
    _write_json(os.path.join(out_dir, "data", "index.json"), index, written)
    return written


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=os.path.join(paths.ROOT, "site"))
    a = ap.parse_args(argv)
    out = os.path.abspath(a.out)
    files = build(out)
    with open(os.path.join(out, "data", "index.json"), encoding="utf-8") as fh:
        teams = [t["name"] for t in json.load(fh)]
    print(f"built {out} — {len(teams)} team(s){': ' + ', '.join(teams) if teams else ''}, "
          f"{len(files)} files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
