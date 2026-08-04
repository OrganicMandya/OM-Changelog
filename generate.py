#!/usr/bin/env python3
"""Org changelog page generator (OM-Infra#86).

Aggregates each repo's CHANGELOG.md into one plain-language, categorized page:
  - categorized by surface (App / Website / Staff tools / Stock & platform)
  - Shipped (dated [x.y.z] sections) vs In-testing ([Unreleased])
  - small ticket refs, auto-linked

Reads via `gh api` so it runs the same locally and in CI. Writes public/index.html.
"""
import subprocess, json, re, html, sys, datetime, os

OWNER = "OrganicMandya"

# surface -> (emoji label, [repos]). Order is the page order.
SURFACES = [
    ("App",              "\U0001F4F1", ["OM-Mobile-App"]),
    ("Website",          "\U0001F6CD",  ["OM-Storefront", "om-shopify-theme"]),
    ("Staff tools",      "\U0001F4CA", ["OM-Insights", "OM-Category-Dashboard"]),
    ("Stock & platform", "\U0001F4E6", ["OM-Infra", "odoo-sync"]),
]
MAX_SHIPPED_VERSIONS = 5   # per repo, most recent first
MAX_TESTING = 8            # per repo: recent In-testing headlines (rest summarised as "+N more")

def gh_json(path):
    out = subprocess.run(["gh", "api", path], capture_output=True, text=True,
                         encoding="utf-8", errors="replace")
    if out.returncode != 0:
        return None
    return json.loads(out.stdout)

def fetch_changelog(repo):
    data = gh_json(f"repos/{OWNER}/{repo}/contents/CHANGELOG.md")
    if not data or "content" not in data:
        return None
    import base64
    return base64.b64decode(data["content"]).decode("utf-8", "replace")

VER_RE = re.compile(r"^##\s*\[(?P<ver>[^\]]+)\]\s*(?:-\s*(?P<date>\d{4}-\d{2}-\d{2}))?")
SUB_RE = re.compile(r"^###\s+(?P<name>.+?)\s*$")
BULLET_RE = re.compile(r"^\s*-\s+(?P<text>.*)$")

def parse_changelog(text):
    """Return list of sections: {ver, date, groups: [{name, bullets:[md]}]}."""
    sections, cur, curgroup = [], None, None
    for raw in text.splitlines():
        m = VER_RE.match(raw)
        if m:
            cur = {"ver": m.group("ver").strip(), "date": m.group("date"), "groups": []}
            sections.append(cur); curgroup = None
            continue
        if cur is None:
            continue
        sm = SUB_RE.match(raw)
        if sm:
            curgroup = {"name": sm.group("name").strip(), "bullets": []}
            cur["groups"].append(curgroup); continue
        bm = BULLET_RE.match(raw)
        if bm:
            if curgroup is None:
                curgroup = {"name": None, "bullets": []}; cur["groups"].append(curgroup)
            curgroup["bullets"].append(bm.group("text").rstrip())
        elif raw.strip() and curgroup and curgroup["bullets"]:
            # continuation of the previous wrapped bullet line
            curgroup["bullets"][-1] += " " + raw.strip()
    return sections

def summarize(b):
    """Plain-language headline for a technical changelog bullet: the leading **bold** lead, else
    the first sentence — with the trailing ticket ref preserved."""
    m = re.match(r"\*\*(.+?)\*\*", b)
    if m:
        head = m.group(1).strip().rstrip(".")
    else:
        head = re.split(r"(?<=[.!?])\s", b, maxsplit=1)[0]
        head = re.split(r"\s[—-]\s", head, maxsplit=1)[0].strip()
    refs = re.findall(r"\(([^)]*#\d+[^)]*)\)", b)
    if refs and "#" not in head:
        head += f" ({refs[-1]})"
    return f"**{head}**" if m else head

def md_inline(s, repo):
    """Minimal, SAFE markdown -> HTML: escape first, then re-introduce a small allowlist."""
    s = html.escape(s)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    s = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"\[([^\]]+)\]\((https?://[^)]+)\)", r'<a href="\2">\1</a>', s)
    # cross-repo ref: repo#123
    s = re.sub(r"\b([A-Za-z0-9._-]+)#(\d+)\b",
               rf'<a href="https://github.com/{OWNER}/\1/issues/\2">\1#\2</a>', s)
    # bare #123 -> this repo (avoid matching inside an href we just built)
    s = re.sub(r"(^|[\s(])#(\d+)\b",
               rf'\1<a href="https://github.com/{OWNER}/{repo}/issues/\2">#\2</a>', s)
    return s

