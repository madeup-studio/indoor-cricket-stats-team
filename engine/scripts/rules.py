#!/usr/bin/env python3
"""Scoring rules: presets, the team's rules (team.yaml -> rules) and the per-game
snapshot (meta.rules in each game file, which always wins so a later change of
arena or rules never rewrites history).

team.yaml:
  rules:
    preset: indoor-sa        # starting point; any key below overrides the preset
    wicket_runs: -5          # a dismissal's run penalty (some arenas use -3)
    extra_runs: 2            # base value of a wide / no-ball
    balls_per_over: 6
    extra_ball_last_over: true   # the optional extra ball in a skin's last over
    skins: 4
    overs_per_pair: 4
    players_per_side: 8

New presets are welcome by pull request: add an entry to PRESETS.
"""

RULE_KEYS = ("wicket_runs", "extra_runs", "balls_per_over", "extra_ball_last_over",
             "skins", "overs_per_pair", "players_per_side")

PRESETS = {
    "indoor-sa": dict(wicket_runs=-5, extra_runs=2, balls_per_over=6,
                      extra_ball_last_over=True, skins=4, overs_per_pair=4,
                      players_per_side=8),
}
DEFAULT_PRESET = "indoor-sa"


def _check_keys(d, where):
    unknown = sorted(set(d) - set(RULE_KEYS))
    if unknown:
        raise ValueError(f"unknown rules key(s) in {where}: {', '.join(unknown)} "
                         f"(allowed: {', '.join(RULE_KEYS)})")


def load_rules(team_cfg):
    """The team's rules: its preset (default indoor-sa) with any overriding keys."""
    cfg = dict(((team_cfg or {}).get("rules") or {}))
    preset = cfg.pop("preset", None) or DEFAULT_PRESET
    if preset not in PRESETS:
        raise ValueError(f"unknown rules preset {preset!r} (known: {', '.join(sorted(PRESETS))})")
    _check_keys(cfg, "team.yaml rules")
    return {**PRESETS[preset], **cfg}


def game_rules(game, team_rules):
    """The rules a game was scored under: its meta.rules snapshot over the team's."""
    snap = dict(((game.get("meta") or {}).get("rules") or {}))
    snap.pop("preset", None)
    _check_keys(snap, "meta.rules")
    return {**team_rules, **snap}


def skin_ball_counts(rules):
    """Allowed balls in one skin (both batters together)."""
    n = rules["overs_per_pair"] * rules["balls_per_over"]
    return {n, n + 1} if rules["extra_ball_last_over"] else {n}


def max_cells_last_over(rules):
    """Most cells the last over of a skin may hold."""
    return rules["balls_per_over"] + (1 if rules["extra_ball_last_over"] else 0)
