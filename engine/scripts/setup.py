#!/usr/bin/env python3
"""Cloudflare Pages provisioning for the team's app (used by the /setup skill).

  python engine/scripts/setup.py --check                 token works? which account?
  python engine/scripts/setup.py --create NAME           create the Pages project (if new),
                                                          write NAME into the deploy workflow
  python engine/scripts/setup.py --gate pin [--pin CODE] how viewers get in: pin | email | none
  python engine/scripts/setup.py --deploy [NAME]         first deploy of site/ (needs Node)
  python engine/scripts/setup.py --status [NAME]         the project's URL and settings
  python engine/scripts/setup.py --forget                delete the saved token (.cf-token)

The Cloudflare API token comes from the CLOUDFLARE_API_TOKEN env var or the file
.cf-token at the repo root (gitignored; the wizard writes it there because shell
variables don't survive between commands, and deletes it at the end). The token is
never printed. NAME defaults to the project named in .github/workflows/deploy.yml.
Changed gate settings apply from the next deploy.
"""
import argparse, json, os, re, secrets, shutil, subprocess, sys, urllib.error, urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
_had_optional = "ACS_TEAM_OPTIONAL" in os.environ
os.environ.setdefault("ACS_TEAM_OPTIONAL", "1")     # setup runs before any team exists
import paths
if not _had_optional:
    del os.environ["ACS_TEAM_OPTIONAL"]

API = "https://api.cloudflare.com/client/v4"
TOKEN_FILE = ".cf-token"
WORKFLOW = os.path.join(".github", "workflows", "deploy.yml")
PLACEHOLDER = "__PROJECT_NAME__"
SECRET_VARS = {"TEAM_PIN", "PIN_SECRET"}
MIN_PIN = 6


class SetupError(Exception):
    pass


# ---------------------------------------------------------------- token
def get_token(repo_root=None):
    if os.environ.get("CLOUDFLARE_API_TOKEN"):
        return os.environ["CLOUDFLARE_API_TOKEN"].strip()
    p = os.path.join(repo_root or paths.ROOT, TOKEN_FILE)
    if os.path.isfile(p):
        with open(p, encoding="utf-8") as fh:
            tok = fh.read().strip()
        if tok:
            return tok
    raise SetupError("no Cloudflare API token: paste one and I'll save it to .cf-token")


def forget_token(repo_root=None):
    p = os.path.join(repo_root or paths.ROOT, TOKEN_FILE)
    if os.path.exists(p):
        os.remove(p)


# ---------------------------------------------------------------- HTTP
UNREACHABLE = ("can't reach api.cloudflare.com from here. In a Claude Code cloud session, "
               "add api.cloudflare.com to the environment's allowed domains (network access: "
               "Custom), or run /setup from Claude Code on a computer.")


def _urllib_http(method, url, headers, data):
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read() or b"{}")
        except ValueError:          # not Cloudflare answering (e.g. a network proxy)
            raise SetupError(UNREACHABLE) from e
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise SetupError(UNREACHABLE) from e


def _errors(payload):
    errs = (payload or {}).get("errors") or []
    return "; ".join(f"{e.get('message', e)} ({e.get('code', '?')})" for e in errs) or "no details"


def api(method, path, body=None, *, http=None, ok_404=False):
    """Call the Cloudflare API; returns the parsed JSON. Raises SetupError on failure."""
    http = http or _urllib_http
    headers = {"Authorization": f"Bearer {get_token()}", "Content-Type": "application/json"}
    data = json.dumps(body).encode("utf-8") if body is not None else None
    status, payload = http(method, API + path, headers, data)
    if status == 404 and ok_404:
        return None
    if status >= 300 or not (payload or {}).get("success", False):
        raise SetupError(f"Cloudflare said no ({status}): {_errors(payload)}")
    return payload


def verify_token(http=None):
    r = api("GET", "/user/tokens/verify", http=http)["result"] or {}
    if r.get("status") != "active":
        raise SetupError("token invalid (not active) — create a new one")
    return r


def account_id(http=None):
    accts = api("GET", "/accounts", http=http)["result"] or []
    if not accts:
        raise SetupError("this token can't see any Cloudflare account — check its permissions")
    return accts[0]["id"]


def project_exists(acct, name, http=None):
    return api("GET", f"/accounts/{acct}/pages/projects/{name}", http=http, ok_404=True) is not None


def get_project(acct, name, http=None):
    r = api("GET", f"/accounts/{acct}/pages/projects/{name}", http=http, ok_404=True)
    return r["result"] if r else None


def create_project(acct, name, http=None):
    r = api("POST", f"/accounts/{acct}/pages/projects",
            {"name": name, "production_branch": "main"}, http=http)["result"] or {}
    return f"https://{r.get('subdomain') or name + '.pages.dev'}"


def set_env(acct, name, env, http=None):
    vars_ = {k: {"type": "secret_text" if k in SECRET_VARS else "plain_text", "value": str(v)}
             for k, v in env.items()}
    api("PATCH", f"/accounts/{acct}/pages/projects/{name}",
        {"deployment_configs": {"production": {"env_vars": vars_}}}, http=http)


# ---------------------------------------------------------------- local helpers
def random_pin():
    """An 8-digit team code (easy to type once; 100 million possibilities)."""
    return f"{secrets.randbelow(10 ** 8):08d}"


def random_secret():
    return secrets.token_hex(16)


