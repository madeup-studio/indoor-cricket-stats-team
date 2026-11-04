// Hash routes: #/[t/<team>/]<name>[/<param>]   — pure, no DOM access.
export const ROUTES = ["home", "coach", "batting", "bowling", "allround", "games", "game",
  "players", "player", "records"];

const HOME = (team) => ({ team, name: "home", params: {} });

export function matchRoute(hash) {
  const parts = String(hash || "").replace(/^#\/?/, "").split("/").filter(Boolean)
    .map((p) => { try { return decodeURIComponent(p); } catch { return p; } });
  let team = null;
  if (parts[0] === "t" && parts.length >= 2) {
    team = parts[1];
    parts.splice(0, 2);
  }
  const [name, param, ...rest] = parts;
  if (!name || !ROUTES.includes(name) || rest.length) return HOME(team);
  return { team, name, params: param === undefined ? {} : { id: param } };
}

// The hash for a route; `team` is included only when given (multi-team sites).
export function routeHash(name, id, team) {
  const t = team ? `t/${encodeURIComponent(team)}/` : "";
  return `#/${t}${name}${id === undefined || id === null ? "" : "/" + encodeURIComponent(id)}`;
}
