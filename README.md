# OM-Changelog

The **org-wide changelog page** — one plain-language view of what Organic Mandya ships, for the whole
team and leadership. Built for OM-Infra#86 (part of the weekly-release-cadence epic, OM-Infra#82), to the
CTO's approved design.

**Live:** https://changelog.organicmandya.club

## What it is
`generate.py` renders the curated entries in **`content.json`** into a single static `public/index.html`
that matches the approved design:

- **Hero** + a sticky **surface filter** (All / 📱 App / 🌐 Website / 📊 Staff tools / ⚙️ Stock & platform) — client-side, no framework.
- Updates grouped by **IN TESTING NOW** → **SHIPPED — this week** → **EARLIER** (by date).
- Per-card **surface + status badges**, an optional **"Why it matters"** line, and a small **REF** chip.

No build step, no dependencies — one self-contained HTML file.

## The content model — `content.json`
The page reads from `content.json`, **not** from repo CHANGELOGs — because the design's voice is
**plain-language, non-technical** ("Test notifications kept away from real customers"), which a raw
changelog can't produce. Each entry:

```json
{
  "surface": "app | website | staff-tools | stock-platform",
  "status":  "in-testing | shipped",
  "date":    "2026-08-06",
  "title":   "Short, human headline — no jargon",
  "body":    "1–2 plain sentences a non-engineer understands.",
  "why":     "(optional) one line on why it matters to the business",
  "ref":     "OM-Mobile-App#133"
}
```

**Voice guide:** write for a store manager or the founder, not an engineer. Say what changed and why it
helps; avoid repo/tooling terms. `why` only on high-impact items. `in-testing` = merged, being verified;
`shipped` = live. `ref` is `repo#number` (issue or PR) and auto-links.

### Keeping it fresh
- **Now (curated):** each Monday, edit `content.json` — add the week's changes in plain language, and
  flip items from `in-testing` to `shipped`. Merge → the page rebuilds.
- **Planned (assisted):** an optional helper that drafts `content.json` entries from the week's merged PRs
  (LLM rewrite) for a human to approve — makes the weekly update near-hands-off. Tracked on OM-Infra#86.

## Hosting
**Cloudflare Pages** (project `om-changelog`), on the standard OM stack alongside OM-Insights — the
project + custom domain are Terraform-managed in **OM-Infra `stacks/om-changelog`**. `deploy.yml`
renders `public/` and `wrangler pages deploy`s it on **push** to `content.json`/`generate.py`,
**weekly** (Wed — re-groups by date), on **dispatch**, and on the `changelog-refresh`
repository-dispatch (from the #85 cut-release). The Cloudflare API token comes from the OM vault
(`om/cloudflare-api-token`) via OIDC — no GitHub secret.

## Run it locally
```bash
python generate.py    # reads content.json -> writes public/index.html
# open public/index.html
```

## Owner setup (one-time)
1. **Apply the Terraform stack** — OM-Infra → `terraform.yml` → `stacks/om-changelog` → plan, then apply
   (creates the Cloudflare Pages project + registers the custom domain).
2. **DNS** — GoDaddy CNAME `changelog` → `om-changelog.pages.dev` (the project's `*.pages.dev`; see the
   stack's `pages_dev_subdomain` output). Cloudflare validates the custom domain once this is live.
