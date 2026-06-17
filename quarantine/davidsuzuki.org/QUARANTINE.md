# davidsuzuki.org — quarantined

**What it actually was:** an HTTP **403 Forbidden** error page from a Varnish
cache server (`<h1>Error 403 Forbidden</h1> … Varnish cache server`), not a
robots.txt.

- HTTP status: `403`
- Content-Type: `text/html; charset=utf-8`
- Body size: 425 bytes
- Captured: `2026-06-17T19:58:56Z` from `https://davidsuzuki.org/robots.txt`
- Classification: **blocked** (non-200)

The rotating Varnish cache-id line in the body produced a false "change" between
the two early runs. Quarantined; the org will re-baseline on the next clean run.
