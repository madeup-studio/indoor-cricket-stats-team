#!/usr/bin/env python3
"""Update the engine vendored in a team repo (run from the team repo's root).

  python engine/scripts/update_engine.py [--tag vX.Y.Z] [--dry-run]

Downloads the engine release (default: the latest release) from GitHub, replaces
engine/ with its engine files (VERSION, requirements.txt, scripts/, viewer/,
.claude/skills/) and prints the new version. Your Teams/ data is never touched.
After updating, rebuild and publish:  python engine/scripts/publish.py "Engine update"

The engine repo is ENGINE_REPO below (override with the ICS_ENGINE_REPO env var).
"""
import argparse, io, json, os, shutil, sys, tempfile, urllib.request, zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

ENGINE_REPO = os.environ.get("ICS_ENGINE_REPO") or "madeup-studio/indoor-cricket-stats"
ENGINE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def zip_url(tag):
    return f"https://github.com/{ENGINE_REPO}/archive/refs/tags/{tag}.zip"


def latest_url():
    return f"https://api.github.com/repos/{ENGINE_REPO}/releases/latest"


def _get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "indoor-cricket-stats-update"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def latest_tag():
    try:
        return json.loads(_get(latest_url()))["tag_name"]
    except Exception:       # no releases yet: fall back to the newest tag
        tags = json.loads(_get(f"https://api.github.com/repos/{ENGINE_REPO}/tags"))
        if not tags:
            sys.exit(f"!! no releases or tags found for {ENGINE_REPO}")
        return tags[0]["name"]


def install(zip_bytes, engine_dir):
    """Replace engine_dir with the engine file set from a GitHub source zip."""
    import make_template
    with tempfile.TemporaryDirectory() as tmp:
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
            z.extractall(tmp)
        tops = [d for d in os.listdir(tmp) if os.path.isdir(os.path.join(tmp, d))]
        if len(tops) != 1:
            sys.exit("!! unexpected archive layout")
        src = os.path.join(tmp, tops[0])
        if not os.path.isfile(os.path.join(src, "VERSION")):
            sys.exit("!! the archive has no VERSION file — not an engine release")
        staged = engine_dir + ".new"
        shutil.rmtree(staged, ignore_errors=True)
        make_template.copy_engine(src, staged)
        readme = os.path.join(engine_dir, "README.txt")
        if os.path.isfile(readme):
            shutil.copy2(readme, os.path.join(staged, "README.txt"))
        old = engine_dir + ".old"
        shutil.rmtree(old, ignore_errors=True)
        os.replace(engine_dir, old)
        os.replace(staged, engine_dir)
        shutil.rmtree(old, ignore_errors=True)
    with open(os.path.join(engine_dir, "VERSION"), encoding="utf-8") as fh:
        return fh.read().strip()


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tag", help="release tag, e.g. v1.0.0 (default: the latest release)")
    ap.add_argument("--dry-run", action="store_true", help="print what would be downloaded")
    a = ap.parse_args(argv)
    if a.dry_run:
        print(zip_url(a.tag) if a.tag else f"{latest_url()}  (then the tag's .zip from github.com)")
        return 0
    if os.path.basename(ENGINE_DIR) != "engine":
        sys.exit("!! run this inside a team repo: python engine/scripts/update_engine.py")
    tag = a.tag or latest_tag()
    print(f"downloading {zip_url(tag)}")
    version = install(_get(zip_url(tag)), ENGINE_DIR)
    print(f"engine updated to {version} ({tag}). Rebuild and publish next.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
