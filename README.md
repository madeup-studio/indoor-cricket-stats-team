# Our team's cricket stats

Scorecard photo in, team stats out: rankings, player pages, every game, records and
a letter from the AI coach after each game — in a small app the team opens from a
link on their phones.

This repo is your team's private copy. First time? Follow
[the setup guide](https://github.com/madeup-studio/indoor-cricket-stats/blob/main/docs/SETUP.md),
or open this repo in Claude Code and type `/setup`.

## Not made your copy yet?

If you are reading this on the template itself, start here. Only the admin (the person
who adds the scorecards) needs any of this; teammates just open a link and enter the
team code. You'll need:

- a **GitHub** account (free): https://github.com/signup
- a **Cloudflare** account (free): https://dash.cloudflare.com/sign-up
- a **Claude Pro or Max** plan: https://claude.ai/upgrade, and the Claude app on your phone
- about 20 minutes; the full guide is
  [docs/SETUP.md](https://github.com/madeup-studio/indoor-cricket-stats/blob/main/docs/SETUP.md)

Then make your team's private copy.
Either open this link in a web browser (the GitHub app hides the button) and fill in
the form: https://github.com/new?template_owner=madeup-studio&template_name=indoor-cricket-stats-team

Or let Claude do it. This needs **Claude Code** on a computer (the desktop app's
**Code** tab, or `claude` in a terminal), because it runs commands; normal chat at
claude.ai cannot. Paste this in exactly as it is; it will ask you what to call the repo:

```text
I want my own private copy of the indoor-cricket stats app, made from the template
https://github.com/madeup-studio/indoor-cricket-stats-team

1. First ask me what to call the repository (lowercase letters, numbers and dashes,
   for example our-team-stats) and wait for my answer. Call it NAME below.
2. Check the GitHub CLI is installed and signed in (`gh auth status`). If not, help me
   install it and run `gh auth login`, telling me exactly what to click.
3. Create a private repository called NAME under my account from that template, and
   clone it:
   gh repo create NAME --private --template madeup-studio/indoor-cricket-stats-team --clone
4. Do not run the setup wizard from here. Instead, finish with short next steps for
   me: the folder it was cloned into; open that folder in Claude Code (desktop app →
   Code → open the folder, or `cd` into it and run `claude`); type /setup and follow
   the wizard, about 20 minutes; or connect the Claude phone app to the new repo and
   run /setup there instead.

Setup guide, for reference:
https://github.com/madeup-studio/indoor-cricket-stats/blob/main/docs/SETUP.md
```

## After every game (from your phone)

1. Take a photo of the scorecard at the arena (or save the one from WhatsApp).
2. Open the **Claude** app → **Code** → choose this repo. Attach the photo and say
   **"new scorecard"**.
3. Answer Claude's questions — usually a new player's name, or a smudged ball.
4. Claude asks once for the league table: attach a screenshot of the standings (or
   say **"skip"**). Add any banter worth passing on to the coach in the same reply.
5. Claude checks every ball adds up, writes the coach's letter and publishes. The
   app updates about a minute later. Nothing to do in the app — just open the link.

Claude will ask permission to run its scripts and to push. Say yes.

## On a computer instead

Open this repo in Claude Code (the desktop app's **Code** tab, or `claude` in a
terminal), drop the photo into `inbox/` and say **"new scorecard"**. Same steps.

## Other things you can ask Claude

- "Rename Sam Unknown to Sam Smith" · "Sam's second spelling is Sammy 7 — merge them"
- "Add a photo for Sam" (attach it) · "Change our colours to …"
- "New season starts on 2027-01-12" · "Switch the coach to encouraging"
- "Change the team code" (everyone re-enters the new code once)
- "Turn on the PDF stat cards" (off by default; the app has everything)
- "We finished second this season" · "Mark the game on 2026-11-20 as the final"
- "Hide best partnership" · "Show awards"
- "Add Sam as an admin" · "Give the coach a personality: a grumpy old pro"

## What's where

```
Teams/<team>/            your data: team.yaml, players.yaml, coach letters, one folder per season
site/                    the built app (generated, committed, deployed by GitHub Actions)
engine/                  the stats engine (don't edit; update with engine/scripts/update_engine.py)
inbox/                   photos waiting to be processed (computer flow)
```

## No support promised

This runs on the free open-source engine
[indoor-cricket-stats](https://github.com/madeup-studio/indoor-cricket-stats). It is
shared as-is: there is no support, and you run your own copy on your own accounts.
