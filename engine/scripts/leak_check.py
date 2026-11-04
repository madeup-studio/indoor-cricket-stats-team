#!/usr/bin/env python3
"""Leak check: refuse to publish anything that names a real team or player.

  python scripts/leak_check.py [--root PATH] [--list FILE]

Two checks:
  1. Identifier scan — every text file (tracked + untracked-not-ignored when ROOT is
     a git repo, else every file) is searched for each forbidden identifier as a
     whole word, case-sensitive. The list comes from --list or the LEAK_LIST env
     var: one identifier per line, `#` comments allowed. The list lives OUTSIDE
     this repo (the owner's private hub) — never commit it here.
  2. Structure guard (the public engine repo only) — Teams/ may hold nothing but
     example-team, and site/, dist/ and engine/ must not be tracked. Skipped for a
     team repo or the team template (they vendor the engine in engine/).

Without a list only the structure guard runs. Exit 1 on any hit, printing
`!! leak: <path>: <identifier>` / `!! structure: <message>` lines.
"""
import argparse, os, re, subprocess, sys

ALLOWED_TEAM = "example-team"
NEVER_TRACKED = ("site/", "dist/", "engine/")
SKIP_DIRS = {".git", ".venv", "node_modules", "__pycache__", ".pytest_cache", ".superpowers"}


def _git_files(root):
    """Tracked + untracked-not-ignored files (posix paths), or None if not a git repo."""
    try:
        r = subprocess.run(["git", "-C", root, "ls-files", "--cached", "--others",
                            "--exclude-standard"], capture_output=True, text=True,
                           encoding="utf-8")
    except OSError:
        return None
    if r.returncode != 0:
        return None
    # only trust it when root is the top of the work tree, not a folder inside one
    top = subprocess.run(["git", "-C", root, "rev-parse", "--show-toplevel"],
                         capture_output=True, text=True, encoding="utf-8").stdout.strip()
    if not top or os.path.normcase(os.path.realpath(top)) != os.path.normcase(os.path.realpath(root)):
        return None
    return sorted({p for p in r.stdout.splitlines() if p})


def _walk_files(root):
    out = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for f in filenames:
            out.append(os.path.relpath(os.path.join(dirpath, f), root).replace(os.sep, "/"))
    return sorted(out)


def _read_text(path):
    """File contents as str, or None for binaries / non-UTF-8 files."""
    try:
        with open(path, "rb") as fh:
            data = fh.read()
    except OSError:
        return None
    if b"\0" in data[:1024]:
        return None
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return None


def scan(root, identifiers, files=None):
    """(relative_path, identifier) for every whole-word, case-sensitive hit."""
    if files is None:
        files = _git_files(root)
        if files is None:
            files = _walk_files(root)
    pats = [(i, re.compile(r"(?<!\w)%s(?!\w)" % re.escape(i))) for i in identifiers if i]
    hits = []
    for rel in files:
        if rel.startswith(".git/"):
            continue
        text = _read_text(os.path.join(root, rel))
        if text is None:
            continue
        hits += [(rel, ident) for ident, pat in pats if pat.search(text)]
    return hits


def structure_errors(root):
    """Public-engine-repo guard; [] for a team repo / template (engine/VERSION exists)."""
    if os.path.isfile(os.path.join(root, "engine", "VERSION")):
        return []
    errs = []
    files = _git_files(root)
    if files is None:   # not a git repo: judge the folders on disk
        teams_dir = os.path.join(root, "Teams")
        entries = sorted(os.listdir(teams_dir)) if os.path.isdir(teams_dir) else []
        errs += [f"Teams/{e} is not allowed here (only Teams/{ALLOWED_TEAM}/)"
                 for e in entries if e != ALLOWED_TEAM]
        return errs
    bad_teams = sorted({p.split("/")[1] for p in files
                        if p.startswith("Teams/") and p.split("/")[1] != ALLOWED_TEAM})
    errs += [f"Teams/{t} is tracked (only Teams/{ALLOWED_TEAM}/ may be)" for t in bad_teams]
    for d in NEVER_TRACKED:
        if any(p.startswith(d) for p in files):
            errs.append(f"{d} is tracked (build output / vendored engine never belong in this repo)")
    return errs


def load_list(path):
    with open(path, encoding="utf-8") as fh:
        return [ln.strip() for ln in fh if ln.strip() and not ln.strip().startswith("#")]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    ap.add_argument("--list", default=os.environ.get("LEAK_LIST"))
    a = ap.parse_args(argv)
    root = os.path.abspath(a.root)
    bad = 0
    if a.list:
        for path, ident in scan(root, load_list(a.list)):
            print(f"!! leak: {path}: {ident}")
            bad += 1
    else:
        print("(no identifier list: set LEAK_LIST or pass --list; structure guard only)")
    for e in structure_errors(root):
        print(f"!! structure: {e}")
        bad += 1
    print(f"leak check: {'FAILED, ' + str(bad) + ' problem(s)' if bad else 'clean'}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
