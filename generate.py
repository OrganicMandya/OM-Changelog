#!/usr/bin/env python3
"""Org changelog page generator (OM-Infra#86).

Renders the curated, plain-language entries in content.json into one static page that matches the
approved design: a dark, green hero; a sticky surface filter (client-side); updates grouped by
IN TESTING NOW / SHIPPED THIS WEEK / EARLIER; per-card surface + status badges, an optional
"Why it matters" line, and a REF chip. Writes public/index.html — no framework, one self-contained file.

Content voice lives in content.json (see README). This generator only lays it out.
Env: AS_OF (YYYY-MM-DD, defaults today), ANCHOR (YYYY-MM-DD start of "this week"; defaults last Tuesday).
"""
import json, re, html, os, datetime

OWNER = "OrganicMandya"

# The public page must NOT render REF chips: they link to PRIVATE org repos (404
# for the public) and expose internal repo/ticket structure (#9 review, gate 1).
# The `ref` stays in content.json for internal tracking + aggregation de-dupe; an
# internal build can re-enable the chips with SHOW_REFS=1.
SHOW_REFS = os.environ.get("SHOW_REFS") == "1"

SURFACE = {
    "app":            {"label": "App",              "badge": "APP",              "emoji": "\U0001F4F1", "color": "#59b877"},
    "website":        {"label": "Website",          "badge": "WEBSITE",          "emoji": "\U0001F310", "color": "#5aa0e0"},
    "staff-tools":    {"label": "Staff tools",      "badge": "STAFF TOOLS",      "emoji": "\U0001F4CA", "color": "#a67fe0"},
    "stock-platform": {"label": "Stock & platform", "badge": "STOCK & PLATFORM", "emoji": "⚙️", "color": "#d7a24b"},
}
STATUS = {
    "in-testing": {"label": "IN TESTING", "color": "#d7a24b"},
    "shipped":    {"label": "SHIPPED",    "color": "#59b877"},
}

def d(s):
    return datetime.date.fromisoformat(s)

def fmt_date(dt):
    return f"{dt.day} {dt:%b %Y}"

def linkify(s):
    s = html.escape(s)
    s = re.sub(r'\b((?:[a-z0-9-]+\.)+(?:club|com|shop|dev|in)(?:/[^\s<]*)?)',
               r'<a href="https://\1" target="_blank" rel="noopener">\1</a>', s)
    return s

def ref_chip(ref):
    if not SHOW_REFS:
        return ""  # public build: never expose private repo/ticket links (gate 1)
    m = re.match(r"([A-Za-z0-9._-]+)#(\d+)", ref or "")
    if not m:
        return ""
    repo, num = m.group(1), m.group(2)
    url = f"https://github.com/{OWNER}/{repo}/issues/{num}"
    return (f'<div class="ref"><span class="ref-lbl">REF</span>'
            f'<a class="ref-chip" href="{url}" target="_blank" rel="noopener">{html.escape(repo)} #{num}</a></div>')

def card(e):
    s = SURFACE.get(e["surface"], {"label": e["surface"], "badge": e["surface"].upper(), "emoji": "", "color": "#59b877"})
    st = STATUS.get(e["status"], {"label": e["status"].upper(), "color": "#59b877"})
    when = "This week" if e["status"] == "in-testing" else fmt_date(d(e["date"]))
    why = ""
    if e.get("why"):
        why = (f'<div class="why"><span class="why-lbl">Why it matters</span> {linkify(e["why"])}</div>')
    return f"""<article class="card" data-surface="{e['surface']}" style="--sc:{s['color']};--stc:{st['color']}">
      <div class="chead">
        <div class="badges">
          <span class="badge surface">{s['emoji']} {html.escape(s['badge'])}</span>
          <span class="badge status"><span class="dot"></span>{st['label']}</span>
        </div>
        <span class="when">{html.escape(when)}</span>
      </div>
      <h3 class="ctitle">{html.escape(e['title'])}</h3>
      <p class="cbody">{linkify(e['body'])}</p>
      {why}
      {ref_chip(e.get('ref',''))}
    </article>"""

