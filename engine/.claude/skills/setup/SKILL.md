---
name: setup
description: Set up this team's stats app from scratch, step by step — Cloudflare account and token, how viewers get in (team code, email list or open link), the Cloudflare Pages project, the GitHub secrets, the first deploy, then the team itself and its first scorecard. Use when the user types /setup, says "set up", "get started", "first time", or wants to change the team code, the gate or the Cloudflare project.
---

# Setup wizard

> **Paths:** run scripts as `python $ENGINE/scripts/<script>.py` from the repo root, where
> `$ENGINE` is `engine` in a team repo and `.` in the engine repo itself.

Walk the user through setup **one step per message**. Each step ends with "tell me
when that's done" (or the question it needs answered). The user is probably on a
phone and not a developer: short sentences, exact button names, one link per step.
Check `site/`, `.github/workflows/deploy.yml` and `Teams/` first and skip any step
that is already done. Total time: about 20 minutes.

**Secrets:** never repeat the Cloudflare token back, never commit it, never write it
anywhere except `.cf-token` (gitignored). Delete it at the end (step 8).

## 0. Where are we?

Confirm this is the team's own repo (it has `engine/` and `Teams/README.txt`) and
that Python works: `python -m pip install -r engine/requirements.txt`. If this is the
engine repo instead, stop: teams set up from their copy of the template.

`setup.py` talks to api.cloudflare.com. In a Claude Code **cloud** session that
domain is blocked unless the environment allows it. If `--check` says it "can't
reach api.cloudflare.com", tell the user the two ways out: add `api.cloudflare.com`
to the cloud environment's allowed domains (Network access → Custom), or run
`/setup` once from Claude Code on a computer. Everything after setup works from
the phone.

## 1. A Cloudflare account (free)

Sign up at https://dash.cloudflare.com/sign-up (skip it if they have one). No card
is needed for the team-code or open-link options.

## 2. An API token

At https://dash.cloudflare.com/profile/api-tokens: **Create Token** → use the
**Edit Cloudflare Workers** template → **Continue to summary** → **Create Token** →
copy it and paste it here. (Custom token instead: Account › Cloudflare Pages: Edit
and Account › Account Settings: Read.)
Save the pasted token to `.cf-token` at the repo root, then run
`python $ENGINE/scripts/setup.py --check`. Say it's saved for setup only and is
deleted at the end.

## 3. How does the team get in?

Ask once, with these three options:
- **Team code** (recommended): one code for the whole team, posted in the team's
  WhatsApp group. Each phone enters it once and stays in for 6 months. Change the
  code when someone leaves; everyone re-enters it once.
- **Email list**: only people on a list get in, with a one-time code sent by email.
  Needs Cloudflare Zero Trust (free, asks for a card) and everyone's email address.
- **Open link**: anyone with the link can look. No protection beyond the link.

## 4. The Cloudflare project

Propose a project name from the repo name (`git remote get-url origin`; lowercase,
dashes) and confirm it: it becomes `<name>.pages.dev`. Then:
`python $ENGINE/scripts/setup.py --create <name>` and
`python $ENGINE/scripts/setup.py --gate <pin|email|none>`
(for a code the user wants: `--gate pin --pin <code>`, at least 6 characters;
otherwise an 8-digit code is generated — note it for step 8).
**Email list:** also give these steps, then wait: at https://one.dash.cloudflare.com/
pick a team name and the free plan → Access → Applications → Add an application →
Self-hosted → domain `<name>.pages.dev` → a policy "Allow" with the emails they
list (and the admins). Cloudflare emails each person a code when they open the app.

## 5. Two GitHub secrets

Link: `https://github.com/<owner>/<repo>/settings/secrets/actions` (from the git
remote). **New repository secret** twice:
- `CLOUDFLARE_API_TOKEN` — the same token they pasted in step 2 (don't show it).
- `CLOUDFLARE_ACCOUNT_ID` — print the account ID from step 4.

## 6. The team

Ask in one message (offer defaults): the team name **exactly as printed on the
scorecards**, the arena, the current league, a badge (2–4 letters), the rules
(standard `indoor-sa`: −5 a wicket, 2 an extra, 6-ball overs; anything different?),
and "Do you want the AI coach's letter after each game? (yes / no)" and, if yes, its
tone (banter, encouraging or serious). Then
`python $ENGINE/scripts/new_team.py "<name>" --arena "<arena>" --league "<league>"
--badge <XX> --tone <tone> --gate <gate>`. A "no" adds `--no-coach` and drops `--tone`.
If a rule differs, set it under `rules:` in the new `team.yaml`. Also put the user's email (`git config user.email`)
in `admins:`. Ask for the season's start date if they know it and add it with
`--season-start` (otherwise the first scorecard does).

## 7. First deploy

`python $ENGINE/scripts/publish.py "Set up the team app"` — this builds the app,
commits (including the deploy workflow) and pushes; GitHub Actions deploys it.
Check the run at `https://github.com/<owner>/<repo>/actions` with the user if it
fails (usually a secret name typo). On a computer with Node.js you can also run
`python $ENGINE/scripts/setup.py --deploy` directly.

## 8. Hand over

`python $ENGINE/scripts/setup.py --forget` (deletes `.cf-token`). Then give the user,
ready to paste into the team group: the link (`https://<name>.pages.dev`) and, for
the team-code gate, the code. Tell them "Add to Home Screen" on the phone gives an
app icon. Then ask for the first scorecard photo and continue with `add-scorecard`.

## Later changes

- **New team code / change gate:** steps 2 and 4 (`--gate`), then
  `publish.py "Change the team code"` or `setup.py --deploy` — the new setting
  applies from the next deploy — then step 8.
- **Status:** `python $ENGINE/scripts/setup.py --status`.
