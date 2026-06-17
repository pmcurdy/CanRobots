# equiterre.org — quarantined

**What it actually was:** an HTTP **429 Too Many Requests** response whose body
was the site's HTML page (Astro-rendered, `<!DOCTYPE html><html lang="en" …`),
not a robots.txt.

- HTTP status: `429`
- Content-Type: `text/html; charset=utf-8`
- Body size: 33793 bytes
- Captured: `2026-06-17T20:00:44Z` from `https://www.equiterre.org/robots.txt`
- Classification: **blocked** (non-200)

Rotating inline tokens in the HTML produced a false "change" between the two
early runs. Quarantined; the org will re-baseline on the next clean run.
