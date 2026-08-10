# Changelog

All notable changes to OM-Changelog, newest first. Format loosely follows
[Keep a Changelog](https://keepachangelog.com/). **Every PR adds an entry under `[Unreleased]`.**

## [Unreleased]

### Changed
- **Rebuilt the page to the CTO's approved design + switched to a curated content source (OM-Infra#86).** Dark green hero, sticky client-side **surface filter**, updates grouped **In testing → Shipped this week → Earlier**, per-card surface/status badges, optional "Why it matters", and a REF chip. The generator now renders a curated **`content.json`** (plain-language entries) instead of scraping repo CHANGELOGs — the design's non-technical voice can't come from raw changelogs — which also **drops the cross-repo vault-token dependency**. Seeded with the approved sample entries. Weekly re-group + auto-draft-from-PRs (LLM) is the planned follow-up.

### Added
- **Org changelog page — generator + hosting (OM-Infra#86).** `generate.py` aggregates every repo's `CHANGELOG.md` into one plain-language, categorized page (App / Website / Staff tools / Stock & platform) with Shipped / In-testing status badges and auto-linked ticket refs; published to GitHub Pages (`changelog.organicmandya.club`) by `build-pages.yml` — weekly, on dispatch, and on a `changelog-refresh` ping. Falls back to the committed snapshot until the vault reader token is in place.