def section(title, entries):
    if not entries:
        return ""
    cards = "\n".join(card(e) for e in entries)
    return f'<section class="group"><h2 class="section">{title}</h2>{cards}</section>'

def build():
    data = json.load(open(os.path.join(os.path.dirname(__file__) or ".", "content.json"), encoding="utf-8"))
    entries = data["entries"]
    as_of = d(os.environ["AS_OF"]) if os.environ.get("AS_OF") else datetime.date.today()
    if os.environ.get("ANCHOR"):
        anchor = d(os.environ["ANCHOR"])
    else:
        anchor = as_of - datetime.timedelta(days=(as_of.weekday() - 1) % 7)  # most recent Tuesday

    in_testing = [e for e in entries if e["status"] == "in-testing"]
    shipped = [e for e in entries if e["status"] == "shipped"]
    this_week = sorted([e for e in shipped if d(e["date"]) >= anchor], key=lambda e: e["date"], reverse=True)
    earlier   = sorted([e for e in shipped if d(e["date"]) <  anchor], key=lambda e: e["date"], reverse=True)

    wk = f"WEEK OF {anchor.day} {anchor:%B %Y}".upper()
    body = "\n".join([
        section('<span class="ico">✏️</span> IN TESTING NOW <span class="muted">— HELP US CHECK THESE</span>', in_testing),
        section(f'<span class="ico">✅</span> SHIPPED <span class="muted">— {wk}</span>', this_week),
        section('EARLIER', earlier),
    ])

    tabs = ['<button class="tab active" data-filter="all">All updates</button>']
    for key, s in SURFACE.items():
        tabs.append(f'<button class="tab" data-filter="{key}"><span class="tdot" style="background:{s["color"]}"></span>{s["emoji"]} {html.escape(s["label"])}</button>')
    tabs_html = "\n".join(tabs)

    built = os.environ.get("BUILD_DATE") or as_of.isoformat()
    return HEAD + STYLE + BODY.format(tabs=tabs_html, body=body, built=built) + SCRIPT + "</body></html>\n"

HEAD = """<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Organic Mandya — What we shipped</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,500;9..144,600&display=swap" rel="stylesheet">
"""

