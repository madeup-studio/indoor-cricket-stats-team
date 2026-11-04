// Players: the squad grid and one player's page (season line, career line, game by game).
import { screens, h, fmt, signed, fmtDate, link, playerBySlug, seasonOf } from "../app.js";
import { sparkline } from "../sparkline.js";
import { helpIcon } from "../help.js";
import { safeHtml } from "../sanitize.js";
import { isShown, awardTally } from "../model.js";

export function initials(name) {
  const w = String(name).trim().split(/\s+/).filter(Boolean);
  return ((w[0] || "?")[0] + (w.length > 1 ? w[w.length - 1][0] : "")).toUpperCase();
}

function avatar(data, name, size = "") {
  const p = data.players?.[name];
  return p && p.photo
    ? h("img", { class: `avatar ${size}`, src: p.photo, alt: "", loading: "lazy" })
    : h("span", { class: `avatar ${size}`, "aria-hidden": "true" }, initials(name));
}

screens.players = (ctx) => {
  const { data, stats } = ctx;
  const title = h("div", { class: "screen-title" }, h("h1", null, "Players"));
  const rows = stats ? stats.allround || [] : [];
  if (!rows.length) {
    return h("div", null, title, h("div", { class: "empty" }, h("h2", null, "No players yet"),
      h("p", null, "Players appear after the first scorecard.")));
  }
  const cards = rows.map((a) => {
    const p = data.players?.[a.name];
    const body = [avatar(data, a.name), h("span", { class: "pc-name" }, a.name),
      h("span", { class: "pc-c num" }, signed(a.avgc, 1)),
      h("span", { class: "pc-sub" }, `avg contribution, ${a.games} ${a.games === 1 ? "game" : "games"}`)];
    return p ? h("a", { class: "card player-card", href: link("player", p.slug) }, body)
      : h("div", { class: "card player-card" }, body);
  });
  return h("div", null, title, h("div", { class: "player-grid" }, cards));
};

// ---------------------------------------------------------------- player page

const tile = (value, labelText, extra) =>
  h("div", { class: "tile" }, h("b", { class: "num" }, value), h("span", null, labelText, extra || null));

const DISM_ORDER = ["caught", "bowled", "run out", "stumped", "lbw", "hit wicket", "mankad"];
function breakdown(counts) {
  const items = DISM_ORDER.map((k) => [k, (counts || {})[k] || 0]).filter(([, n]) => n > 0);
  const total = items.reduce((s, [, n]) => s + n, 0);
  if (!total) return null;
  return h("div", { class: "breakdown" },
    h("div", { class: "bar", role: "img", "aria-label": items.map(([k, n]) => `${k} ${n}`).join(", ") },
      items.map(([k, n]) => h("span", { class: `seg d-${k.replace(/\s+/g, "-")}`,
        style: { flexGrow: String(n) } }))),
    h("ul", { class: "legend" }, items.map(([k, n]) =>
      h("li", null, h("i", { class: `d-${k.replace(/\s+/g, "-")}` }), `${k} `, h("b", { class: "num" }, n)))));
}

function chips(counts) {
  const items = DISM_ORDER.map((k) => [k, (counts || {})[k] || 0]).filter(([, n]) => n > 0);
  return items.length ? h("ul", { class: "chips" }, items.map(([k, n]) => h("li", null, `${k} `, h("b", null, n))))
    : null;
}

