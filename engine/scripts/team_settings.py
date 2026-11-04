#!/usr/bin/env python3
"""Default `show:` switches in team.yaml (what the app displays), the comment written
beside each, and a merge of a team's own switches over those defaults."""

SHOW_DEFAULTS = {
    "awards": False,
    "medals": True,
    "stage_tags": True,
    "streaks": True,
    "partnerships": True,
    "hattricks": True,
    "records": {
        "high_total": True,
        "low_total": True,
        "biggest_win": True,
        "heaviest_loss": True,
        "best_skin": True,
        "most_wkts_game": True,
        "fewest_extras_game": True,
        "best_contribution": True,
        "most_runs_game": True,
        "best_econ": True,
        "most_runouts_created": True,
    },
}

SHOW_NOTES = {
    "awards": "player / batter / bowler of the season (finished seasons)",
    "medals": "the season's medal icon in the season menu",
    "stage_tags": '"Playoff" / "Final" tags on games',
    "streaks": "longest winning / losing runs",
    "partnerships": "best partnership record",
    "hattricks": "the hat-trick records (there is no player-page count)",
    "records": "individual record cards; a key set to false hides that card",
}


def merge_show(cfg):
    show = cfg.get("show")
    if not isinstance(show, dict):
        show = {}
    merged = {k: v for k, v in SHOW_DEFAULTS.items() if k != "records"}
    for key in merged:
        if key in show:
            merged[key] = bool(show[key])
    records = dict(SHOW_DEFAULTS["records"])
    given = show.get("records")
    if isinstance(given, dict):
        for key in records:
            if key in given:
                records[key] = bool(given[key])
    merged["records"] = records
    return merged
