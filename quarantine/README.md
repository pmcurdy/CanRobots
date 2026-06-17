# quarantine — contaminated captures (NOT part of the dataset)

This folder holds captures that were committed before response validation was
added to `scripts/fetch.py`, and which turned out **not to be real robots.txt
files**. They are kept here for forensic transparency — so the record of what
the early runs actually received is not silently erased — but they are **not
part of the longitudinal dataset** and are **excluded from the pipeline**, just
like `baseline_may2026/`.

Each subfolder contains the original `robots.txt` body and `meta.json` exactly
as captured, plus a `QUARANTINE.md` recording what the response actually was and
why it was quarantined.

## Why these were quarantined

The change detector originally hashed whatever the server returned. Some sites
do not serve a plain robots.txt to an automated client — they return a
bot-challenge page, an HTTP error page, or a JavaScript single-page-app shell.
Those pages often carry rotating tokens, so they produced spurious "changes"
every run and, worse, overwrote (or stood in for) real captures.

`fetch.py` now classifies each response (`ok` / `blocked` /
`non-robots-response` / `fetch_error`) and treats anything non-`ok` as a soft
error that never overwrites good data or flags a change. See the project README,
section *Response validation guards against false changes*.

## What happens next

Because each quarantined org's entry was removed from `data/`, the next
scheduled run re-baselines it from scratch. If the site still blocks the runner,
the run records a soft error (visible in `logs/runs.csv`) instead of archiving
the junk — no contaminated capture re-enters the dataset.

## Contents

| domain | HTTP | what it actually was | persistence |
|---|---|---|---|
| `davidsuzuki.org` | 403 | Varnish "Error 403 Forbidden" page | likely-permanent (consistent edge block) |
| `equiterre.org` | 429 | Too Many Requests, HTML page | **possibly-transient** (rate limit, likely from today's test runs) |
| `thetyee.ca` | 403 | Cloudflare "Just a moment…" challenge | likely-permanent (bot challenge) |
| `thewalrus.ca` | 403 | Cloudflare "Just a moment…" challenge | likely-permanent (bot challenge) |
| `tvo.org` | 200 | React single-page-app shell (not robots.txt) | **possibly-transient** (run-1 returned the real file) |

"Persistence" is a first-read judgement, not a verdict: 403 Cloudflare challenges
and steady edge 403s tend to recur, whereas a 429 (rate limit) or an
intermittent SPA/timeout often clears on the normal cadence. Don't mislabel
rate-limiting as blocking — let the re-baseline decide.

> Note: `tvo.org`'s genuine baseline robots.txt *was* captured on the first run
> and is preserved at `snapshots/tvo.org/2026-06-17T191848Z.txt`; only the later
> SPA-shell capture was quarantined.
