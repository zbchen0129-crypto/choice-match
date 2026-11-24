# Architecture and engineering boundaries

ChoiceMatch separates eligibility, retrieval relevance, evidence direction, and user decisions. A highly relevant negative review should be retrieved; it should not increase the recommendation's suitability score.

## Data and eligibility

Candidate snapshots preserve the application contract. Normalized rental fields support SQL filtering. PostgreSQL stores sources, chunks, evidence, import audit records, and query embeddings. Importing changed source content invalidates dependent chunks, vectors, and evidence transactionally. SQL and application eligibility must agree before model processing.

Hard conditions have pass/fail/unknown states. Monthly cost uses a known lower bound: missing fees cannot establish affordability, but an already excessive lower bound establishes failure. Unknowns remain candidates needing verification.

## Retrieval

Each preference theme retrieves keyword and semantic matches, combined by reciprocal rank fusion. A candidate's strongest chunk per theme contributes to a weighted mean. The original question is embedded separately and contributes once at candidate level, rather than being counted once per theme.

The current default uses topic coverage first, then an experimental 80/20 normalized topic/original-query score, then a stable ID tie-break. The original-query contribution is disabled for empty queries. These weights are not calibrated or proven optimal. Candidate-rank fusion and five fixed weight choices remain experiments.

Coverage currently counts retrieved themes, not independently verified semantic coverage. This is a known limitation. Vector retrieval uses exact scans at the current small scale, not an approximate index. At most five candidates are deeply analyzed; truncated results do not represent an exhaustive property search.

## Extraction and recommendation

The extractor receives selected full sources, confirmed requirements, and the original text. Local validation requires known source IDs and exact, nonempty quotes. Evidence retains support/risk direction, source dates, and conditions. Model output with valid syntax and quotes can still be semantically wrong.

For each preference, deterministic scoring adds its weight if support exists and subtracts it if risk exists. Each direction counts at most once per theme. Mixed evidence and no evidence can both net to zero; separate statuses and summaries distinguish them. The explanation model may cite only the allowed candidate/topic evidence and cannot change the deterministic order.

## User decisions

The workbench offers a user-controlled exclusion with a source quote and reason. `/api/review-exclusion` rereads current sources, validates citations and the requirements/source fingerprint, and returns a decision explicitly marked as a user choice. It does not authenticate an independent reviewer or certify truth.

Decisions are session-local result overlays. They do not mutate the database or automatically retrain a model. Undo restores the baseline result and its explanations. Changes to requirements, source content, or original text invalidate old decisions. New analysis and refresh clear the overlay; exported JSON includes the decision trace.

## Resource control and current limits

Live evaluations run sequentially with declared call, context, response, memory, and time limits. Model responses have a 4 MiB read cap. These protections are not a production-wide concurrency governor: the normal development HTTP server is threaded and deployment requires further capacity and security design.

The standalone source-relevance classifier remains experimental and is not wired into automatic exclusion. The no-key preview uses static fixtures and no database/model calls. No live listing ingestion or cross-domain validation is claimed.
