// Games: the results list and one game's page (skins, both sides, the coach letter).
import { screens, h, fmt, signed, fmtDate, score, pill, outcomeWord, skinsStrip, link,
  gameByKey } from "../app.js";
import { renderLetter, latestLetterGame } from "./coach.js";
import { helpIcon } from "../help.js";
import { isShown, stageLabel } from "../model.js";

const stageTag = (data, g) =>
  isShown(data.team && data.team.show, "stage_tags") && stageLabel(g) ? h("span", { class: "tag" }, stageLabel(g)) : null;

screens.games = (ctx) => {
  const title = h("div", { class: "screen-title" }, h("h1", null, "Games"));
  if (!ctx.games.length) {
    return h("div", null, title, h("div", { class: "empty" }, h("h2", null, "No games yet"),
      h("p", null, "Games appear here after each scorecard is added.")));
  }
  const rows = [...ctx.games].reverse().map((g) =>
    h("a", { class: "game-row", href: link("game", g.key) },
      h("span", { class: "when num" }, fmtDate(g.date)),
      h("span", { class: "what" },
        h("span", { class: "opp" }, g.opp), stageTag(ctx.data, g),
        h("span", { class: "sk num" }, `skins ${g.skins}–${g.oskins}`),
        skinsStrip(g.skin_scores, true)),
      h("span", { class: "res" }, h("b", { class: "num" }, score(g.total, g.against)), pill(g.outcome))));
  return h("div", null, title, h("div", { class: "rank-list" }, rows));
};

function skinCards(pairs) {
  return h("div", { class: "skin-cards", style: { "--n": pairs.length || 4 } }, pairs.map(([a, b], i) => {
    const cls = a > b ? "won" : a < b ? "lost" : "level";
    return h("div", { class: `skin-card ${cls}` },
      h("span", { class: "sk-label" }, `Skin ${i + 1}`),
      h("b", { class: "num" }, fmt(a)),
      h("span", { class: "num them" }, fmt(b)),
      cls === "level" ? h("span", { class: "shared" }, "shared") : null);
  }));
}

function summaryTable(title, rows, ours, players) {
  const head = h("tr", null, h("th", { scope: "col" }, title),
    ...["RS", "Wkts", "RC", "C"].map((c) => h("th", { scope: "col", class: "n" }, c)));
  const body = rows.map((r) => {
    const p = ours && players[r.name];
    const name = p ? h("a", { href: link("player", p.slug) }, r.name) : r.name;
    return h("tr", null, h("td", { class: "nm" }, name),
      h("td", { class: "n" }, fmt(r.rs)), h("td", { class: "n" }, fmt(r.wkts)),
      h("td", { class: "n" }, fmt(r.rc)), h("td", { class: "n c" }, signed(r.c)));
  });
  return h("table", { class: "sum" }, h("thead", null, head), h("tbody", null, body));
}

screens.game = (ctx) => {
  const { data } = ctx;
  const g = gameByKey(data, ctx.params.id);
  if (!g) {
    return h("div", { class: "empty" }, h("h2", null, "Game not found"),
      h("p", null, "It may have been renamed."), h("a", { href: link("games") }, "All games"));
  }
  const header = h("header", { class: "game-head" },
    h("span", { class: "label" }, fmtDate(g.date, true)), stageTag(data, g),
    h("h1", null, `vs ${g.opp}`),
    h("div", { class: "score-line" }, h("span", { class: "big" }, score(g.total, g.against)), pill(g.outcome),
      h("span", { class: "muted small" }, `${outcomeWord(g.outcome)}, skins ${g.skins}–${g.oskins}`)));

  const [topName, topC] = g.top_c || [];
  const pom = h("div", { class: "card pom" },
    h("span", { class: "label" }, "Player of the match"),
    h("h2", null, g.pom || "–", g.pom && !g.pom_ours ? h("span", { class: "muted small" }, ` (${g.opp})`) : null),
    topName ? h("p", { class: "muted small" }, "Our best on the night: ",
      h("b", null, topName), ` ${signed(topC)}`, helpIcon("c")) : null);

  const tables = h("div", { class: "card tables" },
    summaryTable(data.team.name, g.summaries?.ours || [], true, data.players || {}),
    summaryTable(g.opp, g.summaries?.theirs || [], false, {}));

  const coachOn = data.team.coach?.enabled !== false;
  let letter = null;
  if (coachOn) {
    const newest = latestLetterGame(data.games || []);
    const newer = newest && newest.key !== g.key && newest.date >= g.date ? newest : null;
    letter = h("section", { class: "game-letter" },
      h("div", { class: "section-head" }, h("h2", null, "Coach's letter"),
        newer ? h("a", { href: link("coach") }, "Latest letter") : null),
      g.letter ? renderLetter(g.letter, data.players)
        : h("div", { class: "empty" }, h("p", null, "No coach letter for this game")));
  }
  return h("div", null, header, h("div", { class: "skins-block" }, skinCards(g.skin_scores || []), helpIcon("skin")),
    pom, tables, letter);
};
