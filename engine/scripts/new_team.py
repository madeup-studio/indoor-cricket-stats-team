#!/usr/bin/env python3
"""Set up a team folder (first run) or add a new season folder to it.

  python scripts/new_team.py "Team Name" --arena "Example Arena" [--badge ABC]
         [--league "Mens E"] [--preset indoor-sa] [--tone banter] [--gate pin] [--no-coach]
      creates Teams/<folder>/ with team.yaml, players.yaml, seasons.md,
      coach_notes.yaml and photos/  (folder defaults to the name, spaces -> '-')

  python scripts/new_team.py --season-start 2026-10-12
      adds Teams/<TEAM>/2026-10-12/{data,scorecards,stats,context}/ for a new season
      (name the folder by the season's START date; the arena website lists it)

Both can be combined on first run. The team name must be spelled exactly as it is
printed on the scorecards.
"""
import argparse, datetime, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rules
import team_settings
_had_optional = "ACS_TEAM_OPTIONAL" in os.environ
os.environ.setdefault("ACS_TEAM_OPTIONAL", "1")    # no team yet is fine here
import paths
if not _had_optional:
    del os.environ["ACS_TEAM_OPTIONAL"]

ROOT = paths.ROOT                  # the repo holding Teams/ (team repo or engine repo)
TEAMS_DIR = paths.TEAMS_DIR
TONES = ("banter", "encouraging", "serious")
GATES = ("pin", "email", "none")


def _rel(path):
    try:
        return os.path.relpath(path, ROOT)
    except ValueError:      # on another drive (Windows)
        return path


def write(path, text):
    if os.path.exists(path):
        print("  exists, kept:", _rel(path))
        return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    open(path, "w", encoding="utf-8").write(text)
    print("  created:", _rel(path))


def default_badge(name):
    words = re.findall(r"[A-Za-z0-9]+", name)
    if len(words) > 1:
        return "".join(w[0] for w in words).upper()[:4]
    return name[:4].upper()


RULE_NOTES = dict(
    wicket_runs="a dismissal's run penalty (some arenas use -3)",
    extra_runs="base value of a wide / no-ball (plus any runs off it)",
    balls_per_over="balls in an over",
    extra_ball_last_over="the optional extra ball in a skin's last over",
    skins="skins (pairs) per innings",
    overs_per_pair="overs each pair faces",
    players_per_side="players per team")


def team_yaml(name, arena, badge, league="", preset=rules.DEFAULT_PRESET, tone="banter",
              gate="pin", coach_enabled=True):
    """team.yaml text for a new team: the spec's layout with every rule written out."""
    def line(key, val, note):
        return f"{key}: {val}".rstrip().ljust(30) + f"# {note}\n"

    def yv(v):
        return ("true" if v else "false") if isinstance(v, bool) else str(v)

    out = ["# Team settings — read by every script (see scripts/paths.py).\n",
           line("name", f'"{name}"', "exactly as printed on the scorecards"),
           line("badge", f'"{badge}"', "short text for the logo (max ~4 chars)"),
           line("arena", f'"{arena}"', "where the team plays (the arena runs the leagues)"),
           line("league", f'"{league}"', "current league at the arena (informational)"),
           line("colours", "", "brand colours (hex)"),
           '  brand: "#4f46e5"\n',
           '  gold: "#f5b301"\n',
           line("publish_unconfirmed", "true",
                "publish a reconciled game even if a name is unconfirmed (flagged)"),
           line("pdf", "false", "also build the PDF stat cards"),
           "\n",
           line("game_type", "indoor", "the only implemented type"),
           "rules:\n",
           line("  preset", preset, "starting point; any value below overrides the preset")]
    out += [line(f"  {k}", yv(v), RULE_NOTES[k]) for k, v in rules.PRESETS[preset].items()]
    out += ["\n",
            "coach:\n",
            line("  enabled", yv(coach_enabled), "false = no Coach tab, no letter"),
            line("  tone", tone, "banter | encouraging | serious"),
            line("  language", "en", "the letter's language (e.g. af)"),
            line("  persona", '""',
                 'optional: one line of flavour for the coach, e.g. "a grumpy old pro"'),
            "\n",
            line("gate", gate, "how viewers get in: pin | email | none"),
            line("admins", "[]", "email addresses of this team's admins"),
            "\n",
            line("show", "", team_settings.SHOW_NOTES.get(
                "show", "what the app shows; false hides it (stats still computed)"))]
    for k, v in team_settings.SHOW_DEFAULTS.items():
        if isinstance(v, dict):
            out.append(line(f"  {k}", "", team_settings.SHOW_NOTES[k]))
            out += [f"    {rk}: {yv(rv)}\n" for rk, rv in v.items()]
        else:
            out.append(line(f"  {k}", yv(v), team_settings.SHOW_NOTES[k]))
    return "".join(out)


