# davidsuzuki.org — quarantined

**What it actually was:** an HTTP **403 Forbidden** error page from a Varnish
cache server (`<h1>Error 403 Forbidden</h1> … Varnish cache server`), not a
robots.txt.

- HTTP status: `403`
- Content-Type: `text/html; charset=utf-8`
- Body size: 425 bytes
- Captured: `2026-06-17T19:58:56Z` from `https://davidsuzuki.org/robots.txt`
- Classification: **blocked** (non-200)
- **Persistence: likely-permanent.** Both early fetches returned 403 from the
  Varnish edge — a consistent block (WAF / bot filter), not a one-off. It is a
  plain 403, not a rate limit, so unlike a 429 it does not look like a transient
  throttle; it would only clear if the edge stops blocking our User-Agent/origin.

The rotating Varnish cache-id line in the body produced a false "change" between
the two early runs. Quarantined; the org will re-baseline on the next clean run.
