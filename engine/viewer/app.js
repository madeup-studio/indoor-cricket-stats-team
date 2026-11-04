// Action Cricket viewer: shell, data loading, scope, routing and the home screen.
// Screens live in screens/*.js and register themselves in `screens` (also exposed
// as window.AC.screens). The viewer never computes stats: it shows data/<team>.json.
import { matchRoute, routeHash } from "./router.js";
import { defaultScope, resolveScope as pickScope } from "./scope.js";
import { closePopover } from "./help.js";
import { seasonOptionLabel, isShown } from "./model.js";

export const screens = {};
export const state = { teams: [], team: null, data: null, scope: null, route: null, chosen: false };
const SCOPE_KEY = "ac.scope";
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const MINUS = "−";

// ---------------------------------------------------------------- DOM helper
const SVG_NS = "http://www.w3.org/2000/svg";
const SVG_TAGS = new Set(["svg", "path", "polyline", "line", "circle", "rect", "g", "text"]);

/** h("div", {class: "card", onclick: fn}, "text", child, [more]) -> Element */
export function h(tag, attrs, ...children) {
  const el = SVG_TAGS.has(tag) ? document.createElementNS(SVG_NS, tag) : document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v === null || v === undefined || v === false) continue;
    if (k === "class" || k === "className") el.setAttribute("class", v);
    else if (k === "html") el.innerHTML = v;   // callers pass safeHtml() output only
    else if (k === "style" && typeof v === "object") {
      for (const [p, val] of Object.entries(v)) {
        if (p.startsWith("--")) el.style.setProperty(p, String(val)); else el.style[p] = val;
      }
    }
    else if (k.startsWith("on") && typeof v === "function") el.addEventListener(k.slice(2), v);
    else el.setAttribute(k, v === true ? "" : String(v));
  }
  const add = (c) => {
    if (c === null || c === undefined || c === false) return;
    if (Array.isArray(c)) return c.forEach(add);
    el.append(c instanceof Node ? c : document.createTextNode(String(c)));
  };
  children.forEach(add);
  return el;
}

// ---------------------------------------------------------------- formatting
export function fmt(n, dp = 0) {
  if (n === null || n === undefined || Number.isNaN(n)) return "–";
  const s = Math.abs(n).toFixed(dp);
  return (n < 0 && Number(s) !== 0 ? MINUS : "") + s;
}
export function signed(n, dp = 0) {
  if (n === null || n === undefined || Number.isNaN(n)) return "–";
  const s = Math.abs(n).toFixed(dp);
  if (Number(s) === 0) return s;
  return (n < 0 ? MINUS : "+") + s;
}
export function fmtDate(iso, withYear = false) {
  const [y, m, d] = String(iso).slice(0, 10).split("-").map(Number);
  if (!y || !m || !d) return String(iso || "");
  return `${d} ${MONTHS[m - 1]}${withYear ? " " + y : ""}`;
}
export const outcomeWord = (o) => ({ win: "Won", loss: "Lost", tie: "Tied" }[o] || o);
export const outcomeLetter = (o) => ({ win: "W", loss: "L", tie: "D" }[o] || "?");
export const score = (a, b) => `${fmt(a)}–${fmt(b)}`;
export function pill(outcome) {
  return h("span", { class: `pill ${outcome}`, "aria-label": outcomeWord(outcome) }, outcomeLetter(outcome));
}
export const label = (text, extra) => h("span", { class: "label" }, text, extra);

/** The four-skin strip: ours over theirs, a won skin filled with the team colour. */
export function skinsStrip(pairs, mini = false) {
  const cells = (pairs || []).map(([a, b], i) => {
    const cls = a > b ? "won" : a < b ? "lost" : "level";
    const title = `Skin ${i + 1}: ${a}–${b}${cls === "level" ? " (level)" : ""}`;
    return mini ? h("span", { class: `skin ${cls}`, title })
      : h("div", { class: `skin ${cls}`, title }, h("b", null, fmt(a)), h("span", null, fmt(b)));
  });
  return h("div", { class: `skins${mini ? " mini" : ""}`, style: { "--n": cells.length || 4 },
    role: "img", "aria-label": (pairs || []).map(([a, b]) => `${a}–${b}`).join(", ") }, cells);
}

