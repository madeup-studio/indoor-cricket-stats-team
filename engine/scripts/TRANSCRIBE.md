# Scorecard transcription guide (for transcription agents)

Transcribe ONE Spawtz action-cricket scorecard image into one combined per-game
JSON for our team (its name, exactly as printed on the cards, is `name` in
`Teams/<TEAM>/team.yaml`). Accuracy is critical — **every number must reconcile**.

## Background
Action cricket: 2 teams × 8 players, batting in **4 pairs = 4 skins**; each pair
faces 4 overs (one per opposing bowler; each bowler bowls 2 overs, so OB=2).

**Rules come from the team.** The scoring constants used below are the team's
`rules` in `team.yaml` (defaults in brackets): `wicket_runs` (−5), `extra_runs` (2),
`balls_per_over` (6), `extra_ball_last_over` (true), `skins` (4), `overs_per_pair`
(4), `players_per_side` (8). Where this guide says "the wicket value" or "an over's
balls", read the team's value. Copy the team's whole `rules` block into the game's
`meta.rules` so the game keeps the rules it was scored under.

## Step 1 — enlarge the grid (the photos are low-res)
Crop horizontal bands and upscale with the repo tool, into a scratch dir:
```
python $ENGINE/scripts/crop_scorecard.py "<IMAGE>" "<SCRATCH>" \
  --band d1:0.205:0.262 --band d2:0.258:0.312 --band d3:0.302:0.360 --band d4:0.353:0.410 \
  --band o1:0.447:0.505 --band o2:0.503:0.560 --band o3:0.558:0.616 --band o4:0.614:0.672
```
`d*` = the first-innings grid (upper half), `o*` = the second-innings grid (lower
half). Read the PNGs with the Read tool. Add `--x0 0.585` on a re-crop to capture the
clipped **4th-bowler column + batter totals**. If a band is misaligned (wrong rows),
re-crop with shifted y-fractions. Photos vary — adjust until every row is legible.

## Step 2 — header
Date/Time; the card's "League:" line → **arena + season + league** (e.g. `Example Arena - Spring 2026 - Mens E`: arena, season, league — read E vs F carefully); Umpire; Court;
the **Skins** table (skins 1-4 + TOTAL + skins-won for both teams); **Player of the
match** (+ team). If the header is cropped off, use the date given to you and leave
unknown text fields null.

## Step 3 — bottom summary tables (AUTHORITATIVE)
One table per team; each player row: RS, OB, RC, Wkts, Econ, C. Verify each team's
RS sums to its TOTAL, and C = RS − RC on every row.

## Step 4 — ball-by-ball, BOTH innings
Each cell is one ball: integer = runs off the bat (0-7); circled letter = a
**dismissal worth the team's `wicket_runs`** (default −5) (R=run out, C=caught,
B=bowled, S=stumped, L=lbw, H=hit wicket, M=mankad); w/nb = wide/no-ball extras,
worth `extra_runs` (default 2) plus any runs off them. The **bold cell** ending each
bowler block = that batter's runs off that over. The `X/YY` line under a bowler =
wickets/runs conceded that over. An over's total = its runs off the bat + the
wicket value × its dismissals + its extras, so an over with no `w`/`nb` cell has no
extra runs (validator [B]).

**Ball-count law (validator [E], user-confirmed):** every cell is ONE delivery and
an over is EXACTLY `balls_per_over` cells (default 6) across the pair — extras are
NOT re-bowled, they use up a ball. With the defaults a skin is therefore 24 balls,
or 25 when the pair takes the optional extra ball at the END of the skin
(`extra_ball_last_over`; only the LAST over of a skin may hold one extra cell — the
classic banter case is taking the extra ball and getting out on it). A cell like
`w¹`/`nb²` (extra + superscript runs) is ONE cell: encode the plain `w`/`nb` token
and absorb the superscript runs into the over total. If you read a different number
of cells in a block, you have misread it — re-crop and recount before
best-guessing. If the
card GENUINELY breaks the rule (rare umpire call), ask the user; once they
adjudicate, record it in `meta.ball_count_exceptions`
(`[{innings, skin, balls, reason}]`) so validator [E] holds that skin to the
recorded count (e.g. a 26-ball skin the umpire allowed).

**Reconcile (mandatory):** each batter's 4 over-totals MUST sum to their summary RS;
each bowler's over-totals MUST sum to their summary RC and their dismissals to their
Wkts. If a cell is unclear, **best-guess the individual balls so these totals
reconcile** — the over/RS/RC/skin totals are the authority.

**Delivery order (mandatory):** within each bowler block, the pair's two rows share
one column axis — each column is one delivery, marked in the row of the batter who
faced it. Read the columns left→right across BOTH rows and record the merged
sequence as `over_seq` (one entry per over, 16 per innings, in skin order then
over order): `{skin, bowler, seq: [[batter, ball], ...]}`. Filtering an over's seq
by batter must reproduce that batter's `balls` list exactly. Ball tokens are
canonical: dismissals UPPERCASE single letters, extras lowercase `w`/`nb`.

## Step 5 — innings order
innings 1 = the team whose "Batting Team" block appears first (earlier innings start
time). Record both innings' batting.

## Output — write JSON to the given path
First Read the template `$ENGINE/scripts/templates/game-template.json` for the EXACT
schema, then WRITE a JSON file of the same shape to the OUTPUT path you were given:
```
{ "date","team":"<our team>","opponent",
  "meta":{"time","season","arena":"<arena as printed>","league" (e.g. "Mens E"),
          "umpire","court","venue":null,"source_image":"scorecards/<image filename>",
          "stage": one of league|playoff|semi-final|final, only when the card's league line or the user says so (omit otherwise),
          "rules":{<the team's rules block from team.yaml, every key written out>}},
  "result":{"outcome"(win/loss/tie for us — skins first, then runs),
            "team_total","team_skins_won","team_skins":[4],
            "opponent_total","opponent_skins_won","opponent_skins":[4],
            "player_of_match","player_of_match_team"},
  "summaries":{"<our team>":[8 rows {name,skin,rs,ob,rc,wkts,econ,c}], "<opponent>":[8 rows]},
  "innings":[{"order":1,"batting_team","batting":[{name,skin,rs,
              overs:[{bowler,balls:[...],total}]}],
              "over_seq":[{"skin","bowler","seq":[[batter,ball],...]} x16]},
             {"order":2,...}] }
```
Keep player `name` EXACTLY as printed (including jersey numbers, and "<First> Unknown"
if the surname is illegible). `skin` on a batter = which skin (pair) they batted in.

## Before returning
Self-check: every batter's overs sum to their RS; every bowler's overs sum to RC and
Wkts; each team RS = team total. Fix any mismatch. Then return ONE short status line:
`<date> vs <opponent>: <our total>-<opp total>, reconciles=<yes/no>[, note]`.
