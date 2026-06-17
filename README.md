# CanRobots — A Longitudinal Archive of Canadian robots.txt Files

CanRobots is an open, automated archive that captures the `robots.txt` files of
~50 Canadian media, environmental (ENGO), and polling organizations on a weekly
schedule. Its purpose is to study **how these organizations adapt their crawler
access rules over time** — in particular, whether and when they add, remove, or
modify directives aimed at AI crawlers (e.g. `GPTBot`, `Google-Extended`,
`CCBot`, `AI2Bot`, `AmazonAdBot`).

The project uses **git scraping**: an automated job fetches each file on a
schedule and commits the results, so the repository's commit history *is* the
longitudinal record. Every change is a dated, inspectable diff.

This is academic research conducted at the **University of Ottawa**. The data is
released openly so other researchers can reuse and cite it.

## What is captured

Once a week, for each organization, the pipeline records:

- the raw `robots.txt` body;
- a SHA-256 hash of the content (the change-detection signal);
- the HTTP status and final URL (after any redirects);
- the server's `Last-Modified` and `ETag` headers, where provided — useful
  because `Last-Modified` reflects when the organization itself last edited the
  file, independent of our polling cadence;
- the capture timestamp and the runner origin;
- a `status` field recording whether the fetch yielded a usable robots.txt
  (`ok`) or a data-quality problem (`fetch_error`, `blocked`,
  `non-robots-response` — see *Response validation* below).

When a file's content changes between runs, the pipeline writes a dated snapshot,
logs the change, and opens a GitHub Issue summarizing it.

## Repository structure

```
orgs.csv                       # the source list — single source of truth
scripts/fetch.py               # the fetcher / change detector
data/<domain>/robots.txt       # latest captured copy (git history holds the timeline)
data/<domain>/meta.json        # latest metadata for that organization
snapshots/<domain>/<ts>.txt    # a dated copy, written only when content changed
logs/changes.csv               # append-only log: one row per detected change
logs/runs.csv                  # append-only log: one row per run
baseline_may2026/              # manually-captured reference baseline (see below)
.github/workflows/scrape.yml   # the scheduled GitHub Action
```

## Methodology notes & limitations

**Capture cadence.** Weekly (Mondays, 06:00 UTC). Free-tier scheduled runs may
start late or, rarely, skip under load; at a weekly cadence this is immaterial.

**Runner origin is United States.** Captures are made by GitHub-hosted runners,
which operate from Microsoft Azure US regions — so the requests originate from a
fixed US IP, not a Canadian one. For `robots.txt` this is almost always
immaterial, but it is recorded in each `meta.json` and noted here as a known
limitation. A Canadian-origin capture would require a self-hosted runner or proxy.

**The May 2026 baseline is a reference, not the t0.** The `baseline_may2026/`
folder contains `robots.txt` copies captured manually on 28–29 May 2026 (the study's
RF-v1 reference frame), imported from source documents. It is preserved for
historical comparison only and is **deliberately excluded from automated change
detection**: because it was captured by a different method and origin, its hashes
are not byte-comparable to live fetches. The **first automated run is the true t0**
for the longitudinal series. See `baseline_may2026/README.md` for details.

**Change detection is content-hash based.** A change is any difference in the
captured bytes. Cosmetic differences (e.g. whitespace, reordered directives) are
therefore treated as changes; qualitative coding of *what kind* of change
occurred is done separately, using the preserved diffs.

**Response validation guards against false changes.** Some sites do not return a
plain robots.txt to an automated client: they serve a bot-challenge page (e.g.
Cloudflare "Just a moment…"), an HTTP error page (e.g. a Varnish 403), or a
JavaScript single-page-app shell. Those bodies often contain rotating tokens, so
naïve byte-hashing would flag a "change" on every run. Before archiving, the
fetcher validates each response and assigns a `status`:

- `ok` — HTTP 200 with a body that looks like a robots.txt (plain-text-ish, and
  containing at least one `User-agent`/`Disallow`/`Allow`/`Sitemap` directive).
- `blocked` — the server did not return HTTP 200 (e.g. a 403 challenge or a 5xx).
- `non-robots-response` — HTTP 200 but the payload is HTML or otherwise not a
  robots.txt (challenge page, error page, SPA shell).
- `fetch_error` — a network/transport failure (timeout, connection error).

Any non-`ok` status is treated as a **soft error**: it is recorded in `meta.json`
and counted in `logs/runs.csv`, but it does **not** overwrite the last-good
`robots.txt` and does **not** flag a change. This keeps transient outages and
bot-protection pages from contaminating the longitudinal record while still
making them visible as data-quality issues.

## Log file schemas

`logs/changes.csv` — append-only, one row per detected change:

`detected_at_utc, number, org_name, domain, prev_sha256, new_sha256,
prev_last_modified, new_last_modified, prev_bytes, new_bytes, snapshot_path`

`logs/runs.csv` — append-only, one row per run (also the keep-alive commit that
prevents the 60-day auto-disable of scheduled workflows):

`run_at_utc, orgs_checked, ok_captures, changes_detected, fetch_errors, blocked,
non_robots_responses, runner_origin`

The three soft-error columns (`fetch_errors`, `blocked`, `non_robots_responses`)
surface data-quality issues per run. Rows recorded before response validation was
introduced leave those columns blank.

## The organization list

The studied organizations are listed in `orgs.csv`, with columns:
`number, source_doc, org_name, domain, robots_url, date_added, active, notes`.
The founding cohort (numbers 1–50) comprises 45 Canadian media/ENGO organizations
and 5 polling firms.

### Adding or retiring an organization

`orgs.csv` is the only file you edit to change the study population:

- **Add:** append a row with the next `number`, set `active=true`, and fill in
  `date_added`. The next run captures its baseline automatically and tracks it
  thereafter. A newly added organization's first capture is a baseline, not a
  change, so it does not trigger a change notification.
- **Retire:** set `active=false`. The pipeline stops fetching it, but all of its
  past snapshots and history are retained.

## Licenses

- **Code:** MIT (see `LICENSE`).
- **Data** (captured files, snapshots, logs): Creative Commons Attribution 4.0
  International (CC-BY-4.0).

