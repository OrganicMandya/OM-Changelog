# OM-Changelog

The **org-wide changelog page** — one plain-language view of what Organic Mandya ships across every
surface. Built for OM-Infra#86 (part of the weekly-release-cadence epic, OM-Infra#82).

**Live:** https://changelog.organicmandya.club

## What it is
`generate.py` aggregates every repo's `CHANGELOG.md` into a single categorized page:

- **Surfaces:** 📱 App · 🛍️ Website · 📊 Staff tools · 📦 Stock & platform
- **Status:** **Shipped** (a repo's dated `[x.y.z]` sections) vs **In testing** (its `[Unreleased]`)
- Plain-language **headlines** (the bold lead of each changelog entry), with auto-linked ticket refs

Output is a single static `public/index.html` — no framework, no build step.

## How it's hosted
GitHub Pages (source: GitHub Actions). `.github/workflows/build-pages.yml` regenerates the page and
deploys it:
- **weekly** (Wed 12:00 UTC — release-train day), on **manual dispatch**, and on a **`changelog-refresh`**
  repository-dispatch (so the cut-release workflow can refresh it on a release).
- The committed `public/index.html` is always deployable, so the page is live even if a refresh is skipped.

## Run it locally
```bash
gh auth status            # needs read access to the org repos
python generate.py        # writes public/index.html
open public/index.html
```

## Owner setup (one-time, to enable auto-refresh + the domain)
1. **DNS** — add a GoDaddy CNAME: `changelog` → `<org>.github.io` (the `.club` zone is at GoDaddy).
2. **Pages** — Settings → Pages → Source: **GitHub Actions**; custom domain `changelog.organicmandya.club`.
3. **Cross-repo read** (for scheduled auto-refresh) — store a fine-grained PAT (OrganicMandya, Contents:read)
   at `om/github-changelog-reader-token`, and add this repo to the `github-actions-secrets-reader` trust
   (OM-Infra). Until then the page deploys the committed snapshot (no auto-refresh).

## Config
Surfaces / repo mapping and the per-repo caps live at the top of [`generate.py`](generate.py).
