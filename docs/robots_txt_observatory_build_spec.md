# robots.txt Observatory — Build Spec & Setup Guide

A free, low-maintenance **git-scraping** pipeline that captures the `robots.txt` file of ~50 organizations on a schedule, archives every version with full provenance, detects changes, and notifies you — while doubling as an open dataset other researchers can cite.

This document has two halves:

- **Part A — Build Spec for Claude Code.** Hand this to Claude Code to scaffold the repository. It specifies *what* to build; Claude Code writes the actual code.
- **Part B — GitHub Setup (your steps).** What you do in your GitHub account to get it live.

At the end: **decisions to confirm** and **what I need from you** to finalize.

---

## The core idea (why this works)

You don't need to design a timestamping scheme. **Git already timestamps every commit.** The Action fetches all the files on a schedule and commits the results; the repo's commit history *becomes* the longitudinal archive. Every change is a diff with a date attached, replayable forever. This is the standard "git scraping" pattern. For public repos it runs on free GitHub-hosted Actions minutes, so the running cost is **$0**.

The research payoff: you can later ask not just *"did this org change its robots.txt?"* but *"when, and what kind of change — did they add a disallow for `GPTBot`, `Google-Extended`, `CCBot`?"* The git diff preserves the exact text, so the **access/basis** coding you do for *Seen or Silent* can be applied retrospectively to any captured change.

---

# Part A — Build Spec for Claude Code

> **Instruction to Claude Code:** Build the repository described below. Use Python 3.11+ with a minimal dependency footprint (`requests` only, plus standard library). Write clean, well-commented code and a thorough README. Do not invent extra features beyond this spec without flagging them.

## A.1 Repository layout

```
robots-txt-observatory/
├── orgs.csv                      # the source list — single source of truth
├── scripts/
│   └── fetch.py                  # the fetcher / change detector
├── data/
│   └── <domain>/
│       ├── robots.txt            # latest copy, overwritten each run
│       └── meta.json             # latest metadata for this org
├── snapshots/
│   └── <domain>/
│       └── <UTC-timestamp>.txt   # written ONLY when content changed
├── logs/
│   ├── changes.csv               # append-only: one row per detected change
│   └── runs.csv                  # append-only: one row per run (keep-alive)
├── .github/
│   └── workflows/
│       └── scrape.yml            # the scheduled Action
├── requirements.txt              # pinned deps
├── README.md                     # methodology, origin caveat, how to add orgs
└── LICENSE                       # see A.8
```

Use a filesystem-safe version of the domain for folder names (e.g. replace `.` is fine; just strip scheme/path). Keep it deterministic so the same org always maps to the same folder.

## A.2 `orgs.csv` — the source of truth

This is the **only** file you edit to add/remove organizations. Schema:

| column | meaning |
|---|---|
| `number` | stable integer key (continuous 1–50, matches the master spreadsheet) |
| `source_doc` | `Canadian` or `Polling` (provenance of where the org entered the study) |
| `org_name` | display name |
| `domain` | registrable host (e.g. `thenarwhal.ca`) — used for the folder name |
| `robots_url` | exact URL to fetch (e.g. `https://thenarwhal.ca/robots.txt`) — **fetch this verbatim, www. and all** |
| `date_added` | ISO date the row was added to the study |
| `active` | `true`/`false` — set `false` to retire an org without deleting its history |
| `notes` | free text |

The fetcher reads `orgs.csv`, skips rows where `active` is false, and loops over the rest. **Adding an organization = append one row and commit.** That is the entire extensibility mechanism.

## A.3 `fetch.py` — required behavior

For **each active org**, the script must:

1. **Fetch** `robots_url` with:
   - a custom, honest `User-Agent` identifying the project and a contact (see A.6);
   - a sane timeout (e.g. 20s) and a small retry-with-backoff (e.g. 2 retries) for transient failures;
   - redirects followed, but the **final URL recorded**.
