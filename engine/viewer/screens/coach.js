// The coach's letter: the Coach tab (newest letter in the scope) and the shared
// letter component the game page uses.
import { screens, h, link, fmtDate } from "../app.js";
import { safeHtml } from "../sanitize.js";

/** One letter as a paper sheet: its sections, then a note to each player who played.
 *  `players` is the team's player map (name -> {slug}) so notes link to player pages. */
export function renderLetter(letter, players) {
  const sections = (letter.sections || []).map((s) =>
    // sections[].html is written by the ai-coach skill from the team's data and notes;
    // it is passed through the formatting-only allowlist before it reaches the page.
    h("section", { class: "letter-sec" }, h("h3", null, s.title), h("div", { html: safeHtml(s.html) })));
  const notes = (letter.players || []).map((p) => {
    const who = players && players[p.name];
    const name = who ? h("a", { href: link("player", who.slug) }, p.name) : h("span", null, p.name);
    return h("li", null, h("strong", null, name), h("span", { html: safeHtml(p.note) }));
  });
  return h("article", { class: "letter" },
    sections,
    notes.length ? h("section", { class: "letter-sec" },
      h("h3", null, "A word to each player who played"), h("ul", { class: "notes" }, notes)) : null,
    h("p", { class: "letter-disc" },
      "Written by the team's AI coach from the verified scorecards. The numbers are checked; the opinions are the coach's own."));
}

/** Newest game (in `games`, chronological) that has a letter. */
export function latestLetterGame(games) {
  for (let i = games.length - 1; i >= 0; i--) if (games[i].letter?.sections?.length) return games[i];
  return null;
}

screens.coach = (ctx) => {
  const g = latestLetterGame(ctx.games);
  if (!g) {
    return h("div", null,
      h("div", { class: "screen-title" }, h("h1", null, "Coach")),
      h("div", { class: "empty" }, h("h2", null, "No letter yet"),
        h("p", null, "The coach writes after every game.")));
  }
  return h("div", null,
    h("div", { class: "screen-title letter-head" },
      h("div", null, h("span", { class: "label" }, `After ${fmtDate(g.date, true)}`),
        h("h1", null, h("a", { class: "plain", href: link("game", g.key) }, `vs ${g.opp}`)))),
    renderLetter(g.letter, ctx.data.players));
};

