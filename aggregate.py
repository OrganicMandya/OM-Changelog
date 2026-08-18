#!/usr/bin/env python3
"""Auto-aggregate the org changelog and rewrite it into customer voice (OM-Infra#86).

Zero-touch pipeline: runs in deploy.yml *before* generate.py. It reads the
human-authored `changelog.d/*.md` fragments each product repo already writes per
PR (CI-enforced, so nothing extra to do per change) plus published GitHub
Releases, filters to customer-facing categories, then has an OpenAI model rewrite
the dev-voice bullets into the page's customer voice — constrained to the facts in
each source line (it may not invent). The result overwrites content.json.

FAIL-OPEN: if the OpenAI key or a GitHub token is missing, or anything goes
wrong, we log a notice and leave the existing curated content.json untouched, so
the page keeps deploying. Auto-aggregation simply activates once the secrets are
provisioned in the vault (see AGGREGATION.md).

Env:
  OPENAI_API_KEY  — OpenAI key (vault: om/openai-api-key). Required to run.
  OM_GH_TOKEN     — GitHub token that can read the source repos' contents +
                    releases (vault: om/github-changelog-reader). Falls back
                    to GITHUB_TOKEN (fine for public repos).
"""
import json
import os
import re
import sys
import urllib.error
import urllib.request

OWNER = "OrganicMandya"

# --- Config (edit these) ---------------------------------------------------
# Which repos feed the page, and which page "surface" each maps to.
# surface ∈ app | website | staff-tools | stock-platform (see generate.py).
SOURCES = {
    "OM-Mobile-App":         "app",
    "OM-Storefront":         "website",
    "om-shopify-theme":      "website",
    "OM-Insights":           "staff-tools",
    "OM-Category-Dashboard": "staff-tools",
    "odoo-sync":             "stock-platform",
}

# changelog.d categories that are safe to show customers. Everything else
# (security, docs, deprecated, removed, internal) is dropped before the model
# sees it — the audience filter. Widen deliberately.
PUBLIC_CATEGORIES = {"added", "changed", "fixed"}

# Second, CONTENT-based gate behind the category filter (#9 review, gate 2).
# The category filter trusts the author's file naming; a sensitive detail
# mis-filed as added/changed/fixed (e.g. the OTP-leak fix that lived under both
# Fixed AND Security) would otherwise slip onto a public page. Any keyword hit
# drops the line outright — before the model, before publish. Widen deliberately.
SENSITIVE_RE = re.compile(
    r"\b(otp|password|passcode|secret|secrets|token|tokens|api[\s_-]?keys?|"
    r"apikeys?|credentials?|vault|private[\s_-]?key|ssh|cookie|session|redact|"
    r"pii|gdpr|cve-|vulnerab|exploit|rce|xss|csrf|sql[\s_-]?inject|injection|"
    r"leak|leaked|breach|malware|razorpay[\s_-]?key|access[\s_-]?token)\b",
    re.I,
)

# How many most-recent shipped releases to pull per repo (keeps the page fresh
# without unbounded history).
RELEASES_PER_REPO = 3

# Rewrite in batches so one large run can't overflow the output limit and truncate
# the JSON — a truncated batch would fail json.loads and (fail-open) leave the page
# un-updated (#9 review, minor). Each batch stays well within the model's output.
BATCH_SIZE = 20

# OpenAI model for the rewrite. Cheap + supports Structured Outputs (strict
# json_schema); bump to gpt-4o / gpt-4.1 for higher-quality wording if wanted.
MODEL = "gpt-4o-mini"
# --------------------------------------------------------------------------

_TOKEN = os.environ.get("OM_GH_TOKEN") or os.environ.get("GITHUB_TOKEN") or ""
_REF_RE = re.compile(r"#(\d+)")
_BULLET_RE = re.compile(r"^\s*[-*]\s+")