STYLE = """<style>
:root{
  --bg:#0a0f0c; --card:#0f1712; --line:#1f2c24; --line2:#26332b;
  --ink:#eef3ee; --mut:#9cb2a6; --dim:#7d9488; --green:#59b877;
  --wrap:920px;
}
*{box-sizing:border-box} html{scroll-behavior:smooth}
body{margin:0;background:var(--bg);color:var(--ink);
  font:16px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;-webkit-font-smoothing:antialiased}
.wrap{max-width:var(--wrap);margin:0 auto;padding:0 22px}
a{color:var(--green);text-decoration:none} a:hover{text-decoration:underline}
h1,h2,h3{font-family:"Fraunces",Georgia,"Times New Roman",serif;font-weight:500;margin:0}

/* hero */
.hero{background:radial-gradient(120% 140% at 22% -20%,rgba(46,120,80,.45) 0,transparent 55%),linear-gradient(160deg,#0e3f2c 0%,#0b2b1f 42%,#081410 100%);
  border-bottom:1px solid #10221a}
.hero .wrap{padding:34px 22px 40px}
.brand{display:flex;align-items:center;gap:9px;color:#dfeee6;font-weight:600;font-size:16px}
.brand .leaf{color:var(--green);font-size:20px}
.hero h1{font-size:clamp(40px,7vw,68px);line-height:1.03;letter-spacing:-.01em;margin:18px 0 16px;color:#f4f8f4}
.hero p{max-width:540px;color:#bcd2c5;font-size:18px;margin:0 0 22px}
.pill{display:inline-flex;align-items:center;gap:8px;font-size:12px;font-weight:600;letter-spacing:.09em;text-transform:uppercase;
  color:#9fe0b8;background:rgba(89,184,119,.10);border:1px solid rgba(89,184,119,.28);padding:8px 14px;border-radius:999px}
.pill .dot{width:7px;height:7px;border-radius:50%;background:var(--green);box-shadow:0 0 8px rgba(89,184,119,.7)}

/* sticky filter */
.filterbar{position:sticky;top:0;z-index:20;background:rgba(10,15,12,.86);backdrop-filter:blur(8px);border-bottom:1px solid var(--line)}
.tabs{display:flex;flex-wrap:wrap;gap:9px;padding:12px 22px}
.tab{display:inline-flex;align-items:center;gap:7px;cursor:pointer;font:inherit;font-size:14px;font-weight:500;
  color:#cfe0d5;background:#12201a;border:1px solid var(--line2);padding:7px 14px;border-radius:999px;transition:.15s}
.tab:hover{border-color:#33463b}
.tab.active{background:#123b28;border-color:#2f6a48;color:#eafaf0}
.tdot{width:8px;height:8px;border-radius:50%}

/* sections */
main{padding:26px 0 8px}
.group{margin:26px 0}
.section{display:flex;align-items:center;gap:10px;font-family:inherit;font-size:13px;font-weight:600;letter-spacing:.11em;
  text-transform:uppercase;color:#8fae9d;margin:0 0 14px}
.section::after{content:"";flex:1;height:1px;background:var(--line)}
.section .ico{font-size:15px}.section .muted{color:var(--dim);font-weight:600}

/* card */
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:18px 20px;margin:0 0 14px}
.chead{display:flex;align-items:center;gap:10px;margin-bottom:11px}
.badges{display:flex;gap:8px;flex-wrap:wrap}
.badge{display:inline-flex;align-items:center;gap:6px;font-size:11px;font-weight:700;letter-spacing:.06em;
  padding:3px 9px;border-radius:7px;text-transform:uppercase}
.badge.surface{color:var(--sc);background:color-mix(in srgb,var(--sc) 16%,transparent);border:1px solid color-mix(in srgb,var(--sc) 30%,transparent)}
.badge.status{color:var(--stc);background:color-mix(in srgb,var(--stc) 13%,transparent)}
.badge.status .dot{width:6px;height:6px;border-radius:50%;background:var(--stc)}
.when{margin-left:auto;color:var(--dim);font-size:13px;white-space:nowrap}
.ctitle{font-size:21px;font-weight:600;color:#f2f7f2;margin:2px 0 8px;letter-spacing:-.005em}
.cbody{color:#a9bfb2;margin:0;font-size:15.5px}
.why{margin-top:12px;padding-top:11px;border-top:1px dashed var(--line2);color:#9db3a6;font-size:14.5px}
.why-lbl{color:var(--green);font-weight:700}
.ref{display:flex;align-items:center;gap:9px;margin-top:13px}
.ref-lbl{color:var(--dim);font-size:11px;font-weight:700;letter-spacing:.08em}
.ref-chip{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:12px;color:#c3d5c9;
  background:#0b1410;border:1px solid var(--line2);padding:3px 9px;border-radius:6px}
.ref-chip:hover{text-decoration:none;border-color:#39513f}

/* footer */
footer{border-top:1px solid var(--line);margin-top:26px}
footer .wrap{padding:22px 22px 60px;color:var(--dim);font-size:14px}
footer p{margin:0 0 10px} footer .b{color:#c3d5c9;font-weight:600}
.s-test{color:#d7a24b;font-weight:700}.s-ship{color:var(--green);font-weight:700}
@media(max-width:560px){.hero h1{font-size:40px}.when{display:none}}
.morewrap{display:flex;justify-content:center;margin:26px 0 8px}
.showmore{appearance:none;cursor:pointer;font:inherit;font-size:14px;font-weight:600;letter-spacing:.02em;
  color:#d7ecdd;background:rgba(89,184,119,.08);border:1px solid rgba(89,184,119,.35);border-radius:999px;padding:11px 24px;transition:background .15s,border-color .15s}
.showmore:hover{background:rgba(89,184,119,.16);border-color:rgba(89,184,119,.6)}
.showmore:focus-visible{outline:2px solid var(--green);outline-offset:2px}
</style>
"""

