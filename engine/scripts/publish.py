#!/usr/bin/env python3
"""Publish: rebuild the app, commit the team data + site, push to main.

  python engine/scripts/publish.py "Game 2026-10-07 vs Opponents" [--no-push]

1. builds site/ from every team under Teams/ (build_site.py),
2. commits Teams/, site/ and .github/workflows/ with the message (no commit when
   nothing changed),
3. pushes the commit to origin's main branch (`git push origin HEAD:main`, which
   also works from a Claude Code cloud session's own branch). GitHub Actions then
   deploys site/ to Cloudflare Pages, usually within a minute.

Refuses to run in the engine repo itself (only the example team there).
"""
import argparse, os, subprocess, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_site            # imports paths in its multi-team mode
import paths

EXAMPLE_TEAM = "example-team"


def _git(repo, *args, check=True):
    r = subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if check and r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {r.stderr.strip() or r.stdout.strip()}")
    return r


def publish(message, push=True, branch="main"):
    """Build, commit and (optionally) push. Returns {committed, pushed, sha, note}."""
    repo = os.path.dirname(paths.TEAMS_DIR)
    teams = paths.team_folders()
    if not teams or teams == [EXAMPLE_TEAM]:
        raise SystemExit("!! nothing to publish here: this repo only has the example team. "
                         "Publish from your team's repo.")
    build_site.build(os.path.join(repo, "site"))
    # the team's data, the built app, and the deploy workflow (/setup writes the
    # Cloudflare project name into it)
    paths_to_add = ["Teams", "site"] + [p for p in (".github/workflows",)
                                        if os.path.isdir(os.path.join(repo, p))]
    _git(repo, "add", "--", *paths_to_add)
    committed = _git(repo, "diff", "--cached", "--quiet", check=False).returncode != 0
    if committed:
        _git(repo, "commit", "-q", "-m", message)
    sha = _git(repo, "rev-parse", "--short", "HEAD", check=False).stdout.strip() or None

    pushed, note = False, ""
    if not push:
        note = "push skipped"
    elif _git(repo, "remote", "get-url", "origin", check=False).returncode != 0:
        note = "no remote"
    else:
        r = _git(repo, "push", "origin", f"HEAD:{branch}", check=False)
        pushed = r.returncode == 0
        note = "pushed" if pushed else f"push failed: {(r.stderr or r.stdout).strip()}"
    return {"committed": committed, "pushed": pushed, "sha": sha, "note": note}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("message", help='commit message, e.g. "Game 2026-10-07 vs Opponents"')
    ap.add_argument("--no-push", action="store_true", help="commit only")
    ap.add_argument("--branch", default="main", help="branch to push to (default: main)")
    a = ap.parse_args(argv)
    r = publish(a.message, push=not a.no_push, branch=a.branch)
    print(f"Committed {r['sha']}: {a.message}" if r["committed"] else
          "Nothing changed since the last publish — no new commit.")
    if r["pushed"]:
        print(f"Pushed to {a.branch}. The app updates in about a minute.")
    elif r["note"] == "no remote":
        print("Not pushed: this repo has no GitHub remote yet (run /setup).")
    elif r["note"].startswith("push failed"):
        print(f"!! {r['note']}\n   Someone else published meanwhile: run `git pull --rebase origin "
              f"{a.branch}`, then publish again (site/ is rebuilt, so take either side of any "
              f"conflict in site/).")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