def _gh(path):
    """GET https://api.github.com/{path} → parsed JSON, or None on 404/error."""
    req = urllib.request.Request(
        f"https://api.github.com{path}",
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "om-changelog-aggregator",
            **({"Authorization": f"Bearer {_TOKEN}"} if _TOKEN else {}),
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as e:
        if e.code != 404:
            print(f"  ! GitHub {e.code} on {path}", file=sys.stderr)
        return None
    except Exception as e:  # noqa: BLE001 — fail-open
        print(f"  ! GitHub error on {path}: {e}", file=sys.stderr)
        return None


def _decode_content(file_obj):
    import base64
    return base64.b64decode(file_obj.get("content", "")).decode("utf-8", "replace")


def _first_bullet(markdown):
    """The first real changelog bullet in a fragment/release body, flattened."""
    for line in markdown.splitlines():
        if _BULLET_RE.match(line):
            return re.sub(r"\s+", " ", _BULLET_RE.sub("", line)).strip()
    # No bullet? use the first non-empty line.
    for line in markdown.splitlines():
        if line.strip():
            return re.sub(r"\s+", " ", line).strip()
    return ""


def _ref(repo, text):
    m = _REF_RE.search(text)
    return f"{repo}#{m.group(1)}" if m else repo


def collect():
    """Return a list of raw entries: {repo, surface, status, date, ref, text}."""
    raw = []
    for repo, surface in SOURCES.items():
        # 1) Pending fragments → "in-testing".
        listing = _gh(f"/repos/{OWNER}/{repo}/contents/changelog.d")
        for f in listing or []:
            name = f.get("name", "")
            if not name.endswith(".md") or name == "README.md":
                continue
            # <slug>.<category>.md
            parts = name[:-3].rsplit(".", 1)
            category = parts[1].lower() if len(parts) == 2 else ""
            if category not in PUBLIC_CATEGORIES:
                continue
            body = _decode_content(f)
            text = _first_bullet(body)
            if not text:
                continue
            if SENSITIVE_RE.search(text):
                continue  # security keyword denylist — never publish (gate 2)
            # Fragment mtime ≈ last commit touching it.
            commits = _gh(
                f"/repos/{OWNER}/{repo}/commits?path=changelog.d/{name}&per_page=1"
            )
            date = "1970-01-01"
            if commits:
                date = (commits[0].get("commit", {}).get("committer", {})
                        .get("date", "1970-01-01"))[:10]
            raw.append({"repo": repo, "surface": surface, "status": "in-testing",
                        "date": date, "ref": _ref(repo, text), "text": text})

        # 2) Recent published releases → "shipped".
        releases = _gh(f"/repos/{OWNER}/{repo}/releases?per_page={RELEASES_PER_REPO}")
        for rel in releases or []:
            if rel.get("draft") or rel.get("prerelease"):
                continue
            date = (rel.get("published_at") or "1970-01-01")[:10]
            for line in (rel.get("body") or "").splitlines():
                if not _BULLET_RE.match(line):
                    continue
                text = re.sub(r"\s+", " ", _BULLET_RE.sub("", line)).strip()
                if len(text) < 12:
                    continue
                if SENSITIVE_RE.search(text):
                    continue  # security keyword denylist (gate 2)
                raw.append({"repo": repo, "surface": surface, "status": "shipped",
                            "date": date, "ref": _ref(repo, text), "text": text})
    # Newest first, de-dupe by (ref, status).
    seen, deduped = set(), []
    for e in sorted(raw, key=lambda x: x["date"], reverse=True):
        key = (e["ref"], e["status"])
        if key not in seen:
            seen.add(key)
            deduped.append(e)
    return deduped


VOICE = """You rewrite internal engineering changelog lines into a public,
customer-facing "what we shipped" page for Organic Mandya (an organic grocery
brand). Voice: plain, warm, concrete, non-technical — a customer or shopkeeper
should understand it. No jargon, no file names, no internal ticket numbers, no
tech stack names (Shopify/Odoo/Flutter/WebEngage/etc.).

HARD RULES:
- Rewrite ONLY. Never invent capabilities, numbers, or outcomes not present in
  the source line. If a line is purely internal (a refactor, a test, tooling)
  with no customer-visible effect, set "skip": true for it.
- Keep it truthful about status: "in-testing" items are being checked, not yet
  guaranteed live; "shipped" items are live.
- title: <=60 chars, sentence case, the change in customer terms.
- body: 1-2 short sentences on what it means for them.
- why: OPTIONAL one line on why it matters — only for clearly high-impact items
  (revenue, reliability, a visible fix); use null otherwise.
"""

# OpenAI Structured Outputs (strict) requires EVERY property in `required` and
# `additionalProperties: false` on every object. `why` is optional in spirit, so
# it's typed nullable ("string" | null) and the model returns null when it
# doesn't apply — we drop empty/null whys when building the entry.
SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "ref": {"type": "string"},
                    "skip": {"type": "boolean"},
                    "title": {"type": "string"},
                    "body": {"type": "string"},
                    "why": {"type": ["string", "null"]},
                },
                "required": ["ref", "skip", "title", "body", "why"],
            },
        }
    },
    "required": ["items"],
}


