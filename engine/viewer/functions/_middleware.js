// Cloudflare Pages middleware: the team-code gate in front of the whole site.
//
// Environment (Cloudflare Pages → Settings → Variables):
//   GATE        pin (default) | email | none
//   TEAM_PIN    the team code (6+ characters), shared in the team's group chat
//   PIN_SECRET  a long random string that signs the "you're in" cookie
//
// GATE=email: Cloudflare Access (email one-time codes) guards the site in front of
// this function, so it lets everything through; GATE=none: an unlisted link.
// GATE=pin with TEAM_PIN or PIN_SECRET missing FAILS CLOSED (503), never open.
// A correct code sets a signed cookie for 180 days. The signature is keyed on the
// secret AND the code, so changing TEAM_PIN signs every phone out.

const COOKIE = "ac_auth";
const MAX_AGE = 15552000;            // 180 days
const WRONG_PIN_DELAY_MS = 1000;
// Code attempts per address: at most MAX_TRIES per window, counted when a request
// starts (so parallel guesses count too). Kept in this worker's memory: it adds
// friction, not a hard guarantee — see docs/SETUP.md for the stronger email gate.
const MAX_TRIES = 5;
const WINDOW_MS = 15 * 60 * 1000;
const MAX_TRACKED = 5000;
const tries = new Map();     // network -> {n, since}; insertion order = oldest first

// IPv6 users get a whole /64 each, so count per /64 rather than per address.
function networkOf(ip) {
  if (!ip.includes(":")) return ip;
  const [head, tail] = ip.split("::");
  const h = head ? head.split(":") : [];
  const t = tail === undefined ? [] : (tail ? tail.split(":") : []);
  const groups = tail === undefined ? h : [...h, ...Array(Math.max(0, 8 - h.length - t.length)).fill("0"), ...t];
  return groups.slice(0, 4).map((g) => (parseInt(g, 16) || 0).toString(16)).join(":") + "::/64";
}

function allowTry(ip) {
  const t = Date.now();
  const key = networkOf(ip);
  const e = tries.get(key);
  if (!e || t - e.since > WINDOW_MS) {
    tries.delete(key);
    tries.set(key, { n: 1, since: t });
    while (tries.size > MAX_TRACKED) tries.delete(tries.keys().next().value);   // drop the oldest
    return true;
  }
  e.n += 1;
  return e.n <= MAX_TRIES;
}

// Files the phone fetches to install the app (often without cookies). They are the
// engine's generic manifest and icons — no team data — so they skip the gate.
const PUBLIC_EXACT = new Set(["/manifest.webmanifest", "/favicon.ico"]);
const isPublic = (path) => PUBLIC_EXACT.has(path) || /^\/icons\/[\w.-]+\.png$/.test(path);
const enc = new TextEncoder();

