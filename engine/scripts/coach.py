#!/usr/bin/env python3
"""AI Coach letters: one letter per game, kept for good.

  python scripts/coach.py --status          games whose letter is missing or stale:
                                            KEY<TAB>FP<TAB>SEASON<TAB>STATE per line
  python scripts/coach.py --convert-legacy  rewrite an old one-letter-per-season
                                            coach_notes.yaml into the per-game form
                                            (the old file is kept as coach_notes.legacy.yaml)

Teams/<TEAM>/coach_notes.yaml:

  letters:
    - game: "2026-10-07"        # game key: the date, plus -<opponent-slug> when two
      fp: "1g51f80a-2026-10-07" #   games share a date; fp = fingerprint of the team's
      sections:                 #   stats up to AND including this game (all-time),
        - {title, html}         #   so later games never make an old letter stale
      players:
        - {name, note}

The ai-coach skill writes a letter for every game that --status lists, in date
order, and never rewrites an existing one. A letter only goes stale when an
earlier scorecard is corrected.
"""
import os, re, shutil, sys
import yaml

NOTES_FILE = "coach_notes.yaml"


def slug(s):
    """Lowercase, runs of non-alphanumerics -> '-', trimmed."""
    return re.sub(r"[^a-z0-9]+", "-", str(s).lower()).strip("-")


def game_keys(matches):
    """Keys aligned with `matches`: the date, suffixed -<slug(opponent)> for every
    match whose date occurs more than once in `matches`."""
    dates = [str(m["date"]) for m in matches]
    return [d + ("-" + slug(m["opponent"]) if dates.count(d) > 1 else "")
            for d, m in zip(dates, matches)]


def game_fp(matches_up_to):
    """Fingerprint of the team's stats over a chronological prefix of games."""
    n = len(matches_up_to)
    runs_for = sum(m["team_total"] for m in matches_up_to)
    runs_against = sum(m["opponent_total"] for m in matches_up_to)
    last = str(matches_up_to[-1]["date"]) if matches_up_to else "none"
    return f"{n}g{runs_for}f{runs_against}a-{last}"


def _letter(entry):
    return {"fp": str(entry.get("fp", "")), "sections": entry.get("sections") or [],
            "players": entry.get("players") or []}


def is_legacy(notes):
    return bool(notes) and "letters" not in notes and any(
        isinstance(v, dict) and "_letter" in v for v in notes.values())


def convert_legacy(notes, seasons):
    """Each season's `_letter` becomes the letter of that season's last game."""
    history = [m for _, _, ms in seasons for m in ms]
    keys = game_keys(history)
    out, done = [], 0
    for _, label, ms in seasons:
        done += len(ms)
        entry = (notes.get(label) or {}).get("_letter") if ms else None
        if not entry:
            continue
        out.append({"game": keys[done - 1], "fp": game_fp(history[:done]),
                    "sections": entry.get("sections") or [],
                    "players": entry.get("players") or []})
    return out


def load_seasons(team_dir):
    """[(season_dir, label, matches)] for a team folder, chronological."""
    import stats_core
    season_re = re.compile(r"\d{4}-\d{2}-\d{2}$")
    out = []
    if not os.path.isdir(team_dir):
        return out
    for n in sorted(os.listdir(team_dir)):
        sd = os.path.join(team_dir, n)
        if season_re.match(n) and os.path.isdir(sd):
            ms = stats_core.load_matches(os.path.join(sd, "scorecards"))
            if ms:
                out.append((sd, ms[0]["season"], ms))
    return out


def _read_notes(team_dir):
    p = os.path.join(team_dir, NOTES_FILE)
    if not os.path.exists(p):
        return {}
    with open(p, encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def load_letters(team_dir, seasons=None):
    """{game_key: {"fp", "sections", "players"}} from the team's coach_notes.yaml.
    A legacy (per-season) file is converted in memory."""
    notes = _read_notes(team_dir)
    if is_legacy(notes):
        entries = convert_legacy(notes, seasons if seasons is not None else load_seasons(team_dir))
    else:
        entries = notes.get("letters") or []
    return {str(e["game"]): _letter(e) for e in entries if e.get("game")}


def status(seasons, letters):
    """One row per game across all seasons (chronological): {key, season, fp, state}
    with state ok | stale (a letter with another fp) | missing."""
    history = [(label, m) for _, label, ms in seasons for m in ms]
    matches = [m for _, m in history]
    rows = []
    for i, (key, (label, _)) in enumerate(zip(game_keys(matches), history)):
        fp = game_fp(matches[:i + 1])
        have = letters.get(key)
        state = "missing" if not have else ("ok" if str(have.get("fp")) == fp else "stale")
        rows.append({"key": key, "season": label, "fp": fp, "state": state})
    return rows


def latest_letter(matches, letters, history=None):
    """(key, letter) of the newest game in `matches` whose letter is ok, else (None, None).
    `history` is the team's all-time chronological games (default: `matches`);
    fingerprints are taken over it, as the letters were written."""
    history = list(history) if history is not None else list(matches)
    hkeys = game_keys(history)
    pos = {(str(m["date"]), m["opponent"]): i for i, m in enumerate(history)}
    for m in reversed(list(matches)):
        i = pos.get((str(m["date"]), m["opponent"]))
        if i is None:
            continue
        entry = letters.get(hkeys[i])
        if entry and str(entry.get("fp")) == game_fp(history[:i + 1]) and entry.get("sections"):
            return hkeys[i], entry
    return None, None


def _write_letters(team_dir, letters_list):
    p = os.path.join(team_dir, NOTES_FILE)
    with open(p, "w", encoding="utf-8") as fh:
        fh.write("# AI Coach letters — one per game, never rewritten (see scripts/coach.py).\n")
        yaml.safe_dump({"letters": letters_list}, fh, allow_unicode=True, sort_keys=False,
                       width=100)


def main(argv):
    import paths
    import report_data as RD
    seasons, _, _ = RD.load_all()
    if "--status" in argv:
        for row in status(seasons, load_letters(paths.TEAM_DIR, seasons)):
            if row["state"] != "ok":
                print("\t".join([row["key"], row["fp"], row["season"], row["state"]]))
        return 0
    if "--convert-legacy" in argv:
        notes = _read_notes(paths.TEAM_DIR)
        if not is_legacy(notes):
            print("coach_notes.yaml is already in the per-game form — nothing to convert.")
            return 0
        src = os.path.join(paths.TEAM_DIR, NOTES_FILE)
        shutil.copy2(src, os.path.join(paths.TEAM_DIR, "coach_notes.legacy.yaml"))
        out = convert_legacy(notes, seasons)
        _write_letters(paths.TEAM_DIR, out)
        print(f"converted {len(out)} season letter(s) to per-game letters "
              f"(old file kept as coach_notes.legacy.yaml)")
        return 0
    print(__doc__)
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    sys.exit(main(sys.argv[1:]))
