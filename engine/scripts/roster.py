#!/usr/bin/env python3
"""Team player list + name registry. Resolves ambiguous scorecard names (e.g.
"Sam Unknown") to confirmed full names, without editing the scorecard records.
One players.yaml per team (Teams/<TEAM>/players.yaml).

  python scripts/roster.py --refresh   # (re)build players.yaml from the scorecards
  python scripts/roster.py --list      # players still needing a confirmed name
  python scripts/roster.py --check     # names on cards NOT yet in players.yaml
                                        # (run on import; ask user: existing or new?)

Edit players.yaml to fill in `name:` (and `aka:` for alternate spellings of the
same person), then re-run `python scripts/generate_stats.py`.
Use TEAM=<name> to target another team.
"""
import glob, os, re, sys, difflib
import yaml
import paths

TN = paths.TEAM_NAME   # our team, exactly as printed on the scorecards

PLAYERS_FILE = paths.PLAYERS_FILE


def _fm(path):
    txt = open(path, encoding="utf-8").read()
    return yaml.safe_load(re.match(r"^---\n(.*?)\n---", txt, re.S).group(1))


def distinct_players():
    """raw name -> set of teams it appeared for (our team or an opponent name),
    scanning every season's rendered scorecards."""
    out = {}
    for sd in paths.season_dirs():
        for md in sorted(glob.glob(os.path.join(paths.cards_dir(sd), "*.md"))):
            fm = _fm(md)
            for r in fm["team_summary"]:
                out.setdefault(r["name"], set()).add(TN)
            for r in fm["opponent_summary"]:
                out.setdefault(r["name"], set()).add(fm["opponent"])
    return out


def _entries(path=None):
    path = path or PLAYERS_FILE
    if not path or not os.path.exists(path):
        return []
    return (yaml.safe_load(open(path, encoding="utf-8")) or {}).get("roster") or []


def load(path=None):
    """Return {raw_or_aka: confirmed_name_or_None} from a players.yaml
    (default: the current team's)."""
    res = {}
    for e in _entries(path):
        conf = (e.get("name") or "").strip() or None
        res[e["as"]] = conf
        for a in e.get("aka") or []:
            res[a] = conf or e["as"]
    return res


def resolve(raw, res=None):
    res = load() if res is None else res
    return res.get(raw) or raw


def needs_confirm(raw, confirmed):
    return ("Unknown" in raw) and not confirmed


def _q(s):
    return '"%s"' % str(s).replace('"', '\\"')


def refresh():
    existing = {e["as"]: e for e in _entries()}
    players = distinct_players()

    def team_of(teams):
        return TN if TN in teams else " / ".join(sorted(teams))

    ours = sorted([r for r, tm in players.items() if TN in tm])
    opp = sorted([r for r, tm in players.items() if TN not in tm])

    L = [
        "# Team player list & name registry (one per team).",
        "#   as    : exactly how the name is printed on a scorecard (do not change).",
        "#   name  : the confirmed full name. Fill this in to clear an ambiguity; the",
        "#           reports then show this instead of the scorecard spelling.",
        "#   aka   : optional OTHER scorecard spellings that are the SAME person",
        "#           (they get merged together in the season stats).",
        "# Refresh after adding scorecards:  python scripts/roster.py --refresh",
        "roster:",
    ]

    def emit(raw, teams):
        e = existing.get(raw, {})
        name = e.get("name")
        flag = "  # NEEDS CONFIRMATION (surname unknown)" if needs_confirm(raw, name) else "  # " + team_of(teams)
        L.append(f'  - as: "{raw}"{flag}')
        L.append(f'    name: {("" if not name else _q(name))}')
        if e.get("aka"):
            L.append("    aka: [%s]" % ", ".join(_q(a) for a in e["aka"]))

    L.append(f"  # -- {TN} --")
    for raw in ours:
        emit(raw, players[raw])
    L.append("  # -- Opponents --")
    for raw in opp:
        emit(raw, players[raw])

    os.makedirs(paths.TEAM_DIR, exist_ok=True)
    open(PLAYERS_FILE, "w", encoding="utf-8").write("\n".join(L) + "\n")
    n = sum(1 for r in players if needs_confirm(r, existing.get(r, {}).get("name")))
    print(f"wrote {os.path.relpath(PLAYERS_FILE, paths.ROOT)} — {len(players)} players, {n} need confirmation")


def list_unconfirmed():
    players, res = distinct_players(), load()
    rows = [(r, tm) for r, tm in players.items() if needs_confirm(r, res.get(r))]
    if not rows:
        print("All players confirmed (or no ambiguous names)."); return
    print(f"{len(rows)} player(s) still need a confirmed name:\n")
    for raw, tm in sorted(rows, key=lambda x: (TN not in x[1], x[0])):
        team = TN if TN in tm else " / ".join(sorted(tm))
        print(f"  - {raw:<20} [{team}]")


def check():
    """Names on scorecards NOT yet registered in players.yaml — run on import so
    you can ask the user whether each is an existing player or a new one."""
    reg = [e["as"] for e in _entries()]
    reg += [a for e in _entries() for a in (e.get("aka") or [])]
    players = distinct_players()
    new = [p for p in players if p not in reg]
    if not new:
        print("No unregistered names — every scorecard name is already in players.yaml."); return
    print(f"{len(new)} name(s) on scorecards are NOT in players.yaml — confirm each:\n")
    for p in sorted(new):
        near = difflib.get_close_matches(p, reg, n=3, cutoff=0.6)
        hint = f"   <- similar existing: {', '.join(near)}" if near else ""
        team = TN if TN in players[p] else " / ".join(sorted(players[p]))
        print(f"  - {p:<20} [{team}]{hint}")
    print("\nAsk: existing player (add under that player's `aka:`) or new (add an entry"
          " with `name:`), then run: python scripts/roster.py --refresh")


if __name__ == "__main__":
    if "--refresh" in sys.argv:
        refresh()
    elif "--list" in sys.argv:
        list_unconfirmed()
    elif "--check" in sys.argv:
        check()
    else:
        print(__doc__)
