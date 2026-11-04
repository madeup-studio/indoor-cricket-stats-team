// Which scope (a season key or "alltime") a screen shows — pure, no DOM.
// Every screen defaults to the latest season. A scope the viewer picked in the switcher
// (kept in sessionStorage for the visit) wins on every screen while it exists for the
// team being shown.

export function defaultScope(routeName, data) {
  const seasons = (data && data.seasons) || [];
  return seasons.length ? seasons[seasons.length - 1].key : "alltime";
}

export function validScope(data, key) {
  return key === "alltime" || ((data && data.seasons) || []).some((s) => s.key === key);
}

export function resolveScope(routeName, data, chosen) {
  return chosen && validScope(data, chosen) ? chosen : defaultScope(routeName, data);
}
