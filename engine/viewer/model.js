// Pure view-model helpers: season medals, game stages, show switches, season awards.
// No imports and no DOM, so it can be unit-tested; the screens call it.

export const MEDAL_ICON = { gold: "🥇", silver: "🥈", bronze: "🥉" };

export function seasonOptionLabel(season) {
  const icon = MEDAL_ICON[season.medal];
  return icon ? `${icon} ${season.label}` : season.label;
}

export function seasonHeading(season, show) {
  const icon = isShown(show, "medals") ? MEDAL_ICON[season.medal] : undefined;
  let s = season.label;
  if (icon) s += ` · ${icon}`;
  if (typeof season.finish === "string" && season.finish) s += icon ? ` ${season.finish}` : ` · ${season.finish}`;
  return s;
}

export const STAGE_LABEL = { playoff: "Playoff", "semi-final": "Semi-final", final: "Final" };

export function stageLabel(game) {
  return (game && STAGE_LABEL[game.stage]) || null;
}

/** Show switches: a missing switch means shown. */
export function isShown(show, key) {
  if (!show) return true;
  if (show.records && typeof show.records === "object" && key in show.records) return Boolean(show.records[key]);
  if (key in show) return Boolean(show[key]);
  return true;
}

const GROUPED = { best_partnership: "partnerships", longest_win_streak: "streaks",
  longest_loss_streak: "streaks", hattricks: "hattricks" };

export function recordVisible(show, key) {
  return isShown(show, GROUPED[key] || key);
}

export const AWARD_TITLES = { player: "Player of the season", batter: "Batter of the season", bowler: "Bowler of the season" };
export const AWARD_UNITS = { player: "avg contribution", batter: "per 12 balls", bowler: "economy" };
const AWARD_KEYS = ["player", "batter", "bowler"];

export function awardRows(season) {
  if (!(season && season.finished && season.awards)) return [];
  return AWARD_KEYS.filter((key) => season.awards[key])
    .map((key) => ({ key, title: AWARD_TITLES[key], name: season.awards[key].name,
      value: season.awards[key].value, unit: AWARD_UNITS[key] }));
}

/** Finished seasons with at least one winner, newest first. */
export function awardsBySeason(data) {
  return (data.seasons || []).map((season) => ({ season, rows: awardRows(season) }))
    .filter((b) => b.rows.length > 0)
    .reverse()
    .map((b) => ({ season: b.season, heading: seasonHeading(b.season, data.team && data.team.show), rows: b.rows }));
}

export function awardTally(player) {
  if (!(player && player.awards)) return null;
  const parts = AWARD_KEYS.filter((k) => player.awards[k] > 0)
    .map((k) => `${AWARD_TITLES[k]} ×${player.awards[k]}`);
  return parts.length ? parts.join(" · ") : null;
}