def render():
    built = os.environ.get("BUILD_DATE") or datetime.date.today().isoformat()
    cards = []
    for label, emoji, repos in SURFACES:
        repo_blocks = []
        for repo in repos:
            text = fetch_changelog(repo)
            if not text:
                continue
            secs = parse_changelog(text)
            unreleased = next((s for s in secs if s["ver"].lower() == "unreleased"), None)
            shipped = [s for s in secs if s["ver"].lower() != "unreleased" and s["date"]][:MAX_SHIPPED_VERSIONS]
            if not (unreleased and any(g["bullets"] for g in unreleased["groups"])) and not shipped:
                continue
            groups_html = []
            if unreleased and any(g["bullets"] for g in unreleased["groups"]):
                groups_html.append(render_release(repo, "In testing", None, unreleased["groups"], "testing"))
            for s in shipped:
                groups_html.append(render_release(repo, s["ver"], s["date"], s["groups"], "shipped"))
            repo_blocks.append(
                f'<div class="repo"><h3 class="repo-name">{html.escape(repo)}</h3>{"".join(groups_html)}</div>')
        if repo_blocks:
            cards.append(f'<section class="surface"><h2>{emoji} {html.escape(label)}</h2>{"".join(repo_blocks)}</section>')
    return PAGE.format(surfaces="\n".join(cards), built=built)

def render_release(repo, title, date, groups, kind):
    badge = '<span class="badge shipped">Shipped</span>' if kind == "shipped" \
            else '<span class="badge testing">In testing</span>'
    ver = f'<span class="ver">{html.escape(title)}</span>'
    when = f'<span class="date">{html.escape(date)}</span>' if date else ""
    bullets = [b for g in groups for b in g["bullets"]]
    extra = 0
    if kind == "testing" and len(bullets) > MAX_TESTING:
        extra = len(bullets) - MAX_TESTING
        bullets = bullets[:MAX_TESTING]
    items = [f"<li>{md_inline(summarize(b), repo)}</li>" for b in bullets]
    if not items:
        return ""
    if extra:
        items.append(f'<li class="more">+{extra} more in this cycle</li>')
    return (f'<div class="release"><div class="rel-head">{badge}{ver}{when}</div>'
            f'<ul class="entries">{"".join(items)}</ul></div>')

PAGE = """<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Organic Mandya — What we're shipping</title>
<style>
:root{{--bg:#f7f6f3;--card:#fff;--ink:#1c2b23;--mut:#5c6b62;--line:#e6e3dc;--green:#2e7d4f;--amber:#b5791f;--accent:#2e7d4f}}
*{{box-sizing:border-box}}
body{{margin:0;font:16px/1.55 -apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;color:var(--ink);background:var(--bg)}}
.wrap{{max-width:900px;margin:0 auto;padding:32px 20px 64px}}
header.top{{padding:8px 0 24px;border-bottom:2px solid var(--accent);margin-bottom:28px}}
header.top h1{{margin:0 0 6px;font-size:28px}}
header.top p{{margin:0;color:var(--mut)}}
.surface{{margin:34px 0}}
.surface>h2{{font-size:20px;margin:0 0 14px;padding-bottom:6px;border-bottom:1px solid var(--line)}}
.repo{{margin:0 0 18px}}
.repo-name{{font-size:13px;letter-spacing:.02em;text-transform:uppercase;color:var(--mut);margin:14px 0 8px}}
.release{{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px 16px;margin:0 0 10px}}
.rel-head{{display:flex;align-items:center;gap:10px;margin-bottom:8px}}
.badge{{font-size:12px;font-weight:600;padding:2px 9px;border-radius:999px;color:#fff}}
.badge.shipped{{background:var(--green)}}
.badge.testing{{background:var(--amber)}}
.ver{{font-weight:700}}
.date{{color:var(--mut);font-size:13px;margin-left:auto}}
ul.entries{{margin:0;padding:0;list-style:none}}
ul.entries li{{padding:6px 0;border-top:1px dashed var(--line)}}
ul.entries li:first-child{{border-top:none}}
.gtag{{display:inline-block;font-size:11px;font-weight:600;color:var(--accent);background:#eaf3ed;border-radius:6px;padding:1px 7px;margin-right:8px;vertical-align:1px}}
a{{color:var(--accent)}}
code{{background:#eee;border-radius:4px;padding:0 4px;font-size:.9em}}
footer{{margin-top:40px;color:var(--mut);font-size:13px;text-align:center}}
</style></head>
<body><div class="wrap">
<header class="top">
  <h1>Organic Mandya — What we're shipping</h1>
  <p>A plain-language view of what changed across our products. <strong>Shipped</strong> = released; <strong>In testing</strong> = merged, verifying on staging.</p>
</header>
{surfaces}
<footer>Generated {built} · sourced from each repo's CHANGELOG · OM-Infra#86</footer>
</div></body></html>
"""

if __name__ == "__main__":
    out = render()
    os.makedirs("public", exist_ok=True)
    with open("public/index.html", "w", encoding="utf-8") as f:
        f.write(out)
    print(f"wrote public/index.html ({len(out)} bytes)")