BODY = """</head><body>
<header class="hero"><div class="wrap">
  <div class="brand"><span class="leaf">\U0001F343</span> Organic Mandya</div>
  <h1>What we shipped</h1>
  <p>A plain-language record of the improvements we make to the app, website, and staff tools — so the whole team and leadership can follow along.</p>
  <p style="max-width:560px;color:#8fb3a0;font-size:15px;margin:-6px 0 20px">Since June we've shipped <strong style="color:#d7ecdd">600+ improvements</strong> across the app, website, staff tools and stock systems. The updates below are the highlights — the ones you'd actually notice.</p>
  <span class="pill"><span class="dot"></span> Updated every Wednesday</span>
</div></header>

<div class="filterbar"><div class="wrap tabs">
{tabs}
</div></div>

<main class="wrap">
{body}
<div class="morewrap"><button id="showmore" class="showmore" type="button">Show more</button></div>
</main>

<footer><div class="wrap">
  <p><span class="b">Two statuses:</span> <span class="s-test">In testing</span> = we're checking it now, help us try it · <span class="s-ship">Shipped</span> = live for everyone. The small <span class="b">Ref</span> code is just an internal tracking number for the team — you don't need it unless you're testing.</p>
  <p><span class="b">How this works:</span> every Wednesday we ship the week's changes and this page updates in plain language. Leadership also gets a short email digest that links here. Categories: \U0001F4F1 the customer app · \U0001F310 the website · \U0001F4CA internal staff tools · ⚙️ stock &amp; behind-the-scenes systems.</p>
  <p style="margin-top:14px;color:#5f7568">Generated {built} · OM-Infra#86</p>
</div></footer>
"""

SCRIPT = """<script>
(function(){
  var PAGE=15;                       // how many updates to reveal per "Show more"
  var tabs=[].slice.call(document.querySelectorAll('.tab'));
  var cards=[].slice.call(document.querySelectorAll('.card'));
  var groups=[].slice.call(document.querySelectorAll('.group'));
  var moreBtn=document.getElementById('showmore');
  var filter='all', shown=PAGE;
  function apply(){
    var matched=0, seen=0;
    cards.forEach(function(c){
      var isMatch=(filter==='all'||c.dataset.surface===filter);
      if(!isMatch){c.style.display='none';return;}
      matched++;
      // reveal only the first `shown` matches, in newest-first document order
      c.style.display=(seen<shown)?'':'none';
      seen++;
    });
    groups.forEach(function(g){
      var any=[].slice.call(g.querySelectorAll('.card')).some(function(c){return c.style.display!=='none';});
      g.style.display=any?'':'none';
    });
    tabs.forEach(function(t){t.classList.toggle('active',t.dataset.filter===filter);});
    var remaining=matched-Math.min(shown,matched);
    if(moreBtn){
      moreBtn.style.display=remaining>0?'':'none';
      moreBtn.textContent='Show '+Math.min(PAGE,remaining)+' more \\u00b7 '+remaining+' left';
    }
  }
  tabs.forEach(function(t){t.addEventListener('click',function(){filter=t.dataset.filter;shown=PAGE;apply();});});
  if(moreBtn){moreBtn.addEventListener('click',function(){shown+=PAGE;apply();});}
  apply();
})();
</script>
"""

if __name__ == "__main__":
    out = build()
    os.makedirs("public", exist_ok=True)
    with open("public/index.html", "w", encoding="utf-8") as f:
        f.write(out)
    print(f"wrote public/index.html ({len(out)} bytes)")
