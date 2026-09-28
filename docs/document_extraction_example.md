# Document Extraction — worked example (spec section 15, Test 8)

`gen/15_simulate_document_extraction.py` actually parses all 10 contract
text files in `contracts/` (real regex extraction against the documents,
not a copy of the ground-truth manifest) and checks each extracted field
against `docs/contracts_ground_truth.csv`.

## Result

**100% field accuracy across all 10 contracts, 8 fields each** (SLA days,
lead time, delivery term, effective date, expiration date, currency,
min OTD%, penalty%).

## Example — Contract C101

```
Contract C101
→ Supplier: Vantage Industrial Gases
→ SLA: delivery within 7 days
→ Lead time: 14 days
→ Delivery term: DDP
→ Effective date: 2025-10-17
→ Expiration date: 2027-10-17
→ Min OTD requirement: 95%
→ Penalty: 2.5% of affected PO value
→ Currency: INR
→ Applicable products: aluminum panels, hydraulic valves
→ Extraction confidence: 100%
```

This is exactly the `sql/21_document_extraction.sql` →
`ONTOLOGY_CORE.CONTRACT` output shape — `EXTRACTION_STATUS` would land as
`AUTO_ACCEPTED` (confidence ≥90) for every contract here.

## An honest caveat about this 100%

These 10 contracts were generated from **one consistent template** (see
`gen/06_generate_contracts.py`), so every contract phrases "SLA" and
"lead time" the same way. A real supplier-contract portfolio has 10
different law firms' drafting styles, inconsistent section numbering, and
genuinely ambiguous phrasing — accuracy in production will be lower than
100%, and some fields (especially penalty terms and renewal clauses) will
land in the `PENDING_REVIEW` tier rather than auto-accepting. That's
exactly why `EXTRACTION_CONFIDENCE` and the same three-tier governance
used for schema mapping (`AUTO_ACCEPTED` / `PENDING_REVIEW` /
`NEEDS_CLARIFICATION`) apply to document extraction too, not just schema
mapping — a clean 100% here is a property of the synthetic dataset, not a
claim about real-world extraction accuracy.

## What the live Cortex version does differently

The regex parser above only works because the contract wording is
predictable. The production path in `sql/21_document_extraction.sql` uses
`SNOWFLAKE.CORTEX.COMPLETE` with a strict JSON-schema prompt (and
`PARSE_DOCUMENT` first, for PDF/scanned contracts) — same output contract,
but robust to phrasing variation a regex would silently miss. Swapping the
regex step for the live Cortex call is the only change needed to move this
from demo to production; `APPLY_CONTRACT_EXTRACTION()` and the confidence
governance tiers stay identical either way.
