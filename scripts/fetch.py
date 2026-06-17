#!/usr/bin/env python3
"""CanRobots fetcher / change detector.

Reads ``orgs.csv`` (the single source of truth), fetches each active
organization's ``robots.txt`` over HTTP, archives the result with full
provenance, and detects content changes against the previously recorded
metadata.

Design (see docs/robots_txt_observatory_build_spec.md, Part A):

* ``data/<domain>/robots.txt`` holds the latest body (overwritten each run);
  git history is the longitudinal archive.
* ``data/<domain>/meta.json`` holds the latest fetch metadata.
* ``snapshots/<domain>/<timestamp>.txt`` is written ONLY when content changed
  (and on the very first/baseline capture, to preserve t0).
* ``logs/changes.csv`` gets one appended row per detected change.
* ``logs/runs.csv`` gets one appended row EVERY run -- this guarantees a commit
  on no-change runs too, which keeps the scheduled workflow alive (GitHub
  auto-disables scheduled workflows after 60 days of repo inactivity).

The script never overwrites a last-good ``robots.txt`` on a fetch error, so a
transient outage cannot destroy good data.

``baseline_may2026/`` is intentionally NOT touched here: it is a labelled
reference set captured by a different method/origin and is excluded from the
change-detection stream by design.

Usage:
    python scripts/fetch.py            # normal run: fetch, archive, log
    python scripts/fetch.py --dry-run  # fetch but write nothing to disk
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

# --- Constants ---------------------------------------------------------------

# Honest, project-identifying User-Agent. This is the final, confirmed string
# (build spec A.6) -- do not change without updating the contact.
USER_AGENT = (
    "CanRobots/1.0 (academic research, University of Ottawa; "
    "pmccurdy@uottawa.ca; +https://github.com/pmcurdy/CanRobots)"
)

REQUEST_TIMEOUT = 20  # seconds, per attempt
MAX_RETRIES = 2       # number of RETRIES after the initial attempt
RETRY_BACKOFF = 3     # seconds; multiplied by attempt number for simple backoff

# Repo layout: this file lives in <repo>/scripts/, so the repo root is its parent.
REPO_ROOT = Path(__file__).resolve().parent.parent
ORGS_CSV = REPO_ROOT / "orgs.csv"
DATA_DIR = REPO_ROOT / "data"
SNAPSHOTS_DIR = REPO_ROOT / "snapshots"
LOGS_DIR = REPO_ROOT / "logs"
CHANGES_CSV = LOGS_DIR / "changes.csv"
RUNS_CSV = LOGS_DIR / "runs.csv"

CHANGES_HEADER = [
    "detected_at_utc", "number", "org_name", "domain",
    "prev_sha256", "new_sha256",
    "prev_last_modified", "new_last_modified",
    "prev_bytes", "new_bytes", "snapshot_path",
]
RUNS_HEADER = [
    "run_at_utc", "orgs_checked", "fetch_errors", "changes_detected",
    "runner_origin",
]


# --- Helpers -----------------------------------------------------------------

def utc_now_iso() -> str:
    """Current UTC time as ISO 8601 with a trailing Z, e.g. 2026-06-17T06:00:12Z."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def safe_timestamp(iso_ts: str) -> str:
    """Filesystem-safe form of an ISO timestamp for use as a snapshot filename.

    Colons are illegal on Windows and awkward everywhere, so 2026-06-17T06:00:12Z
    becomes 2026-06-17T060012Z. Still sorts chronologically and round-trips visibly.
    """
    return iso_ts.replace(":", "")


def safe_domain(domain: str) -> str:
    """Deterministic, filesystem-safe folder name for a domain.

    Domains are already hosts (no scheme/path), so this is mostly defensive:
    keep dots/letters/digits/hyphens, replace anything else with '_'.
    """
    return re.sub(r"[^A-Za-z0-9._-]", "_", domain.strip())


def runner_origin() -> str:
    """A short note on where this capture originated.

    GitHub-hosted runners live in Azure US regions (build spec A.7), so live
    captures come from a fixed US IP. We record that fact in every meta.json
    and runs.csv row; a local run is labelled distinctly.
    """
    if os.environ.get("GITHUB_ACTIONS") == "true":
        return "GitHub-hosted runner (Azure, US region)"
    return "local/manual run"


