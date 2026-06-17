# tvo.org — quarantined

**What it actually was:** the site's **React single-page-app shell** served with
HTTP **200** (`<!doctype html> … You need to enable JavaScript to run this
app. … webpackJsonptvo-cad`), not a robots.txt.

- HTTP status: `200`
- Content-Type: `text/html`
- Body size: 5623 bytes
- Captured: `2026-06-17T20:00:40Z` from `https://www.tvo.org:443/robots.txt`
- Classification: **non-robots-response** (HTML body at HTTP 200)
- **Persistence: possibly-transient.** This is HTTP 200, not a block or a rate
  limit — and the *first* fetch the same day returned the genuine robots.txt
  (608 bytes). So the SPA shell is intermittent, not a steady state: likely a
  deploy/cache moment where the SPA catch-all answered the robots.txt path. A
  re-baseline may well capture the real file again.

This is the *second* capture. The **first** run captured tvo.org's genuine
robots.txt (608 bytes, `User-agent: *` plus a sitemap list); that real baseline
is preserved at `snapshots/tvo.org/2026-06-17T191848Z.txt` and was **not**
quarantined. The spurious SPA-shell capture is what produced the false 608→5623
byte "change". Quarantined; the org will re-baseline on the next clean run.
