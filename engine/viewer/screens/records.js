// Records: team and individual bests for the scope (opens on the latest season like
// every screen; the switcher offers all-time). Each card opens the game the record was set in.
import { screens, h, fmt, signed, fmtDate, link, gameByKey, seasonOf } from "../app.js";
import { helpIcon } from "../help.js";
import { isShown, recordVisible, awardRows, awardsBySeason } from "../model.js";

const TEAM = [
  ["high_total", "Highest total", (r) => fmt(r.value)],
  ["low_total", "Lowest total", (r) => fmt(r.value)],
  ["biggest_win", "Biggest win", (r) => `by ${fmt(r.value)}`],
  ["heaviest_loss", "Heaviest loss", (r) => fmt(r.value)],
  ["best_skin", "Best skin in the field", (r) => fmt(r.value), "skin"],
  ["most_wkts_game", "Most wickets in a game", (r) => fmt(r.value)],
  ["fewest_extras_game", "Fewest extras bowled", (r) => fmt(r.value)],
];
const STREAKS = [["longest_win_streak", "Longest winning run"], ["longest_loss_streak", "Longest losing run"]];
const PLAYERS = [
  ["best_contribution", "Best contribution", (r) => signed(r.value), "c"],
  ["most_runs_game", "Most runs in a game", (r) => fmt(r.value), "rs"],
  ["most_wkts_game", "Most wickets in a game", (r) => fmt(r.value)],
  ["best_econ", "Best economy in a game", (r) => fmt(r.value, 2), "econ"],
  ["best_partnership", "Best partnership", (r) => fmt(r.value)],
  ["most_runouts_created", "Most run outs off one bowler", (r) => fmt(r.value)],
];

function card(title, value, who, rec, help) {
  const where = rec.key ? `vs ${rec.opp}, ${fmtDate(rec.date, true)}` : null;
  const body = [
    h("span", { class: "label" }, title),
    h("span", { class: "rec-val big" }, value),
    who ? h("span", { class: "rec-who" }, who) : null,
    where ? h("span", { class: "rec-where" }, where) : null,
  ];
  return h("div", { class: "rec-wrap" },
    rec.key ? h("a", { class: "card rec", href: link("game", rec.key) }, body) : h("div", { class: "card rec" }, body),
    help ? helpIcon(help) : null);
}

const AWARD_FORMAT = { player: (v) => signed(v, 1), batter: (v) => fmt(v, 1), bowler: (v) => fmt(v, 2) };

// One season's award cards; the ? sits on the first card only.
function awardGrid(rows) {
  return h("div", { class: "rec-grid" }, rows.map((row, i) => {
    const c = card(row.title, AWARD_FORMAT[row.key](row.value), row.name, {}, i === 0 ? "awards" : null);
    c.querySelector(".card.rec").append(h("span", { class: "rec-where" }, row.unit));
    return c;
  }));
}

function awardsBlock(data, scope) {
  if (scope !== "alltime") {
    const rows = awardRows(seasonOf(data, scope));
    return rows.length ? [h("h2", { class: "group" }, "Awards"), awardGrid(rows)] : null;
  }
  const seasons = awardsBySeason(data);
  return seasons.length ? [h("h2", { class: "group" }, "Awards"),
    seasons.map((s) => [h("h3", { class: "label" }, s.heading), awardGrid(s.rows)])] : null;
}

function streakCard(data, title, s) {
  if (!s || !s.value) return null;
  const from = gameByKey(data, s.from), to = gameByKey(data, s.to);
  const rec = { key: s.to, opp: to?.opp, date: to?.date };
  const span = from && to && s.value > 1 ? `${fmtDate(from.date)} to ${fmtDate(to.date, true)}` : null;
  const c = card(title, `${s.value}`, `${s.value === 1 ? "game" : "games in a row"}`, rec);
  if (span) c.querySelector(".rec-where").textContent = span;
  return c;
}

screens.records = (ctx) => {
  const { data, records, scopeLabel } = ctx;
  const show = data.team && data.team.show;
  const title = h("div", { class: "screen-title" }, h("h1", null, "Records"));
  if (!records) {
    return h("div", null, title, h("div", { class: "empty" }, h("h2", null, "No records yet"),
      h("p", null, "Records appear after the first scorecard.")));
  }
  const t = records.team || {}, ind = records.individual || {};
  const teamCards = TEAM.filter(([k]) => t[k] && recordVisible(show, k)).map(([k, name, val, help]) => card(name, val(t[k]), null, t[k], help));
  STREAKS.filter(([k]) => recordVisible(show, k)).forEach(([k, name]) => { const c = streakCard(data, name, t[k]); if (c) teamCards.push(c); });

  const playerCards = PLAYERS.filter(([k]) => ind[k] && recordVisible(show, k)).map(([k, name, val, help]) => {
    const r = ind[k];
    return card(name, val(r), r.names ? r.names.join(" & ") : r.name, r, help);
  });
  for (const ht of recordVisible(show, "hattricks") ? ind.hattricks || [] : []) {
    playerCards.push(card(ht.value > 3 ? `${ht.value} wickets in ${ht.value} balls` : "Hat-trick",
      ht.name, `Victims: ${(ht.victims || []).join(", ")}`, ht));
  }
  return h("div", null, title,
    h("p", { class: "muted small scope-note" }, scopeLabel),
    isShown(show, "awards") ? awardsBlock(data, ctx.scope) : null,
    h("h2", { class: "group" }, "Team"), h("div", { class: "rec-grid" }, teamCards),
    playerCards.length ? [h("h2", { class: "group" }, "Players"), h("div", { class: "rec-grid" }, playerCards)] : null);
};