def sha256_hex(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def read_orgs(path: Path) -> list[dict]:
    """Read orgs.csv, returning only the active rows in file order."""
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = []
        for row in reader:
            active = (row.get("active") or "").strip().lower()
            if active in ("true", "1", "yes"):
                rows.append(row)
    return rows


def load_prev_meta(domain: str) -> dict | None:
    """Load the previous meta.json for a domain, or None if there is no prior run."""
    meta_path = DATA_DIR / safe_domain(domain) / "meta.json"
    if not meta_path.exists():
        return None
    try:
        return json.loads(meta_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def append_csv(path: Path, header: list[str], row: dict, dry_run: bool) -> None:
    """Append a row to a CSV, writing the header first if the file is new."""
    if dry_run:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    is_new = not path.exists()
    with path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=header)
        if is_new:
            writer.writeheader()
        writer.writerow(row)


# --- Fetch -------------------------------------------------------------------

def fetch_one(session: requests.Session, url: str) -> dict:
    """Fetch a single robots.txt with retry/backoff.

    Returns a dict describing the outcome. On success ``error`` is None and
    ``body`` holds the raw bytes. On failure ``error`` is a short string and
    ``body`` is None.
    """
    last_err = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            resp = session.get(url, timeout=REQUEST_TIMEOUT, allow_redirects=True)
            return {
                "body": resp.content,
                "http_status": resp.status_code,
                "final_url": resp.url,
                "redirected": len(resp.history) > 0,
                "last_modified_header": resp.headers.get("Last-Modified"),
                "etag_header": resp.headers.get("ETag"),
                "content_type": resp.headers.get("Content-Type"),
                "error": None,
            }
        except requests.RequestException as exc:
            last_err = exc
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_BACKOFF * (attempt + 1))
    return {
        "body": None,
        "http_status": None,
        "final_url": None,
        "redirected": None,
        "last_modified_header": None,
        "etag_header": None,
        "content_type": None,
        "error": f"{type(last_err).__name__}: {last_err}",
    }


