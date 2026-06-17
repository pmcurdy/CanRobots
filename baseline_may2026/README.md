# baseline_may2026 — Reference frame (RF-v1)

Manually-captured `robots.txt` copies for the 50 organizations in the CanRobots
study, imported from two source documents:

- `canadian_robots_txt_files.docx` — 45 orgs, recorded **2026-05-28**
- `Polling_Firms-robot-txt_files.docx` — 5 polling firms, recorded **2026-05-29**

## What this is — and is NOT

This folder is a **historical reference baseline**, preserved for comparison. It is
**NOT** part of the automated change-detection stream and must not be used as the
pipeline's t0.

Two reasons:

1. **Different capture method/origin.** These were captured manually (origin
   unknown / not a US GitHub runner) and round-tripped through Word, so whitespace
   and line endings may not be byte-identical to a live HTTP fetch.
2. **Hashes are not comparable.** Because of (1), the `content_sha256` values here
   will generally NOT match a clean live capture even when the underlying
   robots.txt is unchanged. Comparing them would flag false "changes."

The **first scheduled Action run is the true t0** for longitudinal change detection.
Use this folder only for qualitative "what did it look like in May 2026" comparison.

## Layout
```
baseline_may2026/
  <domain>/
    robots.txt     # the imported body, verbatim
    meta.json      # provenance: source_doc, captured_date, method=manual, origin=unknown, sha256, bytes
  manifest.csv     # one row per org: number, source_doc, org_name, domain, lines, bytes, first_line
```

All 50 organizations have a non-empty body. Source of truth for the org list and
the URLs to fetch live remains `orgs.csv` in the repo root.
