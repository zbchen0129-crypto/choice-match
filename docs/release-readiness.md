# GitHub release preparation

Publication update on 2026-11-24: project code has been committed to https://github.com/zbchen0129-crypto/choice-match. Public visibility has been verified through GitHub metadata and an unauthenticated HTTPS clone. ChoiceMatch and its public GitHub link have been added to the LinkedIn Projects section, and the local career library has been updated. No hosted app deployment is claimed. The checklist below records the preparation process.

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

No license is selected yet. Choose a license explicitly before representing the code as licensed open source. Preserve data attribution separately from any future code license. The public repository is https://github.com/zbchen0129-crypto/choice-match.

Before the first push, inspect the exact staged file list and staged diff, rerun the file audit, and verify the public package from an isolated copy. The current audit examines Git-visible project files, not a finalized staging area. A clean-machine installation and CI matrix are not yet verified.

## Claims ready to use

Implemented prototype, persistent source-backed retrieval, deterministic filtering, source invalidation, reversible user decisions, recorded evaluations, and tested failure handling.

## Claims not supported

Live inventory, Zillow/Redfin integration, deployed multi-user service, independent human evaluation, production accuracy improvement, proven generality across domains, verified listing quality, or quantified business impact.

## Suggested next milestone

Adapt the published project bullets to the actual target role and resume format, prepare a short demonstration, and choose a code license if desired. Public source publication is complete; hosted deployment remains a separate milestone.

## Initial publication verification

Commit `e8b195b74ad3c97803ac778bcc6ec8f778f42db0` contains the 97 reviewed project files, uploaded through the GitHub connector. An isolated copy passed 89 offline tests; five database tests were skipped as expected. The full configured workspace previously passed all 94. No downloaded data, secrets, virtual environment, career-library files, or adjacent projects were included.