def process_org(session: requests.Session, org: dict, origin: str,
                dry_run: bool) -> dict:
    """Fetch, archive, and change-detect one organization.

    Returns a summary dict used for run-level logging and the change notice.
    """
    number = org.get("number", "")
    org_name = org.get("org_name", "")
    domain = org.get("domain", "")
    robots_url = org.get("robots_url", "")

    fetched_at = utc_now_iso()
    prev_meta = load_prev_meta(domain)
    prev_sha = (prev_meta or {}).get("content_sha256")

    result = fetch_one(session, robots_url)

    domain_dir = DATA_DIR / safe_domain(domain)

    if result["error"] is not None:
        # Fetch failed. Do NOT overwrite the last-good robots.txt. Record the
        # error in meta.json, but carry forward the last-good content fields so
        # change detection survives a transient outage (a null hash here would
        # make the next good fetch look like a fresh baseline).
        meta = {
            "org_name": org_name,
            "domain": domain,
            "robots_url": robots_url,
            "fetched_at_utc": fetched_at,
            "http_status": result["http_status"],
            "final_url": result["final_url"],
            "redirected": result["redirected"],
            "content_sha256": prev_sha,
            "content_bytes": (prev_meta or {}).get("content_bytes"),
            "last_modified_header": (prev_meta or {}).get("last_modified_header"),
            "etag_header": (prev_meta or {}).get("etag_header"),
            "content_type": (prev_meta or {}).get("content_type"),
            "runner_origin": origin,
            "error": result["error"],
        }
        if not dry_run:
            domain_dir.mkdir(parents=True, exist_ok=True)
            (domain_dir / "meta.json").write_text(
                json.dumps(meta, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
        return {
            "domain": domain, "org_name": org_name, "error": True,
            "changed": False, "snapshot_path": None,
        }

    # --- Success path ---
    body = result["body"]
    new_sha = sha256_hex(body)
    new_bytes = len(body)

    meta = {
        "org_name": org_name,
        "domain": domain,
        "robots_url": robots_url,
        "fetched_at_utc": fetched_at,
        "http_status": result["http_status"],
        "final_url": result["final_url"],
        "redirected": result["redirected"],
        "content_sha256": new_sha,
        "content_bytes": new_bytes,
        "last_modified_header": result["last_modified_header"],
        "etag_header": result["etag_header"],
        "content_type": result["content_type"],
        "runner_origin": origin,
        "error": None,
    }

    # Classify: baseline (no prior), unchanged, or changed.
    if prev_sha is None:
        kind = "baseline"
    elif prev_sha == new_sha:
        kind = "unchanged"
    else:
        kind = "changed"

    snapshot_path_rel = None
    # Write a snapshot on baseline (preserve t0) and on every change.
    if kind in ("baseline", "changed"):
        snap_dir = SNAPSHOTS_DIR / safe_domain(domain)
        snap_file = snap_dir / f"{safe_timestamp(fetched_at)}.txt"
        snapshot_path_rel = str(snap_file.relative_to(REPO_ROOT)).replace("\\", "/")
        if not dry_run:
            snap_dir.mkdir(parents=True, exist_ok=True)
            snap_file.write_bytes(body)

    # Write the latest body and metadata.
    if not dry_run:
        domain_dir.mkdir(parents=True, exist_ok=True)
        (domain_dir / "robots.txt").write_bytes(body)
        (domain_dir / "meta.json").write_text(
            json.dumps(meta, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    # A change (not a baseline) gets logged and flagged for notification.
    changed = kind == "changed"
    if changed:
        append_csv(CHANGES_CSV, CHANGES_HEADER, {
            "detected_at_utc": fetched_at,
            "number": number,
            "org_name": org_name,
            "domain": domain,
            "prev_sha256": prev_sha,
            "new_sha256": new_sha,
            "prev_last_modified": (prev_meta or {}).get("last_modified_header"),
            "new_last_modified": result["last_modified_header"],
            "prev_bytes": (prev_meta or {}).get("content_bytes"),
            "new_bytes": new_bytes,
            "snapshot_path": snapshot_path_rel,
        }, dry_run)

    return {
        "domain": domain,
        "org_name": org_name,
        "error": False,
        "changed": changed,
        "kind": kind,
        "prev_bytes": (prev_meta or {}).get("content_bytes"),
        "new_bytes": new_bytes,
        "snapshot_path": snapshot_path_rel,
    }


# --- Notification plumbing ---------------------------------------------------

def write_workflow_outputs(changes: list[dict], run_date: str) -> None:
    """Hand the change set to the GitHub Actions workflow.

    * Writes ``changes_detected`` and ``issue_title`` to ``$GITHUB_OUTPUT`` so
      the workflow can decide whether to open an issue.
    * Writes a Markdown issue body to the path in ``$ISSUE_BODY_FILE`` (the
      workflow points this at a temp file and passes it to ``gh issue create``).

    No-ops gracefully when those env vars are absent (e.g. local runs).
    """
    n = len(changes)

    gh_out = os.environ.get("GITHUB_OUTPUT")
    if gh_out:
        title = f"robots.txt changes detected — {run_date} ({n} org{'s' if n != 1 else ''})"
        with open(gh_out, "a", encoding="utf-8") as f:
            f.write(f"changes_detected={n}\n")
            f.write(f"issue_title={title}\n")

    if n == 0:
        return

    body_file = os.environ.get("ISSUE_BODY_FILE")
    if body_file:
        lines = [
            f"Detected **{n}** robots.txt change(s) in the {run_date} run.",
            "",
            "| Org | Domain | Bytes (old → new) | Snapshot |",
            "|---|---|---|---|",
        ]
        for c in changes:
            old_b = c.get("prev_bytes")
            new_b = c.get("new_bytes")
            snap = c.get("snapshot_path") or ""
            lines.append(
                f"| {c['org_name']} | {c['domain']} | {old_b} → {new_b} | `{snap}` |"
            )
        lines += [
            "",
            "Inspect the diff in the commit for this run, or open the snapshot "
            "file listed above. See `logs/changes.csv` for the full record.",
        ]
        with open(body_file, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")


# --- Main --------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="CanRobots fetcher / change detector")
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Fetch everything but write nothing to disk (for local testing).",
    )
    args = parser.parse_args()

    if not ORGS_CSV.exists():
        print(f"ERROR: {ORGS_CSV} not found.", file=sys.stderr)
        return 1

    orgs = read_orgs(ORGS_CSV)
    origin = runner_origin()
    run_at = utc_now_iso()
    run_date = run_at[:10]

    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})

    print(f"CanRobots run @ {run_at} ({origin}) — {len(orgs)} active org(s)"
          + (" [DRY RUN]" if args.dry_run else ""))

    changes: list[dict] = []
    errors = 0
    for org in orgs:
        summary = process_org(session, org, origin, args.dry_run)
        status = (
            "ERROR" if summary["error"]
            else summary.get("kind", "?").upper()
        )
        print(f"  [{status:9}] {summary['domain']} — {summary['org_name']}")
        if summary["error"]:
            errors += 1
        if summary["changed"]:
            changes.append(summary)

    # ALWAYS append a runs.csv row — even on a no-change run — so every run
    # produces a commit and the scheduled workflow stays alive.
    append_csv(RUNS_CSV, RUNS_HEADER, {
        "run_at_utc": run_at,
        "orgs_checked": len(orgs),
        "fetch_errors": errors,
        "changes_detected": len(changes),
        "runner_origin": origin,
    }, args.dry_run)

    write_workflow_outputs(changes, run_date)

    print(f"Done: {len(orgs)} checked, {errors} error(s), "
          f"{len(changes)} change(s) detected.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