2. **Record metadata** for the fetch (write to `data/<domain>/meta.json`, overwriting):
   - `org_name`, `domain`, `robots_url`
   - `fetched_at_utc` (ISO 8601, e.g. `2026-06-17T06:00:12Z`)
   - `http_status`
   - `final_url` (after redirects) and `redirected` (bool)
   - `content_sha256` (hash of the raw response body)
   - `content_bytes` (length)
   - `last_modified_header` (the server's `Last-Modified`, if present — **valuable: it's the org's own edit timestamp**)
   - `etag_header` (if present)
   - `content_type`
   - `runner_origin` (hardcode/derive a note that this is a GitHub-hosted US runner — see A.7)
   - `error` (null, or a short error string if the fetch failed)
3. **Write the body** to `data/<domain>/robots.txt` (overwrite). On fetch error, do **not** overwrite the last-good copy — record the error in `meta.json` only, so a transient outage never destroys good data.
4. **Detect change** by comparing the new `content_sha256` against the previous `meta.json`'s hash:
   - **No previous meta** → this is the **baseline** capture. Not a "change." (Still write a snapshot so t0 is preserved.)
   - **Hash identical** → no change. Do nothing further for this org.
   - **Hash differs** → a **change**:
     - write `snapshots/<domain>/<fetched_at_utc>.txt` with the new body;
     - append a row to `logs/changes.csv` (schema in A.4);
     - flag for notification (A.5).
5. **Always** append a row to `logs/runs.csv` (schema in A.4) — even on a no-change run. This guarantees a commit every run, which keeps the scheduled workflow alive (see A.7 gotcha).

The script should be idempotent and safe to run locally for testing (a `--dry-run` flag that fetches but writes nothing is a nice-to-have).

## A.4 Log schemas

`logs/changes.csv` (append-only):

| column |
|---|
| `detected_at_utc`, `number`, `org_name`, `domain`, `prev_sha256`, `new_sha256`, `prev_last_modified`, `new_last_modified`, `prev_bytes`, `new_bytes`, `snapshot_path` |

`logs/runs.csv` (append-only — the keep-alive + audit trail):

| column |
|---|
| `run_at_utc`, `orgs_checked`, `fetch_errors`, `changes_detected`, `runner_origin` |

## A.5 Notifications — GitHub Issues (free, emails you)

When changes are detected in a run, the workflow opens (or comments on) a **GitHub Issue** summarizing them. No external service needed — GitHub emails you through normal repo notifications.

- Preferred: **one issue per run** when there are changes, titled e.g. `robots.txt changes detected — 2026-06-17 (3 orgs)`, body listing each changed org with old→new byte counts and a link to the diff/snapshot. Simpler to manage than one-issue-per-org.
- Implement via the GitHub CLI (`gh`, preinstalled on runners) or the REST API using the built-in `GITHUB_TOKEN`. No secrets to configure.

## A.6 Fetch etiquette / honest identification

Fetching `robots.txt` is always permitted — it's the one file every crawler is *expected* to read — so there's no access question here. But identify the bot honestly (good form, and fitting given the subject):

```
User-Agent: CanRobots/1.0 (academic research, University of Ottawa; pmccurdy@uottawa.ca; +https://github.com/pmcurdy/CanRobots)
```

This is the final, confirmed contact string — use it verbatim. Sequential fetches of ~50 small files is trivial load; no special rate limiting needed beyond the per-request timeout.

## A.7 Known gotchas to handle in the build

- **Workflow permissions.** The Action commits back to the repo and opens issues, so it needs **read/write** permissions and issue access. The workflow YAML must declare `permissions: { contents: write, issues: write }`, and the repo setting must also allow it (Part B, step 5).
- **Auto-disable after 60 days.** GitHub disables *scheduled* workflows if the repo has no activity for 60 days. The `runs.csv` keep-alive commit every run prevents this — make sure even a no-change run commits something.
- **Runner origin is US.** GitHub-hosted runners are in Azure US regions, so captures come from a fixed US IP. For `robots.txt` this is almost always immaterial, but **record it** in metadata and **state it in the README** as a known limitation. (If you later want a Canadian origin, that's a self-hosted runner or a proxy — out of scope for v1.)
- **Cron cadence.** Weekly is clean: `0 6 * * 1` (Mondays 06:00 UTC). True "every 10 days" isn't expressible in cron (it's calendar-based); if you insist on ~10 days, approximate with specific days-of-month or gate a daily run with a counter. **Recommend weekly.** Also: free-tier scheduled runs can start late or rarely skip under load — fine at weekly cadence.
- **First run = baseline, not change.** Don't fire change notifications on the very first capture of an org.
- **Don't clobber good data on error.** Covered in A.3 step 3.

## A.8 Licensing & openness (the "available to other researchers" bonus)

- **Code:** MIT (permissive, standard).
- **Data:** CC-BY 4.0 (lets others reuse the captures with attribution — the norm for open research data).
- Put both in `LICENSE` / note the data license in the README.
- **Citability:** connect the repo to **Zenodo** (free, integrates with GitHub) so that each GitHub *Release* mints a **DOI**. That turns your archive into something formally citable in papers. (Setup is a Part B optional step.)

## A.9 README must document

The research purpose; the methodology (cadence, what's captured, change detection); the **US-runner-origin caveat**; how the data is structured; **how to add an org** (edit `orgs.csv`); the licenses; and a "how to cite" line. This README *is* part of the scholarly record — write it accordingly.

## A.10 `.github/workflows/scrape.yml` — required shape

- **Triggers:** `schedule` (weekly cron above) **and** `workflow_dispatch` (so you can run it manually on demand — essential for testing).
- **Steps:** checkout → set up Python 3.11 → `pip install -r requirements.txt` → run `scripts/fetch.py` → if changes, open/update the issue → commit & push all changed files (`data/`, `snapshots/`, `logs/`) with a message like `chore: scrape <date> (<n> changes)`.
- **Permissions block** as in A.7.

---

# Part B — GitHub Setup (your steps)

You can do all of this in a free GitHub account. Estimated time: ~30–45 min the first time, mostly clicking.

### Step 1 — Account
Use your existing GitHub account (the one behind your `pmcurdy` remote) or create a free one at github.com. No paid plan needed.

### Step 2 — Create the repository
- Click **+ → New repository**.
- **Name:** e.g. `robots-txt-observatory` (rename to taste).
- **Visibility:** **Public** ← required for free unlimited Actions minutes *and* for the open-data bonus.
- Tick **Add a README** and **Add a license** (pick MIT now; you'll add the data license by hand).
- **Create repository.**

### Step 3 — Get the code in (two routes)

**Route A — Claude Code (recommended).**
1. On the repo page: **Code → HTTPS → copy the URL.**
2. Locally: `git clone <that-url>` and `cd` into the folder.
3. Run **Claude Code** in that folder and give it **Part A of this document** plus the `orgs.csv` (below). Let it scaffold `scripts/fetch.py`, `.github/workflows/scrape.yml`, `requirements.txt`, the folders, and the README.
4. Review the output (this is your usual divide: Claude Code implements, you/Claude-chat review).
5. `git add -A && git commit -m "Initial scaffold" && git push`.

**Route B — Web upload (fallback, no local git).** Use **Add file → Upload files** / **Create new file** in the GitHub web UI to paste in each file Claude Code generates. Slower, but works entirely in the browser.

### Step 4 — Add `orgs.csv`
Export the master spreadsheet's **Simple (4 columns)** sheet to CSV and reshape to the A.2 schema, or just have me generate `orgs.csv` ready-to-commit (I have all 50 rows). Commit it to the repo root.

### Step 5 — Enable Actions & set write permissions  ⚠️ easy to miss
- **Settings → Actions → General.**
- Under **Workflow permissions**, select **Read and write permissions** and tick **Allow GitHub Actions to create and approve pull requests** isn't needed, but **issue/content write is** — the "Read and write" radio covers it.
- Save. (Without this, the Action can't commit results or open issues.)

### Step 6 — Test before trusting the schedule
- **Actions** tab → select the **scrape** workflow → **Run workflow** (this is the `workflow_dispatch` trigger).
- Watch it run. Confirm: `data/` populated for all 50, `meta.json` looks right, `logs/runs.csv` got a row, and (on first run) baseline snapshots written.
- Fix anything, re-run, until a clean pass.

### Step 7 — Turn on notifications
- Click **Watch → All Activity** (or at least **Issues**) on the repo so GitHub emails you when the Action opens a change issue.
- Optionally verify your GitHub email notification settings are on.

### Step 8 — Confirm the schedule
- The weekly cron runs automatically once committed. The `runs.csv` keep-alive prevents the 60-day auto-disable. Check back after the first scheduled Monday to confirm it fired.

### Step 9 (optional) — Mint a DOI via Zenodo
- Log in to **zenodo.org** with GitHub, flip the toggle **on** for this repo, then cut a **Release** in GitHub. Zenodo archives that release and issues a citable **DOI**. Re-release periodically (e.g. each paper) to snapshot the dataset.

### Adding organizations later (the whole workflow)
Edit `orgs.csv` → append a row (`active=true`, fill `date_added`) → commit. The next run picks it up and captures its baseline automatically. To retire one without losing history, set `active=false`.

---

## Decisions I've defaulted (change any of these)

- **Cadence:** weekly (Mon 06:00 UTC), not 10-day — cron-clean and simpler.
- **Visibility:** public — free minutes + open data.
- **Storage model:** latest copy overwritten + snapshot-only-on-change (keeps the repo small; git holds the full timeline).
- **Notifications:** GitHub Issues (no external service).
- **Code MIT / Data CC-BY 4.0**, optional Zenodo DOI.
- **Origin:** US GitHub runner, documented as a limitation (no Canadian-origin capture in v1).

## May baseline — stored as a separate reference, NOT as t0
The full `robots.txt` bodies from your two `.docx` files (the ~May 28–29 2026 RF-v1 capture) are provided in a `baseline_may2026/` folder (see `CanRobots_baseline_may2026.zip`). **Commit this folder as-is**, but treat it as a historical reference only — it is deliberately kept out of the change-detection stream because it was captured by a different method/origin and round-tripped through Word, so its hashes will not match clean live fetches. The **first scheduled Action run is the true t0.** Claude Code should NOT wire `baseline_may2026/` into `fetch.py`'s hash comparison; it lives alongside the pipeline as a labelled reference set (its own README explains this).

## What I need from you to finalize
1. **GitHub username** + **preferred repo name** (so I can fill in the User-Agent and README URLs).
2. **Contact** for the bot User-Agent (an email or a URL is fine).
3. **Confirm:** weekly cadence? public repo? seed the May baseline as t0?
4. Anything else you want captured per fetch beyond the A.3 metadata list.