// ---------------------------------------------------------------- data helpers
export const seasonOf = (data, key) => (data?.seasons || []).find((s) => s.key === key) || null;
export function scopeLabel(data, scope) {
  return scope === "alltime" ? "All-time" : (seasonOf(data, scope)?.label || "");
}
export function scopeStats(data, scope) {
  if (!data) return null;
  return scope === "alltime" ? data.alltime?.stats || null : seasonOf(data, scope)?.stats || null;
}
export function scopeRecords(data, scope) {
  if (!data) return null;
  return scope === "alltime" ? data.alltime?.records || null : seasonOf(data, scope)?.records || null;
}
export function scopeGames(data, scope) {
  const games = data?.games || [];
  return scope === "alltime" ? games : games.filter((g) => g.season === scope);
}
export const gameByKey = (data, key) => (data?.games || []).find((g) => g.key === key) || null;
export function playerByName(data, name) {
  const p = data?.players?.[name];
  return p ? { name, ...p } : null;
}
export function playerBySlug(data, slug) {
  const hit = Object.entries(data?.players || {}).find(([, p]) => p.slug === slug);
  return hit ? { name: hit[0], ...hit[1] } : null;
}

/** Link to a route, keeping the team in the URL when the site has several teams. */
export function link(name, id) {
  const team = state.teams.length > 1 && state.data ? state.data.team.slug : null;
  return routeHash(name, id, team);
}
export function navigate(name, id) { location.hash = link(name, id); }

// ---------------------------------------------------------------- scope
function readChosen() {
  try { return sessionStorage.getItem(SCOPE_KEY); } catch { return null; }
}
export function setScope(key) {
  state.scope = key;
  state.chosen = true;
  try { sessionStorage.setItem(SCOPE_KEY, key); } catch { /* private mode: fine */ }
}
export { defaultScope };
export const resolveScope = (routeName, data) => pickScope(routeName, data, readChosen());

// ---------------------------------------------------------------- loading
async function getJSON(url) {
  const r = await fetch(url, { cache: "no-cache" });
  if (!r.ok) throw new Error(`${url}: HTTP ${r.status}`);
  return r.json();
}
export async function loadIndex() {
  state.teams = await getJSON("data/index.json");
  return state.teams;
}
export async function loadTeam(slug) {
  state.data = await getJSON(`data/${encodeURIComponent(slug)}.json`);
  state.team = state.data.team;
  return state.data;
}

// ---------------------------------------------------------------- theme
const HEX = /^#[0-9a-f]{3,8}$/i;
function applyTeam(team) {
  const root = document.documentElement.style;
  const c = team.colours || {};
  if (HEX.test(c.brand || "")) root.setProperty("--madeup-color-accent", c.brand);
  else root.removeProperty("--madeup-color-accent");
  if (HEX.test(c.gold || "")) root.setProperty("--ac-gold", c.gold);
  document.title = team.name;
  const badge = $("#badge");
  badge.textContent = team.badge || team.name.slice(0, 4);
  const many = state.teams.length > 1;
  badge.disabled = !many;
  badge.setAttribute("aria-label", many ? `${team.name}: switch team` : team.name);
  if (many) badge.setAttribute("aria-haspopup", "dialog"); else badge.removeAttribute("aria-haspopup");
  $("#team-name").textContent = team.name;
}

// ---------------------------------------------------------------- shell
const $ = (sel) => document.querySelector(sel);

function fillScope(data, scope) {
  const sel = $("#scope");
  const opts = [...(data.seasons || [])].reverse()
    .map((s) => [s.key, isShown(data.team && data.team.show, "medals") ? seasonOptionLabel(s) : s.label]);
  opts.push(["alltime", "All-time"]);
  sel.replaceChildren(...opts.map(([v, t]) => h("option", { value: v, selected: v === scope }, t)));
  sel.hidden = !(data.seasons || []).length;
}

function markNav(name) {
  for (const a of document.querySelectorAll("#nav a")) {
    a.setAttribute("href", link(a.dataset.route));
    if (a.dataset.route === name || (name === "game" && a.dataset.route === "games")
        || (name === "player" && a.dataset.route === "players")) a.setAttribute("aria-current", "page");
    else a.removeAttribute("aria-current");
  }
  const coachOn = state.data?.team?.coach?.enabled !== false;
  const coachLink = document.querySelector('#nav a[data-route="coach"]');
  coachLink.hidden = !coachOn;
  $("#nav").style.setProperty("--ac-nav-n", coachOn ? 6 : 5);
  const rec = $("#records-link");
  rec.setAttribute("href", link("records"));
  if (name === "records") rec.setAttribute("aria-current", "page"); else rec.removeAttribute("aria-current");
}

