#!/usr/bin/env python3
"""Per-season metadata. An optional <season>/season.yaml holds what the admin states
(medal, finish, closed); a season counts as finished once a later one exists, it is
closed, or it has a medal."""
import os
import yaml

MEDALS = ("gold", "silver", "bronze")


def load(season_dir):
    path = os.path.join(season_dir, "season.yaml")
    data = {}
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    medal = data.get("medal")
    if medal is not None and medal not in MEDALS:
        raise ValueError(f"{path}: medal must be one of gold/silver/bronze, got {medal!r}")
    finish = data.get("finish")
    if finish is not None:
        finish = str(finish)
    return {"medal": medal, "finish": finish, "closed": bool(data.get("closed", False))}


def is_finished(index, n_seasons, meta):
    return index < n_seasons - 1 or meta["closed"] or bool(meta["medal"])