def create_team(name, folder, arena, badge, league="", preset=rules.DEFAULT_PRESET,
                tone="banter", gate="pin", coach_enabled=True):
    team_dir = os.path.join(TEAMS_DIR, folder)
    print(f"Team '{name}' -> {_rel(team_dir)}")
    write(os.path.join(team_dir, "team.yaml"),
          team_yaml(name, arena, badge, league, preset, tone, gate, coach_enabled))
    write(os.path.join(team_dir, "players.yaml"),
          "# Team player list & name registry (one per team).\n"
          "#   as    : exactly how the name is printed on a scorecard (do not change).\n"
          "#   name  : the confirmed full name. Fill this in to clear an ambiguity; the\n"
          "#           reports then show this instead of the scorecard spelling.\n"
          "#   aka   : optional OTHER scorecard spellings that are the SAME person\n"
          "#           (they get merged together in the season stats).\n"
          "# Check new names after adding scorecards:  python scripts/roster.py --check\n"
          "roster: []\n")
    write(os.path.join(team_dir, "seasons.md"),
          f"# {name} — seasons & game inventory\n\n"
          "One folder per season, named by the season **start date** (YYYY-MM-DD). Every\n"
          "transcribed game has fully-reconciled ball-by-ball (each batter's runs, each\n"
          "bowler's runs/wickets and the skin totals cross-check).\n\n"
          "| Season | League | Folder | Games transcribed |\n"
          "|--------|--------|--------|-------------------|\n")
    write(os.path.join(team_dir, "coach_notes.yaml"),
          "# AI Coach letters — one per game, written by Claude with the ai-coach skill and\n"
          "# never rewritten (see scripts/coach.py):\n"
          "#   - {game: \"<date>[-<opponent-slug>]\", fp, sections: [{title, html}],\n"
          "#      players: [{name, note}]}\n"
          "letters: []\n")
    write(os.path.join(team_dir, "photos", "README.txt"),
          "Player photos for the PDF report's player pages.\n\n"
          "One image per player, named by the player's display name in lowercase-kebab\n"
          "form, as .jpg / .jpeg / .png (e.g. sam.jpg, sam-smith.png). Square images look\n"
          "best. Until a photo exists the report shows the player's initials.\n")
    return team_dir


def create_season(team_dir, start):
    datetime.date.fromisoformat(start)   # validates YYYY-MM-DD
    sd = os.path.join(team_dir, start)
    print(f"Season folder {_rel(sd)}")
    for sub in ("data", "scorecards", "stats"):
        os.makedirs(os.path.join(sd, sub), exist_ok=True)
    write(os.path.join(sd, "context", "README.md"),
          "# Season context (supplemental, non-scorecard info)\n\n"
          "Anything that is NOT a scorecard but should inform the reports and the AI Coach\n"
          "letter: league table screenshots transcribed to text, fixtures, comments about a\n"
          "game, guest players, banter material.\n\n"
          "- One file per upload, named `YYYY-MM-DD-<topic>.md` (date = when the info was true).\n"
          "- Keep data faithful to the source (transcribe tables as markdown tables).\n"
          "- Context only: never parsed by the stats pipeline, never overrides scorecards.\n")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("name", nargs="?", help="team name exactly as printed on the scorecards")
    ap.add_argument("--arena", default="", help='e.g. "Example Arena"')
    ap.add_argument("--badge", help="2-4 characters for the report logo (default: initials)")
    ap.add_argument("--league", default="", help='current league at the arena, e.g. "Mens E"')
    ap.add_argument("--preset", default=rules.DEFAULT_PRESET, choices=sorted(rules.PRESETS),
                    help="scoring rules preset (default: %(default)s)")
    ap.add_argument("--tone", default="banter", choices=TONES, help="AI coach tone")
    ap.add_argument("--gate", default="pin", choices=GATES, help="how viewers get in")
    ap.add_argument("--no-coach", action="store_true", help="turn the AI coach off")
    ap.add_argument("--folder", help="folder name under Teams/ (default: the name)")
    ap.add_argument("--season-start", help="YYYY-MM-DD: also create this season's folder")
    a = ap.parse_args()

    if a.name:
        folder = a.folder or re.sub(r"[^A-Za-z0-9]+", "-", a.name).strip("-")
        team_dir = create_team(a.name, folder, a.arena, a.badge or default_badge(a.name),
                               a.league, a.preset, a.tone, a.gate, not a.no_coach)
    elif a.season_start:
        team_dir = paths.TEAM_DIR      # the TEAM env var or the only team
        if not team_dir:
            teams = paths.team_folders()
            sys.exit("No team set up yet: give the team name too." if not teams else
                     f"Several teams ({', '.join(teams)}): pick one with the TEAM env var.")
    else:
        ap.error("give a team name (first run) and/or --season-start YYYY-MM-DD")
    if a.season_start:
        create_season(team_dir, a.season_start)


if __name__ == "__main__":
    main()
