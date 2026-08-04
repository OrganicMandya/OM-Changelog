# Changelog

All notable changes to OM-Changelog, newest first. Format loosely follows
[Keep a Changelog](https://keepachangelog.com/). **Every PR adds an entry under `[Unreleased]`.**

## [Unreleased]

### Added
- **Org changelog page — generator + hosting (OM-Infra#86).** `generate.py` aggregates every repo's `CHANGELOG.md` into one plain-language, categorized page (App / Website / Staff tools / Stock & platform) with Shipped / In-testing status badges and auto-linked ticket refs; published to GitHub Pages (`changelog.organicmandya.club`) by `build-pages.yml` — weekly, on dispatch, and on a `changelog-refresh` ping. Falls back to the committed snapshot until the vault reader token is in place.