let lastKey = null;
function show(el, routeKey) {
  const view = $("#view");
  const screen = h("div", { class: "screen" }, el);
  const old = [...view.children];
  const moved = routeKey !== lastKey;
  lastKey = routeKey;
  if (!moved || matchMedia("(prefers-reduced-motion: reduce)").matches) {
    view.replaceChildren(screen);
    return;
  }
  for (const o of old) {
    if (!o.classList.contains("screen")) { o.remove(); continue; }
    o.classList.add("leave");
    setTimeout(() => o.remove(), 120);
  }
  view.append(screen);
  window.scrollTo(0, 0);
}

function message(title, text, action) {
  return h("div", { class: "empty" }, h("h2", null, title), text ? h("p", null, text) : null, action || null);
}

let renderSeq = 0;
export async function render() {
  const seq = ++renderSeq;
  const route = matchRoute(location.hash);
  state.route = route;
  try {
    if (!state.teams.length) await loadIndex();
  } catch (e) {
    console.warn(e);
    return show(message("Couldn't load the stats", "Check your connection, then try again.",
      h("button", { type: "button", onclick: () => location.reload() }, "Try again")), "error");
  }
  if (!state.teams.length) {
    $("#scope").hidden = true;
    return show(screens.setup(), "setup");
  }
  const want = state.teams.find((t) => t.slug === route.team) ? route.team
    : (state.data && state.teams.find((t) => t.slug === state.data.team.slug) ? state.data.team.slug
      : state.teams[0].slug);
  try {
    if (!state.data || state.data.team.slug !== want) await loadTeam(want);
  } catch (e) {
    console.warn(e);
    return show(message("Couldn't load the stats", "Check your connection, then try again.",
      h("button", { type: "button", onclick: () => location.reload() }, "Try again")), "error");
  }
  if (seq !== renderSeq) return;          // a newer navigation is already rendering
  const data = state.data;
  applyTeam(data.team);
  let name = route.name;
  if (name === "coach" && data.team.coach?.enabled === false) name = "home";
  const scope = resolveScope(name, data);
  state.scope = scope;
  fillScope(data, scope);
  markNav(name);
  const ctx = {
    data, scope, params: route.params, navigate, route: name,
    stats: scopeStats(data, scope), games: scopeGames(data, scope),
    records: scopeRecords(data, scope), scopeLabel: scopeLabel(data, scope),
  };
  const screen = screens[name] || screens.home;
  let el;
  try {
    el = screen(ctx);
  } catch (e) {
    console.error(e);
    el = message("Something went wrong on this page", "Go back and try another section.");
  }
  show(el, `${data.team.slug}/${name}/${route.params.id || ""}`);
}

// ---------------------------------------------------------------- screens: setup + home
screens.setup = () => message("Finish setup",
  "No team on this site yet. Open your team repo in Claude Code and run /setup.");

function latestLetterGame(games) {
  for (let i = games.length - 1; i >= 0; i--) if (games[i].letter?.sections?.length) return games[i];
  return null;
}
// Text of a letter section (DOMParser: an inert document, nothing loads or runs).
export const plain = (html) =>
  (new DOMParser().parseFromString(html || "", "text/html").body.textContent || "")
    .replace(/\s+/g, " ").trim();

