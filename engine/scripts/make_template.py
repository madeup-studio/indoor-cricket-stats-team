#!/usr/bin/env python3
"""Assemble the team template: what a new team's private repo starts from.

  python scripts/make_template.py [--out dist/team-template]

OUT gets everything in template/ plus the engine vendored into engine/:
  engine/VERSION, engine/requirements.txt, engine/scripts/ (incl. templates/),
  engine/viewer/ (no tests), engine/.claude/skills/
and a thin wrapper skill per engine skill in .claude/skills/ (same name and
description; the body points at the engine's copy), because Claude Code finds
skills only at the repo root.

Refuses (exit 1) when the leak check finds a forbidden identifier in the output
(identifier list from the LEAK_LIST env var) or when any team data slipped in.
"""
import argparse, os, re, shutil, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import leak_check

ENGINE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATE_DIR = os.path.join(ENGINE_ROOT, "template")
DEFAULT_OUT = os.path.join(ENGINE_ROOT, "dist", "team-template")

ENGINE_FILES = ("VERSION", "requirements.txt")
ENGINE_DIRS = ("scripts", "viewer", ".claude/skills")
SKIP_DIRS = {"__pycache__", "tests", "node_modules", ".pytest_cache"}


def _skip(rel):
    parts = rel.replace(os.sep, "/").split("/")
    if any(p in SKIP_DIRS for p in parts[:-1]):
        return True
    name = parts[-1]
    return (name.endswith((".pyc", ".test.js")) or name == ".DS_Store"
            or rel.replace(os.sep, "/") == "viewer/package.json")


def engine_files(src_root):
    """Relative paths (posix) of the engine file set under src_root."""
    out = [f for f in ENGINE_FILES if os.path.isfile(os.path.join(src_root, f))]
    for d in ENGINE_DIRS:
        base = os.path.join(src_root, d)
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames[:] = sorted(x for x in dirnames if x not in SKIP_DIRS)
            for f in sorted(filenames):
                rel = os.path.relpath(os.path.join(dirpath, f), src_root).replace(os.sep, "/")
                if not _skip(rel):
                    out.append(rel)
    return out


def copy_engine(src_root, engine_dir):
    written = []
    for rel in engine_files(src_root):
        dst = os.path.join(engine_dir, *rel.split("/"))
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(os.path.join(src_root, *rel.split("/")), dst)
        written.append(dst)
    return written


def frontmatter(text):
    m = re.match(r"^---\n(.*?)\n---\n", text.replace("\r\n", "\n"), re.S)
    return m.group(1) if m else None


def wrapper_skill(name, engine_skill_text):
    fm = frontmatter(engine_skill_text)
    if fm is None:
        raise ValueError(f"engine skill {name} has no frontmatter")
    return (f"---\n{fm}\n---\n\n"
            f"Read and follow `engine/.claude/skills/{name}/SKILL.md`. Run scripts as "
            f"`python engine/scripts/<script>.py` from the repo root (in that file, "
            f"`$ENGINE` means `engine`).\n")


def _safe_to_replace(out_dir):
    if not os.path.exists(out_dir):
        return True
    if not os.listdir(out_dir):
        return True
    return os.path.isfile(os.path.join(out_dir, "engine", "VERSION"))   # an earlier template


def assemble(out_dir):
    """Build the template into out_dir; returns the files written."""
    out_dir = os.path.abspath(out_dir)
    if not _safe_to_replace(out_dir):
        sys.exit(f"!! {out_dir} exists and is not a team template; refusing to overwrite it")
    shutil.rmtree(out_dir, ignore_errors=True)
    shutil.copytree(TEMPLATE_DIR, out_dir,
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store"))
    written = [os.path.join(dp, f) for dp, _, fs in os.walk(out_dir) for f in fs]
    written += copy_engine(ENGINE_ROOT, os.path.join(out_dir, "engine"))
    skills_src = os.path.join(ENGINE_ROOT, ".claude", "skills")
    for name in sorted(os.listdir(skills_src)):
        src = os.path.join(skills_src, name, "SKILL.md")
        if os.path.isfile(src):
            dst = os.path.join(out_dir, ".claude", "skills", name, "SKILL.md")
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            with open(src, encoding="utf-8") as fh, open(dst, "w", encoding="utf-8", newline="\n") as out:
                out.write(wrapper_skill(name, fh.read()))
            written.append(dst)

    problems = []
    teams = os.path.join(out_dir, "Teams")
    problems += [f"!! team data in the template: Teams/{e}" for e in
                 (sorted(os.listdir(teams)) if os.path.isdir(teams) else []) if e != "README.txt"]
    if os.environ.get("LEAK_LIST"):
        ids = leak_check.load_list(os.environ["LEAK_LIST"])
        problems += [f"!! leak: {p}: {i}" for p, i in leak_check.scan(out_dir, ids)]
    problems += [f"!! structure: {e}" for e in leak_check.structure_errors(out_dir)]
    if problems:
        print("\n".join(problems))
        shutil.rmtree(out_dir, ignore_errors=True)
        sys.exit(1)
    return written


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=DEFAULT_OUT)
    a = ap.parse_args(argv)
    files = assemble(a.out)
    with open(os.path.join(ENGINE_ROOT, "VERSION"), encoding="utf-8") as fh:
        version = fh.read().strip()
    print(f"team template: {os.path.abspath(a.out)} — engine {version}, {len(files)} files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
