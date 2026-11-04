// Minimal service worker: it exists so Android offers "Install app". It does not
// intercept requests at all — the browser fetches everything from the network as
// normal, so the stats are never served stale.
self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (event) => event.waitUntil(self.clients.claim()));
