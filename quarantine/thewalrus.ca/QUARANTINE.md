# thewalrus.ca — quarantined

**What it actually was:** a **Cloudflare "Just a moment…" interstitial
challenge** page served with HTTP **403**
(`<title>Just a moment...</title> … challenges.cloudflare.com`), not a
robots.txt.

- HTTP status: `403`
- Content-Type: `text/html; charset=UTF-8`
- Body size: 5667 bytes
- Captured: `2026-06-17T20:00:38Z` from `https://thewalrus.ca/robots.txt`
- Classification: **blocked** (non-200)

The challenge page's rotating CSP nonce / tokens produced a false "change"
between the two early runs. Quarantined; the org will re-baseline on the next
clean run.
