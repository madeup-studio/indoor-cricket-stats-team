# Our team's cricket stats — context for Claude

This private repo turns photos of the team's indoor/action-cricket scorecards (Spawtz
cards) into verified stats, a coach letter after every game and a phone app the team
opens from a link. The person talking to you is a team admin and probably not a
programmer: run the commands yourself, keep explanations plain, show results rather
than code. Most sessions happen on a phone, in a Claude Code cloud session.

## How the repo works

- **The engine** (scripts, viewer, skills) is vendored in `engine/`. Run scripts from
  the repo root as `python engine/scripts/<script>.py`. Never edit `engine/`; it is
  replaced by `python engine/scripts/update_engine.py`.
- **Skills:** a new scorecard, a league table or a note → `add-scorecard`; the coach
  letter → `ai-coach`; first-time setup or Cloudflare changes → `setup`. The files
  in `.claude/skills/` are thin wrappers around `engine/.claude/skills/`.
- **The team** lives in `Teams/<Team>/`; `team.yaml` has its name exactly as printed
  on the cards, badge, colours, arena, league, the scoring `rules`, the `coach`
  settings, the viewer `gate` and the `admins`.
- **Season and display settings:** `Teams/<Team>/<season>/season.yaml` holds the
  season's `medal` (gold / silver / bronze), `finish` text and `closed`; `team.yaml` →
  `show` switches things in the app on or off (awards are off by default).
- **Source of truth:** `Teams/<Team>/<season>/data/*.json`, one file per game. All
  else is generated. Never hand-edit `stats/`, `scorecards/*.md` or `site/`; fix the
  game file and re-run the scripts.
- **Every number must reconcile:** `python engine/scripts/validate_ballbyball.py`
  ends with `ALL RECONCILE` before anything is published. Never bend a total to fit.
- **Publishing:** `python engine/scripts/publish.py "<message>"` rebuilds `site/`,
  commits and pushes; GitHub Actions deploys `site/` to Cloudflare Pages within a
  minute. `site/` and `engine/` are committed on purpose.
- **Admins:** if `team.yaml` lists `admins:` and the signed-in git user's email
  (`git config user.email`) is not one of them, don't change that team — tell the
  user and stop. (A courtesy guard between teams sharing a repo, not security.)

## Rules

- Player names, scorecards, letters and notes are the team's private data. Don't
  send them anywhere except this repo.
- Terminology: action cricket has no clubs. Teams play at an **arena** (owned by a
  franchise) in ability-based **leagues** (Mens E, Mens F …) with promotion and
  relegation.
- Python 3 with `pip install -r engine/requirements.txt`. PDFs are off by default
  (`pdf: false`); the team uses the app.