def gate_env(gate, pin=None):
    if gate not in ("pin", "email", "none"):
        raise SetupError("gate must be pin, email or none")
    if gate != "pin":
        return {"GATE": gate}
    pin = (pin or random_pin()).strip()
    if len(pin) < MIN_PIN:
        raise SetupError(f"team codes need at least {MIN_PIN} characters")
    return {"GATE": "pin", "TEAM_PIN": pin, "PIN_SECRET": random_secret()}


def write_workflow(project, repo_root):
    p = os.path.join(repo_root, WORKFLOW)
    with open(p, encoding="utf-8") as fh:
        text = fh.read()
    text = text.replace(PLACEHOLDER, project)
    text = re.sub(r"--project-name=\S+", f"--project-name={project}", text)
    with open(p, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


def workflow_project(repo_root):
    p = os.path.join(repo_root, WORKFLOW)
    if not os.path.isfile(p):
        return None
    with open(p, encoding="utf-8") as fh:
        m = re.search(r"--project-name=(\S+)", fh.read())
    return m.group(1) if m and m.group(1) != PLACEHOLDER else None


def set_team_gate(gate, teams_dir):
    """Keep team.yaml's `gate:` line in step with the site's gate."""
    for team in paths.team_folders():
        p = os.path.join(teams_dir, team, "team.yaml")
        with open(p, encoding="utf-8") as fh:
            text = fh.read()
        new, n = re.subn(r"(?m)^gate:\s*\w+", f"gate: {gate}", text)
        if n:
            with open(p, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(new)


def mark_redeploy(site_dir):
    """Settings changes (gate, code) need a new deploy: leave a fresh stamp in site/ so
    the next publish commits something and GitHub Actions deploys."""
    import datetime
    os.makedirs(site_dir, exist_ok=True)
    with open(os.path.join(site_dir, ".redeploy"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds") + "\n")


def deploy(project, site_dir, acct=None):
    """`wrangler pages deploy` from inside site/ (so site/functions — the gate — ships)."""
    npx = shutil.which("npx")
    if not npx:
        raise SetupError("Node.js isn't installed here: push once instead and GitHub deploys it")
    env = dict(os.environ, CLOUDFLARE_API_TOKEN=get_token())
    if acct:
        env["CLOUDFLARE_ACCOUNT_ID"] = acct
    return subprocess.run([npx, "--yes", "wrangler@4", "pages", "deploy", ".",
                           f"--project-name={project}", "--branch=main"],
                          cwd=site_dir, env=env).returncode


# ---------------------------------------------------------------- CLI
def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--check", action="store_true")
    g.add_argument("--create", metavar="NAME")
    g.add_argument("--gate", choices=["pin", "email", "none"])
    g.add_argument("--deploy", nargs="?", const="", metavar="NAME")
    g.add_argument("--status", nargs="?", const="", metavar="NAME")
    g.add_argument("--forget", action="store_true")
    ap.add_argument("--pin", help="team code for --gate pin (default: a new 8-digit code)")
    ap.add_argument("--project", help="project name (default: the one in deploy.yml)")
    a = ap.parse_args(argv)
    root = paths.ROOT
    try:
        if a.forget:
            forget_token(root)
            print("The saved Cloudflare token is deleted from this repo.")
            return 0
        if a.check:
            verify_token()
            print(f"Token works. Cloudflare account: {account_id()}")
            return 0
        acct = account_id()
        if a.create:
            name = a.create.lower()
            if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,56}", name):
                raise SetupError("project names use lowercase letters, digits and dashes")
            if project_exists(acct, name):
                url = f"https://{(get_project(acct, name) or {}).get('subdomain') or name + '.pages.dev'}"
                print(f"Project {name} already exists: {url}")
            else:
                url = create_project(acct, name)
                print(f"Created the Cloudflare Pages project {name}: {url}")
            if os.path.isfile(os.path.join(root, WORKFLOW)):
                write_workflow(name, root)
                print(f"The deploy workflow now deploys to {name}.")
            print(f"Account ID (for the GitHub secret CLOUDFLARE_ACCOUNT_ID): {acct}")
            return 0
        name = a.project or (a.deploy or a.status or None) or workflow_project(root)
        if not name:
            raise SetupError("no project yet: run --create NAME first")
        if a.gate:
            env = gate_env(a.gate, a.pin)
            set_env(acct, name, env)
            set_team_gate(a.gate, paths.TEAMS_DIR)
            mark_redeploy(os.path.join(root, "site"))
            if a.gate == "pin":
                print(f"Team code set: {env['TEAM_PIN']}  (share it in the team group).")
            else:
                print(f"Gate set to {a.gate}.")
            print("It applies from the next deploy (publish.py now commits and deploys).")
            return 0
        if a.deploy is not None:
            site = os.path.join(root, "site")
            if not os.path.isfile(os.path.join(site, "index.html")):
                raise SetupError("site/ isn't built yet: run engine/scripts/build_site.py first")
            code = deploy(name, site, acct)
            print("Deployed." if code == 0 else f"!! deploy failed (exit {code})")
            return code
        if a.status is not None:
            p = get_project(acct, name)
            if not p:
                raise SetupError(f"no Cloudflare Pages project called {name}")
            env = ((p.get("deployment_configs") or {}).get("production") or {}).get("env_vars") or {}
            latest = p.get("latest_deployment") or {}
            print(f"Project {name}: https://{p.get('subdomain') or name + '.pages.dev'}")
            print(f"Settings: {', '.join(sorted(env)) or 'none'}  (values are not shown)")
            print(f"Last deploy: {latest.get('created_on') or 'never'}")
            return 0
    except SetupError as e:
        print(f"!! {e}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
