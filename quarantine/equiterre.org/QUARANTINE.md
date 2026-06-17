# equiterre.org — quarantined

**What it actually was:** an HTTP **429 Too Many Requests** response whose body
was the site's HTML page (Astro-rendered, `<!DOCTYPE html><html lang="en" …`),
not a robots.txt.

- HTTP status: `429`
- Content-Type: `text/html; charset=utf-8`
- Body size: 33793 bytes
- Captured: `2026-06-17T20:00:44Z` from `https://www.equiterre.org/robots.txt`
- Classification: **blocked** (non-200)
- **Persistence: possibly-transient.** 429 = *Too Many Requests*, i.e. rate
  limiting — very likely amplified by today's repeated manual test runs against
  this host rather than a deliberate, durable block. This should NOT be read as
  "equiterre blocks crawlers"; it must be retried on the normal weekly cadence
  before drawing any conclusion. Caveat: the body returned was the site's full
  HTML page, so even without the 429 this URL may not serve a clean robots.txt —
  watch what the re-baseline captures.

Rotating inline tokens in the HTML produced a false "change" between the two
early runs. Quarantined; the org will re-baseline on the next clean run.
