## What & why
The public changelog at https://changelog.organicmandya.club/ only had **9 entries (23 Jul – 6 Aug)**, so it read like the product only started shipping in late July — and it was stale (nothing since 6 Aug, despite a lot shipping since).

This **backfills the history to 16 July** and **catches it up to today (11 Aug)** — 12 new curated, plain-language, customer/leadership-facing highlights. The page now spans **16 Jul → 11 Aug**.

## What was added (12 entries → 21 total)
**Earlier (the gap before 23 Jul):**
- Combo/bundle products buyable again · hourly self-healing stock · **stop oversells at checkout** · spoken new-order alerts on the Store Dashboard · the org-wide **Ticket Dashboard**

**Catch-up (after 6 Aug):**
- Login stored more securely · sensitive data removed from app logs · staff dashboards refresh every 15 min · **PayU as a second way to pay (in testing)** · a leaner/better-maintained app · dashboards that self-check after every update · **instant wallet-history refresh**

Every entry is sourced from a real merged PR/issue (linked via the REF chip), written in the site's non-technical voice, and de-duplicated against the existing 9.

## A note on June
OM's org repos were transferred and put under governance from **mid-July**, so genuine *customer-facing shipped* history begins there. The **June–early-July** period was foundational — repo transfers, testing/CI, safe-deploy pipelines — not user-visible shipping, so I didn't invent entries for it rather than pad the timeline. If you want a single "foundations" summary entry to represent that groundwork, say the word and I'll add it.

## Verification
- `python generate.py` builds clean (25.6 KB); date range confirmed **2026-07-16 → 2026-08-11**, 21 entries.
- `public/index.html` regenerated (the deploy workflow re-renders identically on merge).
- Docs are accurate as-is: the README + the CHANGELOG's later entry already state the page renders the **curated `content.json`, not** repo CHANGELOGs — so nothing to correct there.

No issue to close — this is a content backfill from a direct request. On merge, `deploy.yml` renders + ships it to Cloudflare Pages automatically.
