# Portfolio narrative and interview notes

## Short introduction

“I built ChoiceMatch, a local evidence-informed recommendation prototype, starting with rentals. It combines structured eligibility checks with PostgreSQL/pgvector retrieval, source-linked model extraction, and deterministic recommendation rules. The workbench makes risks and missing information visible and lets users exclude candidates with a cited reason.”

## Design story

The inspiration came from an earlier Airbnb data analysis project and the experience of comparing rental information. The goal became a reusable decision-support architecture, with rentals as the implemented vertical—not a claim of a completed general-purpose marketplace.

Fixed topic queries lost details such as overnight calls. Rather than inventing a new structured field for every detail, I kept the original question and added a separate vector route. It contributes once per candidate, avoiding accidental multiplication across themes.

I froze small synthetic experiments before live calls. Adding the original query at 20% did not improve the first experiment's shortlist recall. Candidate-rank fusion improved some scenario metrics but failed the predeclared adoption gate and displaced risk evidence. I kept both results and left the default unchanged.

A source-relevance experiment exposed another boundary: an exact quote can still support a wrong interpretation. I separated local source-text binding from semantic judgment and retained the rejected outputs. A single interruption can refute a claim of uninterrupted service without describing the entire time window; observation coverage and contradiction must not be conflated.

The product then converged on conflict screening and evidence-based comparison. Hard conditions are automatic; uncertain semantic risks remain visible, while users control text-based exclusions with reasons, citations, undo, and stale-context checks.

## Draft project bullets

These are standalone drafts, not edits to a resume or LinkedIn profile:

- Built a rental recommendation prototype with Python, PostgreSQL, and pgvector, combining three-state eligibility checks, hybrid evidence retrieval, source-linked extraction, and deterministic comparison.
- Designed reproducible retrieval ablations and offline weight analysis; retained negative results and used predeclared criteria to avoid promoting a fusion strategy that lost relevant risk evidence.
- Implemented source-hash invalidation, exact citation validation, and reversible user exclusions bound to current requirements and evidence; covered the pipeline with 94 regression tests, including five PostgreSQL integration tests.

Use the third bullet's test count only while it remains current. Do not substitute synthetic recall metrics for production accuracy, business impact, or independently validated quality. No user adoption, latency improvement, revenue, or deployment claim is supported.

## Questions to be ready for

**Why a rule engine after retrieval?** Relevance finds useful positive and negative material. It is not suitability. Hard failures cannot be rescued by high semantic similarity.

**Why exact vector scans?** The local corpus is small; no demonstrated need for approximate indexing. Scaling claims require profiling and larger evaluation data.

**What makes the evaluation weak?** Small assistant-authored synthetic cases, no independent human annotations, observed cases reused only as development diagnostics. Production generalization is unknown.

**What would you do next?** Independently review labels and real source provenance, evaluate an end-to-end held-out set, establish deployment/authentication/resource controls, and validate another domain before claiming generality.
