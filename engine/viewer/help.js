// `?` help icons and the stat glossary. Popover rules (studio standard): portal to
// <body>, position: fixed against the viewport, flip above when there's no room
// below, clamp to the screen edges, a bottom sheet under 500px, re-measure on
// resize/scroll, one open at a time, close on click-outside / Escape (focus returns).
// No imports from app.js, so the glossary can be unit-tested without a DOM.

const wv = (rules) => Math.abs((rules && rules.wicket_runs) ?? -5);
const xv = (rules) => (rules && rules.extra_runs) ?? 2;

export const GLOSSARY = {
  rs: { title: "Runs scored (RS)",
    text: (r) => `Runs off the bat, minus ${wv(r)} every time you're out. It can go below zero.` },
  rc: { title: "Runs conceded (RC)",
    text: (r) => `Runs your overs gave away, including wides and no-balls (${xv(r)} each). Every wicket you take knocks ${wv(r)} off, so it can go below zero.` },
  wkts: { title: "Wickets",
    text: () => "Batters out off your bowling: caught, bowled, stumped, lbw, hit wicket, run out or mankad." },
  econ: { title: "Economy",
    text: () => "Runs conceded per over you bowled. Lower is better; below zero means your wickets outweighed the runs." },
  c: { title: "Contribution (C)",
    text: () => "Runs scored minus runs conceded. Above zero, you added more to the team than you gave away." },
  avg12: { title: "Average per 12 balls",
    text: () => "Runs scored for every 12 balls faced (two overs). The batting ranking, so a short innings and a long one compare fairly." },
  sr: { title: "Strike rate",
    text: () => "Runs scored per 100 balls faced." },
  skin: { title: "Skin",
    text: () => "A pair's spell at the crease: four overs, one from each bowler pair. The side that scores more in a skin wins it." },
  big_hits: { title: "Big hits",
    text: () => "Shots worth 5 or 7 runs." },
  awards: { title: "Season awards",
    text: (r, n) => `Worked out from the season's rankings once the season is over: best average per 12 balls, best economy and best average contribution. A player needs at least ${(n && n.season) ?? 3} games to win one.` },
  ranked: { title: "Ranked",
    text: (r, n) => `Ranked players have played at least ${(n && n.season) ?? 3} games in a season, or ${(n && n.alltime) ?? 10} all-time. Players with fewer are listed below the line, unranked.` },
};

export function glossaryText(key, rules, thresholds) {
  const g = GLOSSARY[key];
  return g ? g.text(rules || {}, thresholds) : "";
}

// ---------------------------------------------------------------- the popover
let current = null;   // {btn, pop, cleanup}

function el(tag, cls, text) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text) e.textContent = text;
  return e;
}

function teamRules() {
  return (globalThis.AC && globalThis.AC.state && globalThis.AC.state.data
    && globalThis.AC.state.data.team.rules) || {};
}
function thresholds() {
  const d = globalThis.AC && globalThis.AC.state && globalThis.AC.state.data;
  const s = d && d.seasons && d.seasons.length ? d.seasons[d.seasons.length - 1].stats : null;
  const a = d && d.alltime && d.alltime.stats;
  return { season: s ? s.min_rank_games : 3, alltime: a ? a.min_rank_games : 10 };
}

export function closePopover(returnFocus = false) {
  if (!current) return;
  const { btn, pop, cleanup } = current;
  current = null;
  cleanup();
  pop.remove();
  btn.setAttribute("aria-expanded", "false");
  if (returnFocus) btn.focus();
}

function place(btn, pop) {
  const vw = window.innerWidth, vh = window.innerHeight;
  if (vw < 500) {                       // phone: bottom sheet
    pop.classList.add("sheet");
    pop.style.left = pop.style.top = "";
    return;
  }
  pop.classList.remove("sheet");
  const r = btn.getBoundingClientRect();
  const pw = pop.offsetWidth, ph = pop.offsetHeight;
  let top = r.bottom + 8;
  if (top + ph > vh - 8 && r.top - 8 - ph >= 8 && r.top > vh - r.bottom) top = r.top - 8 - ph;
  const left = Math.max(8, Math.min(r.left + r.width / 2 - pw / 2, vw - pw - 8));
  pop.style.left = `${left}px`;
  pop.style.top = `${top}px`;
}

function openPopover(btn, key) {
  closePopover();
  const g = GLOSSARY[key];
  const id = `help-${key}-${Math.random().toString(36).slice(2, 7)}`;
  const pop = el("div", "popover");
  pop.id = id;
  pop.setAttribute("role", "dialog");
  pop.setAttribute("aria-label", g.title);
  pop.append(el("strong", null, g.title), el("p", null, glossaryText(key, teamRules(), thresholds())));
  document.body.append(pop);
  btn.setAttribute("aria-expanded", "true");
  btn.setAttribute("aria-controls", id);
  const reposition = () => place(btn, pop);
  const onDown = (e) => { if (!pop.contains(e.target) && !btn.contains(e.target)) closePopover(); };
  const onKey = (e) => { if (e.key === "Escape") closePopover(true); };
  const onNav = () => closePopover();
  window.addEventListener("resize", reposition);
  window.addEventListener("scroll", reposition, true);
  window.addEventListener("hashchange", onNav);
  document.addEventListener("pointerdown", onDown, true);
  document.addEventListener("keydown", onKey);
  current = { btn, pop, cleanup: () => {
    window.removeEventListener("resize", reposition);
    window.removeEventListener("scroll", reposition, true);
    window.removeEventListener("hashchange", onNav);
    document.removeEventListener("pointerdown", onDown, true);
    document.removeEventListener("keydown", onKey);
  } };
  reposition();
}

/** A `?` button that explains a stat. */
export function helpIcon(key) {
  const g = GLOSSARY[key];
  const btn = el("button", "help", "?");
  btn.type = "button";
  btn.setAttribute("aria-label", `What is ${g ? g.title : key}?`);
  btn.setAttribute("aria-expanded", "false");
  btn.addEventListener("click", (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (current && current.btn === btn) closePopover();
    else openPopover(btn, key);
  });
  return btn;
}
