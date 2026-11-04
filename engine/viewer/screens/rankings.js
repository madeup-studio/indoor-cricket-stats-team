// Batting, Bowling and All-round rankings: the engine's lists, in the engine's order.
import { screens, h, fmt, signed, link, playerByName } from "../app.js";
import { helpIcon } from "../help.js";

const LISTS = {
  batting: {
    title: "Batting", list: "batting", metric: "avg12",
    headline: (r) => fmt(r.balls ? r.avg12 : null, 1),
    support: (r) => [[fmt(r.rs), Math.abs(r.rs) === 1 ? "run" : "runs"], [fmt(r.games), r.games === 1 ? "game" : "games"]],
  },
  bowling: {
    title: "Bowling", list: "bowling", metric: "econ",
    headline: (r) => fmt(r.ob ? r.econ : null, 2),
    support: (r) => [[fmt(r.wkts), r.wkts === 1 ? "wicket" : "wickets"], [fmt(r.rc), "conceded"]],
  },
  allround: {
    title: "All-round", list: "allround", metric: "c",
    headline: (r) => signed(r.avgc, 1),
    support: (r) => [[signed(r.c), "total"], [fmt(r.games), r.games === 1 ? "game" : "games"]],
  },
};

function row(cfg, r, rank) {
  const p = playerByName(window.AC.state.data, r.name);
  const body = [
    h("span", { class: "rank num" }, rank ? String(rank) : ""),
    h("span", { class: "who" },
      h("span", { class: "name" }, r.name),
      h("span", { class: "support" }, cfg.support(r).map(([v, unit]) =>
        h("span", null, h("b", { class: "num" }, v), " ", unit)))),
    h("span", { class: "head num" }, cfg.headline(r)),
  ];
  return p ? h("a", { class: "rank-row", href: link("player", p.slug) }, body)
    : h("div", { class: "rank-row" }, body);
}

function rankingScreen(kind) {
  const cfg = LISTS[kind];
  return (ctx) => {
    const title = h("div", { class: "screen-title" }, h("h1", null, cfg.title), helpIcon(cfg.metric));
    const rows = ctx.stats ? ctx.stats[cfg.list] || [] : [];
    if (!rows.length) {
      return h("div", null, title, h("div", { class: "empty" },
        h("h2", null, "No games yet"), h("p", null, "Rankings appear after the first scorecard.")));
    }
    const n = kind === "allround" ? ctx.stats.min_ar_games : ctx.stats.min_rank_games;
    const ranked = rows.filter((r) => r.ranked);
    const rest = rows.filter((r) => !r.ranked);
    const list = h("div", { class: "rank-list" }, ranked.map((r, i) => row(cfg, r, i + 1)));
    if (rest.length) {
      list.append(h("div", { class: "divider" },
        h("span", null, `fewer than ${n} games — not ranked`), helpIcon("ranked")));
      rest.forEach((r) => list.append(row(cfg, r, null)));
    }
    return h("div", null, title, list);
  };
}

screens.batting = rankingScreen("batting");
screens.bowling = rankingScreen("bowling");
screens.allround = rankingScreen("allround");
