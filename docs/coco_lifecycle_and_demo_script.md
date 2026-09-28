# CoCo lifecycle guide + demo script (spec sections 23 and 26)

## Honest status of CoCo evidence

This package was authored with Claude, **not** with Snowflake CoCo, and none
of the SQL/Streamlit has been executed against a live Snowflake account.
The spec requires *documented evidence of CoCo usage*; that evidence can
only be produced by you running CoCo in your account. This section gives
you the prompts and a log to capture it — don't claim CoCo built what it
didn't.

## Suggested CoCo prompts per lifecycle stage

| Stage | What to ask CoCo | Artifact to capture |
|---|---|---|
| **Planning** | "Inspect RAW_ERP_A and RAW_ERP_B; list entities, keys, and likely relationships." / "Which columns are ambiguous across the two schemas?" | Screenshot/transcript; compare to `docs/golden_entity_crosswalk.csv` |
| **Development** | "Review sql/14_canonical_metrics.sql for correctness." / "Fix any syntax errors in sql/15 (SEMANTIC VIEW)." / "Review the Streamlit pages for Snowflake-compatibility." | Diff of any CoCo-suggested fixes |
| **Execution** | Have CoCo run scripts 00–21 in order and report row counts per schema | Row-count output, errors and fixes |
| **Testing** | "Run the queries in docs/test_cases.md and report pass/fail." / "Simulate EINDT DATE→VARCHAR and confirm drift is logged." | Pass/fail table for Tests 1–8 |

Expect CoCo to find real problems. Likely first-run issues: `CREATE SEMANTIC VIEW`
syntax details, `CONTRACT_RAW_TEXT` stage-read view in sql/21 (needs
adjustment for line-per-row reads), role grants for the Streamlit app, and
COPY INTO column-order mismatches.

## Evidence log (fill in as you go)

| Date | Stage | Prompt to CoCo | What CoCo did | Result / fix applied |
|---|---|---|---|---|
| | | | | |

## Demo script (spec section 26)

1. **Two ERPs, different columns** — show `RAW_ERP_A.SUPPLIERS` (`LIFNR`) next to `RAW_ERP_B.VENDORS` (`VENDOR_ID`).
2. **AI mapping** — Streamlit *Schema Mapping*: `LIFNR → supplier_id` (99.4%) and `VENDOR_ID → supplier_id` (99.2%).
3. **Canonical ontology** — *Ontology Explorer*, static diagram; then `ONTOLOGY_CORE.SUPPLIER` showing one canonical ID carrying both source IDs.
4. **Same question, three personas** — *Conversational Analytics*: the three OTD phrasings for one supplier; show identical result + Trust panel.
5. **Inject a delay** — insert a `DELAYED` event into `RAW_LOGISTICS.SHIPMENT_EVENTS`; `EXECUTE TASK PROCESS_SHIPMENT_DELAY_EVENTS`; show it on the *Control Tower*.
6. **Traverse the graph** — *Ontology Explorer → Live traversal* from the shipment's supplier, forward.
7. **Impact analysis** — *Impact Analysis* on `SHP-100001`, 4 days; read out affected plant/orders/customers and the ESTIMATED cost.
8. **Contract extraction** — run `CALL APPLY_CONTRACT_EXTRACTION()`; show Contract C101's SLA linked to its supplier.
9. **Trust** — *Data & Metric Lineage*: definition, formula, lineage, weakest-mapping confidence.
10. **Human approval** — *Human Review*: approve or modify `EINDT → promised_delivery_date` (72%).

Positioning line: *An adaptive and governed supply-chain intelligence layer
that lets heterogeneous enterprise systems speak one common business
language, while connecting operational events to their downstream business
and financial impact.*
