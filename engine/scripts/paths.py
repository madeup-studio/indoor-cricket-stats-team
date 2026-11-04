#!/usr/bin/env python3
"""Shared path resolver. Layout:

  Teams/<TEAM>/                 team folder
    team.yaml                   team settings: name as printed on cards, badge, arena, colours
    players.yaml                team player list (name registry)
    seasons.md                  season inventory
    coach_notes.yaml            AI Coach letters
    <YYYY-MM-DD>/               one folder per season (named by start date)
      scorecards/               source images + rendered per-game .md
      data/                     one combined <date>.json per game (source of truth)
      stats/                    generated season report (.md + .html)
      context/                  league table, banter, anything the AI Coach should know

Teams/ is found by find_root() (or the TEAMS_DIR env var). The team is the TEAM
env var if set, otherwise the only folder in Teams/ that has a team.yaml.
Optionally restrict to one season with the SEASON env var (e.g. SEASON=2026-08-08).
Create a team with scripts/new_team.py.
"""
import os, re, sys
import yaml
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rules as _rules

ENGINE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def find_root(start):
    """The nearest ancestor of `start` (inclusive, up to 4 levels) holding a Teams/
    folder: the team repo root when the engine is vendored under engine/, the
    engine's own root otherwise."""
    d = os.path.abspath(start)
    for _ in range(5):
        if os.path.isdir(os.path.join(d, "Teams")):
            return d
        parent = os.path.dirname(d)
        if parent == d:
            break
        d = parent
    return ENGINE_ROOT


ROOT = find_root(os.path.dirname(os.path.abspath(__file__)))
TEAMS_DIR = os.environ.get("TEAMS_DIR") or os.path.join(ROOT, "Teams")


def team_folders():
    if not os.path.isdir(TEAMS_DIR):
        return []
    return [n for n in sorted(os.listdir(TEAMS_DIR))
            if os.path.isfile(os.path.join(TEAMS_DIR, n, "team.yaml"))]


def _pick_team():
    if os.environ.get("TEAM"):
        return os.environ["TEAM"]
    teams = team_folders()
    if len(teams) == 1:
        return teams[0]
    if os.environ.get("ACS_TEAM_OPTIONAL"):   # multi-team tools (build_site, publish)
        return None
    if not teams:
        sys.exit("No team set up yet. Run:  python scripts/new_team.py \"<team name as on the scorecard>\"")
    sys.exit(f"Several teams in Teams/ ({', '.join(teams)}). Pick one with the TEAM env var, "
             f"e.g. TEAM={teams[0]} python scripts/generate_stats.py")


# TEAM is None only when ACS_TEAM_OPTIONAL is set and no single team can be picked;
# tools that work on every team (build_site.py, publish.py) never read the TEAM_* values.
TEAM = _pick_team()
TEAM_DIR = os.path.join(TEAMS_DIR, TEAM) if TEAM else None
PLAYERS_FILE = os.path.join(TEAM_DIR, "players.yaml") if TEAM_DIR else None

_cfg_file = os.path.join(TEAM_DIR, "team.yaml") if TEAM_DIR else None
TEAM_CFG = (yaml.safe_load(open(_cfg_file, encoding="utf-8"))
            if _cfg_file and os.path.exists(_cfg_file) else None) or {}
TEAM_NAME = TEAM_CFG.get("name") or TEAM or ""    # exactly as printed on the scorecards
BADGE = TEAM_CFG.get("badge") or TEAM_NAME[:4]    # short text for the report logo
ARENA = TEAM_CFG.get("arena") or ""               # e.g. "Example Arena"
COLOURS = TEAM_CFG.get("colours") or {}           # optional: brand, gold (hex)
RULES = _rules.load_rules(TEAM_CFG)               # scoring rules (see scripts/rules.py)
COACH = {"enabled": True, "tone": "banter", "language": "en", **(TEAM_CFG.get("coach") or {})}
GATE = TEAM_CFG.get("gate") or "pin"              # how viewers get in: pin | email | none

SEASON_RE = re.compile(r"\d{4}-\d{2}-\d{2}$")


def season_dirs():
    """All season folders for the team (or just SEASON if that env var is set)."""
    only = os.environ.get("SEASON")
    if not TEAM_DIR:
        return []
    if only:
        return [os.path.join(TEAM_DIR, only)]
    if not os.path.isdir(TEAM_DIR):
        return []
    return [os.path.join(TEAM_DIR, n) for n in sorted(os.listdir(TEAM_DIR))
            if SEASON_RE.match(n) and os.path.isdir(os.path.join(TEAM_DIR, n))]


def data_dir(season_dir):       return os.path.join(season_dir, "data")
def cards_dir(season_dir):      return os.path.join(season_dir, "scorecards")
def stats_dir(season_dir):      return os.path.join(season_dir, "stats")
