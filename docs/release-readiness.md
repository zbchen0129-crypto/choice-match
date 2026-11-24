# GitHub release preparation

Status on 2026-11-24: local portfolio documentation prepared; no remote repository created, no push, no deployment, and no changes to a live resume or LinkedIn profile.

## Completed locally

- English README with a no-key quick start, screenshot, architecture overview, implemented scope, negative experiments, and limits.
- English setup and three-minute demonstration guide.
- Interview narrative and fact-based draft project bullets.
- Existing Chinese development history preserved separately; detailed experiment records retained.
- `.env`, `.venv`, `data/private`, SQLite files, `.DS_Store`, and logs ignored.
- Read-only bounded Git-visible file audit (`python3 scripts/check_release.py`). It never opens `.env`; it checks path exclusions, file/total-size budgets, and common credential patterns. A clean heuristic result is not a complete security guarantee.
- No-key demo and HTTP GET preview checked. 94 tests passed with PostgreSQL enabled, including five integration tests; no paid model calls. Test peak RSS was 52.98 MiB.

## Publication boundary

This directory currently lives inside a shared workspace containing other projects. Publish only ChoiceMatch from a dedicated repository or an explicitly isolated export. Do not stage, push, or copy the entire parent workspace. Do not include ignored files, local database contents, downloaded historical datasets, environment files, or virtual environments.

No license is selected yet. Choose a license explicitly before representing the code as licensed open source. Preserve data attribution separately from any future code license. The repository name/account and public visibility must be settled before publication; no remote destination is assumed here.

Before the first push, inspect the exact staged file list and staged diff, rerun the file audit, and verify the public package from an isolated copy. The current audit examines Git-visible project files, not a finalized staging area. A clean-machine installation and CI matrix are not yet verified.

## Claims ready to use

Implemented prototype, persistent source-backed retrieval, deterministic filtering, source invalidation, reversible user decisions, recorded evaluations, and tested failure handling.

## Claims not supported

Live inventory, Zillow/Redfin integration, deployed multi-user service, independent human evaluation, production accuracy improvement, proven generality across domains, verified listing quality, or quantified business impact.

## Suggested next milestone

Create an isolated publication candidate containing only the reviewed project files, verify the no-key walkthrough there, settle the license and remote visibility, then publish. After a stable repository URL exists, adapt the draft project bullets to the actual target role and resume format.