def rewrite(raw):
    """Ask an OpenAI model to rewrite each raw line into customer voice. Returns dict by ref.

    Batched (BATCH_SIZE) so a large run can't overflow the output limit and truncate
    the structured-output JSON. Uses OpenAI Structured Outputs (response_format
    json_schema with strict:true), so the reply is guaranteed to conform to SCHEMA and
    parses straight from the message content."""
    from openai import OpenAI
    client = OpenAI()
    out = {}
    for start in range(0, len(raw), BATCH_SIZE):
        batch = raw[start:start + BATCH_SIZE]
        payload = [{"ref": e["ref"], "surface": e["surface"], "status": e["status"],
                    "source": e["text"]} for e in batch]
        resp = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": VOICE},
                {"role": "user", "content":
                 "Rewrite each entry. Return one item per input ref.\n\n"
                 + json.dumps(payload, ensure_ascii=False, indent=2)},
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {"name": "changelog_rewrite",
                                "strict": True, "schema": SCHEMA},
            },
        )
        msg = resp.choices[0].message
        if getattr(msg, "refusal", None) or not msg.content:
            continue  # model refused / empty — fail-open, skip this batch
        for item in json.loads(msg.content).get("items", []):
            out[item["ref"]] = item
    return out


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    content_path = os.path.join(here, "content.json")

    if not os.environ.get("OPENAI_API_KEY"):
        print("aggregate: OPENAI_API_KEY not set — leaving content.json as-is "
              "(auto-aggregation inactive; see AGGREGATION.md).")
        return 0
    if not _TOKEN:
        print("aggregate: no GitHub token — leaving content.json as-is.")
        return 0

    raw = collect()
    print(f"aggregate: collected {len(raw)} candidate entries from "
          f"{len(SOURCES)} repos.")
    if not raw:
        print("aggregate: nothing collected — leaving content.json as-is.")
        return 0

    rewritten = rewrite(raw)

    entries = []
    for e in raw:
        r = rewritten.get(e["ref"])
        if not r or r.get("skip") or not r.get("title") or not r.get("body"):
            continue
        entry = {"surface": e["surface"], "status": e["status"], "date": e["date"],
                 "title": r["title"].strip(), "body": r["body"].strip()}
        why = (r.get("why") or "").strip()
        if why:
            entry["why"] = why
        entry["ref"] = e["ref"]
        entries.append(entry)

    if not entries:
        print("aggregate: everything filtered/skipped — leaving content.json as-is.")
        return 0

    # MERGE over the committed content.json rather than replacing it (#9 review):
    # a full replace would wipe the curated backfill the moment aggregation goes
    # live, since collect() only sees current fragments + the last few releases.
    # Rule: `in-testing` is fully refreshed each run — only currently-open
    # fragments should read as "in testing", so stale ones drop — while `shipped`
    # entries accumulate as history; a fresh rewrite wins on a ref collision.
    # deploy.yml renders + deploys but never commits content.json back, so the
    # committed copy stays a stable historical seed each run layers onto.
    fresh_refs = {e["ref"] for e in entries}
    try:
        prior = json.load(open(content_path, encoding="utf-8")).get("entries", [])
    except Exception:
        prior = []  # missing/unreadable seed → just publish the fresh set (fail-open)
    merged = list(entries)
    for e in prior:
        if e.get("status") == "in-testing":
            continue  # refreshed from live fragments; don't carry stale ones
        if e.get("ref") in fresh_refs:
            continue  # a fresh rewrite already replaced this ref
        merged.append(e)  # preserve historical / hand-curated shipped entry

    data = {
        "_comment": ("Fresh entries are auto-aggregated from each repo's changelog.d "
                     "fragments + recent releases and rewritten to customer voice by "
                     "an OpenAI model (OM-Infra#86), then MERGED over the committed "
                     "history here: shipped entries accumulate, in-testing is refreshed "
                     "each deploy. This committed copy is the historical seed — safe to "
                     "curate; to change auto-sourced wording, fix the source fragment."),
        "entries": merged,
    }
    with open(content_path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    print(f"aggregate: wrote {len(merged)} entries "
          f"({len(entries)} fresh + {len(merged) - len(entries)} preserved).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