async function hmacHex(secret, message) {
  const key = await crypto.subtle.importKey("raw", enc.encode(secret),
    { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  const mac = await crypto.subtle.sign("HMAC", key, enc.encode(message));
  return [...new Uint8Array(mac)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

function sameString(a, b) {           // constant time for equal-length strings
  a = String(a); b = String(b);
  let diff = a.length ^ b.length;
  for (let i = 0; i < Math.max(a.length, b.length); i++) {
    diff |= (a.charCodeAt(i) || 0) ^ (b.charCodeAt(i) || 0);
  }
  return diff === 0;
}

/** Cookie value "<exp>.<hex hmac of 'ok:<exp>'>" (exp = unix seconds). */
async function sign(secret, exp) {
  return `${exp}.${await hmacHex(secret, `ok:${exp}`)}`;
}

/** True when the cookie value is well-formed, unexpired and signed with `secret`. */
async function verify(secret, value) {
  const m = /^(\d{1,12})\.([0-9a-f]{64})$/.exec(String(value || ""));
  if (!m) return false;
  if (Number(m[1]) <= Math.floor(Date.now() / 1000)) return false;
  return sameString(await hmacHex(secret, `ok:${m[1]}`), m[2]);
}

function readCookie(request, name) {
  for (const part of (request.headers.get("Cookie") || "").split(";")) {
    const i = part.indexOf("=");
    if (i > 0 && part.slice(0, i).trim() === name) return part.slice(i + 1).trim();
  }
  return null;
}

// Inline page: the middleware cannot load the site's CSS. Values are the studio tokens.
function pinPage(error) {
  const msg = error ? `<p class="err" role="alert">That code didn't work. Try again.</p>` : "";
  return `<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="robots" content="noindex"><title>Team code</title>
<style>
:root{--bg:#f1f5f9;--card:#ffffff;--ink:#0f172a;--muted:#64748b;--line:#e2e8f0;--accent:#4f46e5;--danger:#dc2626}
@media (prefers-color-scheme:dark){:root{--bg:#0f172a;--card:#1e293b;--ink:#f1f5f9;--muted:#94a3b8;--line:#334155;--accent:#818cf8;--danger:#f87171}}
*{box-sizing:border-box}
body{margin:0;min-height:100dvh;display:grid;place-items:center;padding:16px;background:var(--bg);color:var(--ink);
font:18px/1.45 ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
form{width:min(360px,100%);background:var(--card);border-radius:12px;padding:24px;box-shadow:0 1px 3px rgba(15,23,42,.08)}
h1{font-size:24px;margin:0 0 16px;font-weight:600}
label{display:block;font-size:15px;color:var(--muted);margin-bottom:6px}
input{width:100%;font:inherit;font-size:28px;letter-spacing:.2em;padding:10px 12px;border:1px solid var(--line);
border-radius:8px;background:var(--bg);color:var(--ink)}
input:focus{outline:2px solid var(--accent);outline-offset:1px}
button{margin-top:16px;width:100%;font:inherit;font-weight:600;padding:12px;border:0;border-radius:8px;background:var(--accent);color:#fff}
.err{color:var(--danger);margin:12px 0 0;font-size:16px}
</style></head><body>
<form method="post" action="/__pin">
<h1>Enter the team code</h1>
<label for="pin">Team code</label>
<input id="pin" name="pin" type="password" inputmode="numeric" autocomplete="one-time-code" required autofocus>
${msg}
<button type="submit">Open</button>
</form></body></html>`;
}

function page(status, error) {
  return new Response(pinPage(error), { status, headers: {
    "Content-Type": "text/html; charset=utf-8", "Cache-Control": "no-store",
    "X-Robots-Tag": "noindex" } });
}

async function onRequest(context) {
  const { request, env = {} } = context;
  const gate = (env.GATE || "pin").toLowerCase();
  if (gate === "none" || gate === "email") return context.next();
  if (!env.TEAM_PIN || !env.PIN_SECRET) {
    return new Response("gate not configured", { status: 503,
      headers: { "Content-Type": "text/plain; charset=utf-8", "Cache-Control": "no-store" } });
  }
  const key = `${env.PIN_SECRET}:${env.TEAM_PIN}`;
  const url = new URL(request.url);
  if (request.method === "GET" && isPublic(url.pathname)) return context.next();

  if (url.pathname === "/__pin" && request.method === "POST") {
    const ip = request.headers.get("CF-Connecting-IP") || "unknown";
    if (!allowTry(ip)) {
      return new Response("Too many tries. Wait 15 minutes, then try again.", { status: 429,
        headers: { "Content-Type": "text/plain; charset=utf-8", "Cache-Control": "no-store",
          "Retry-After": String(WINDOW_MS / 1000) } });
    }
    let pin = "";
    try { pin = String((await request.formData()).get("pin") || "").trim(); } catch { /* bad body */ }
    if (pin && sameString(pin, env.TEAM_PIN)) {
      tries.delete(networkOf(ip));
      const value = await sign(key, Math.floor(Date.now() / 1000) + MAX_AGE);
      return new Response(null, { status: 302, headers: {
        Location: "/", "Cache-Control": "no-store",
        "Set-Cookie": `${COOKIE}=${value}; Max-Age=${MAX_AGE}; Path=/; HttpOnly; Secure; SameSite=Lax` } });
    }
    await new Promise((r) => setTimeout(r, WRONG_PIN_DELAY_MS));   // slow down guessing
    return page(401, true);
  }

  if (await verify(key, readCookie(request, COOKIE))) return context.next();
  return page(200, false);
}

export { onRequest, sign, verify };