function block(title, stats, name) {
  const bat = (stats?.batting || []).find((r) => r.name === name);
  const bowl = (stats?.bowling || []).find((r) => r.name === name);
  const ar = (stats?.allround || []).find((r) => r.name === name);
  if (!ar) {
    return h("section", { class: "pblock" }, h("h2", null, title),
      h("p", { class: "muted" }, `Didn't play in ${title}.`));
  }
  const faced = bat && bat.balls > 0;
  const bowled = bowl && bowl.ob > 0;
  const best = bowl && bowl.best ? `${bowl.best[1]}/${fmt(bowl.best[2])}` : "–";
  return h("section", { class: "pblock" },
    h("h2", null, title),
    h("div", { class: "contrib" },
      h("span", { class: "big" }, signed(ar.avgc, 1)),
      h("span", { class: "muted" }, "avg contribution ", helpIcon("c")),
      h("span", { class: "muted small" }, `${signed(ar.c)} total in ${ar.games} ${ar.games === 1 ? "game" : "games"}`)),
    h("h3", { class: "label" }, "Batting"),
    h("div", { class: "tiles" },
      tile(fmt(bat?.rs ?? 0), Math.abs(bat?.rs ?? 0) === 1 ? "run" : "runs"),
      tile(faced ? fmt(bat.avg12, 1) : "–", "per 12 balls"),
      tile(faced ? fmt(bat.sr, 0) : "–", "strike rate"),
      tile(fmt(bat?.balls ?? 0), "balls"),
      tile(fmt(bat?.outs ?? 0), (bat?.outs ?? 0) === 1 ? "out" : "outs"),
      tile(fmt((bat?.s5 ?? 0) + (bat?.s7 ?? 0)), "big hits")),
    faced ? breakdown(bat.outs_by_type) : null,
    h("h3", { class: "label" }, "Bowling"),
    h("div", { class: "tiles" },
      tile(fmt(bowl?.wkts ?? 0), (bowl?.wkts ?? 0) === 1 ? "wicket" : "wickets"),
      tile(bowled ? fmt(bowl.econ, 2) : "–", "economy"),
      tile(fmt(bowl?.rc ?? 0), "conceded"),
      tile(best, "best")),
    bowled ? chips(bowl.wkt_types) : null);
}

function latestNote(data, name) {
  const games = data.games || [];
  for (let i = games.length - 1; i >= 0; i--) {
    const n = (games[i].letter?.players || []).find((p) => p.name === name);
    if (n) return { note: n.note, game: games[i] };
  }
  return null;
}

function gameLog(log, name) {
  if (!log || !log.length) return null;
  const rows = [...log].reverse().map((e) => h("tr", null,
    h("td", { class: "dt num" }, fmtDate(e.date)), h("td", { class: "nm" }, e.opp),
    h("td", { class: "n" }, fmt(e.rs)), h("td", { class: "n" }, fmt(e.wkts)),
    h("td", { class: "n" }, fmt(e.rc)), h("td", { class: "n c" }, signed(e.c))));
  return h("section", { class: "pblock" },
    h("h2", null, "Game by game"),
    log.length > 1 ? h("div", { class: "spark-row" },
      sparkline(log.map((e) => e.c), { w: 280, h: 44, label: `${name}'s contribution, game by game` }),
      h("span", { class: "muted small" }, "contribution")) : null,
    h("table", { class: "sum log" },
      h("thead", null, h("tr", null, h("th", { scope: "col" }, "Date"), h("th", { scope: "col" }, "Opponent"),
        ...["RS", "Wkts", "RC", "C"].map((c) => h("th", { scope: "col", class: "n" }, c)))),
      h("tbody", null, rows)));
}

screens.player = (ctx) => {
  const { data, scope } = ctx;
  const p = playerBySlug(data, ctx.params.id);
  if (!p) {
    return h("div", { class: "empty" }, h("h2", null, "Player not found"),
      h("a", { href: link("players") }, "All players"));
  }
  const name = p.name;
  const seasons = data.seasons || [];
  const seasonKey = scope !== "alltime" ? scope : (seasons.length ? seasons[seasons.length - 1].key : null);
  const season = seasonKey ? seasonOf(data, seasonKey) : null;
  const note = latestNote(data, name);
  const tally = isShown(data.team && data.team.show, "awards") ? awardTally(p) : null;
  const scopeLog = (ctx.stats?.gamelog || {})[name];

  return h("div", null,
    h("header", { class: "player-head" }, avatar(data, name, "lg"),
      h("div", { class: "player-title" }, h("h1", null, name),
        tally ? h("p", { class: "muted small tally" }, tally) : null)),
    note ? h("aside", { class: "coach-note" },
      h("span", { class: "label" }, "From the coach"),
      h("p", { html: safeHtml(note.note) }),
      h("a", { class: "small", href: link("game", note.game.key) },
        `After the game vs ${note.game.opp}, ${fmtDate(note.game.date)}`)) : null,
    season ? block(season.label, season.stats, name) : null,
    block("All-time", data.alltime?.stats, name),
    gameLog(scopeLog, name));
};