screens.home = (ctx) => {
  const { data, stats, games, scopeLabel: sl } = ctx;
  if (!stats || !games.length) {
    return message("No games yet", "Stats appear here after the first scorecard is added.");
  }
  const t = stats.team;
  const hero = h("section", { class: "hero" },
    label(sl),
    h("div", { class: "record" },
      h("div", { class: "won" }, h("span", { class: "big" }, fmt(t.won)), h("span", null, "won")),
      h("div", null, h("span", { class: "big" }, fmt(t.lost)), h("span", null, "lost")),
      h("div", null, h("span", { class: "big" }, fmt(t.drawn)), h("span", null, "drawn"))),
    h("div", { class: "avgs" },
      h("span", null, h("b", null, fmt(t.avg_for, 1)), " avg for"),
      h("span", null, h("b", null, fmt(t.avg_against, 1)), " avg against")));

  const last = games[games.length - 1];
  const lastCard = h("a", { class: "card", href: link("game", last.key) },
    label("Last game"),
    h("div", { class: "pad-right" }, `${outcomeWord(last.outcome)} vs ${last.opp}, ${fmtDate(last.date)}`),
    h("div", { class: "score-line" }, h("span", { class: "big" }, score(last.total, last.against)), pill(last.outcome)),
    skinsStrip(last.skin_scores));

  const cards = [lastCard];
  const lg = data.team.coach?.enabled === false ? null : latestLetterGame(games);
  if (lg) {
    const first = lg.letter.sections[0];
    cards.push(h("a", { class: "card", href: link("coach") },
      label("Coach's letter"),
      h("h2", { class: "pad-right" }, first.title),
      h("p", { class: "excerpt pad-right" }, plain(first.html))));
  }
  const rec = data.alltime?.records?.team?.high_total;
  cards.push(h("a", { class: "card", href: link("records") },
    label("Records"),
    rec ? h("div", { class: "pad-right" }, "Highest total ", h("b", { class: "num" }, fmt(rec.value)),
      ` vs ${rec.opp}, ${fmtDate(rec.date, true)}`)
      : h("div", null, "Team and player bests")));
  return h("div", null, hero, cards);
};

// ---------------------------------------------------------------- team picker
// Several teams on one site: the badge opens a sheet listing them (popover rules:
// on <body>, fixed, a bottom sheet on phones, one open at a time, Escape/outside closes).
let picker = null;
function closePicker(returnFocus = false) {
  if (!picker) return;
  picker.cleanup();
  picker.el.remove();
  picker = null;
  $("#badge").setAttribute("aria-expanded", "false");
  if (returnFocus) $("#badge").focus();
}
function openPicker() {
  if (picker) return closePicker();
  closePopover();
  const current = state.data?.team?.slug;
  const items = state.teams.map((t) => {
    const swatch = h("span", { class: "badge mini" }, t.badge || t.name.slice(0, 4));
    if (HEX.test(t.colours?.brand || "")) swatch.style.background = t.colours.brand;
    return h("li", null, h("a", { href: routeHash("home", null, t.slug),
      "aria-current": t.slug === current ? "true" : null, onclick: () => closePicker() }, swatch, t.name));
  });
  const el = h("div", { class: "popover picker", role: "dialog", "aria-label": "Choose a team" },
    h("strong", null, "Teams"), h("ul", { class: "team-list" }, items));
  document.body.append(el);
  const badge = $("#badge");
  const place = () => {
    if (window.innerWidth < 500) { el.classList.add("sheet"); el.style.left = el.style.top = ""; return; }
    el.classList.remove("sheet");
    const r = badge.getBoundingClientRect();
    el.style.left = `${Math.max(8, Math.min(r.left, window.innerWidth - el.offsetWidth - 8))}px`;
    el.style.top = `${r.bottom + 8}px`;
  };
  const onDown = (e) => { if (!el.contains(e.target) && !badge.contains(e.target)) closePicker(); };
  const onKey = (e) => { if (e.key === "Escape") closePicker(true); };
  const onNav = () => closePicker();
  window.addEventListener("resize", place);
  window.addEventListener("hashchange", onNav);
  document.addEventListener("pointerdown", onDown, true);
  document.addEventListener("keydown", onKey);
  picker = { el, cleanup: () => {
    window.removeEventListener("resize", place);
    window.removeEventListener("hashchange", onNav);
    document.removeEventListener("pointerdown", onDown, true);
    document.removeEventListener("keydown", onKey);
  } };
  badge.setAttribute("aria-expanded", "true");
  place();
  el.querySelector("a")?.focus();
}

// ---------------------------------------------------------------- boot
function boot() {
  $("#badge").addEventListener("click", () => { if (state.teams.length > 1) openPicker(); });
  $("#scope").addEventListener("change", (e) => { setScope(e.target.value); render(); });
  window.addEventListener("hashchange", render);
  if ("serviceWorker" in navigator) navigator.serviceWorker.register("sw.js").catch(() => {});
  render();
}
window.AC = { screens, state, h, render, navigate, link };
// Module scripts run before DOMContentLoaded, so every screens/*.js module has
// registered itself by the time boot() renders.
if (document.readyState === "complete") boot();
else document.addEventListener("DOMContentLoaded", boot);
