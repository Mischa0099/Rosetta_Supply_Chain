# Phase 1 Synthetic Data — Adaptive Supply Chain Intelligence Platform

This package contains the synthetic source data for **Phase 1 (Foundation)**:
two heterogeneous ERP schemas, a logistics/TMS domain, IoT operational
events, and supplier contracts — all internally consistent so the later
schema-mapping, ontology, and impact-analysis work has real relationships to
resolve.

## Folder structure

```
csv/erp_a/        ERP A — SAP-like schema (LIFNR, MATNR, WERKS, EINDT, ...)
csv/erp_b/        ERP B — Oracle/custom-like schema (vendor_id, sku, location_code, promise_dt, ...)
csv/logistics/    Carriers, shipments, shipment_events (spans both ERPs)
csv/iot/          location_updates, temperature_readings, warehouse_events, shipment_status_events
contracts/        10 synthetic supplier contracts (.txt) for document extraction
docs/              Ground-truth answer keys (NOT source data — see below)
sql/               Snowflake DDL + COPY INTO scripts, one file per domain, in run order
```

## Design principles baked into the data

**1. Genuine schema heterogeneity.** ERP A uses real SAP-style field names
(`LIFNR`, `MATNR`, `WERKS`, `EINDT`, `EBELN`/`EBELP`). ERP B uses a
different, Oracle/custom-style convention (`VENDOR_ID`, `SKU`,
`LOCATION_CODE`, `PROMISE_DT`, `PO_NUMBER`/`LINE_NUM`) for the same
concepts. This is what section 7 (AI-Powered Schema Mapping) needs to
resolve.

**2. Deliberate entity overlap for mapping/resolution testing.** Behind the
scenes, 18 "real" suppliers, 40 "real" products, and 6 "real" plants exist.
- **12 suppliers / 26 products** appear in **both** ERPs under different IDs
  (and sometimes slightly different names — `Ltd` vs `Ltd.`, `Corp` vs
  `Corporation` — realistic drift, not identical strings).
- **3 suppliers / 7 products** exist **only** in ERP A, and **3 / 7** only
  in ERP B.
- All 6 plants are shared (a company's own plants are visible in every
  internal system), but under different codes (`WERKS` vs `LOCATION_CODE`).

This directly supports **Test 1** ("SAP LIFNR and Custom ERP VENDOR_NO
should map to the same canonical Supplier ID") and gives the mapping
component real precision/recall to measure, not a trivial 1:1 match.

**3. Data quality edge cases, on purpose:**
- ~2% of PO/SO line items have a **missing promised delivery date**
  (`EINDT` / `PROMISE_DT` blank) — for **Test 6** (missing data must not
  silently produce a wrong OTD).
- ~5% of suppliers/vendors are flagged blocked/on-hold (`SPERR='X'` /
  `STATUS='HOLD'`).
- IoT `shipment_status_events` are captured **independently** of
  TMS-reported `shipment_events` and can disagree — a reconciliation case,
  not a bug.
- ~6% of temperature readings are flagged `EXCURSION_FLAG=TRUE`.

**4. Timezone traps, on purpose.** Shipment events are stored as
**local timestamp + IANA timezone**, not pre-converted to UTC — exactly the
raw condition section 9 (Time-Zone Normalization) is meant to fix. Origin
and destination timezones frequently differ (e.g. a Pune-origin,
New York–destination shipment), which is what **Test 3** exercises.

**5. One featured delayed shipment for the impact-analysis demo.** See
`docs/golden_entity_crosswalk.csv` and the console output of
`04_generate_logistics.py` — a specific `SHIPMENT_ID` with status
`DELAYED`/`IN_TRANSIT` is called out, playing the role of "Shipment S123"
in section 17/26 of the spec. Use it for the Phase 4 impact-analysis walk-through.

**6. Contracts are prose, not key-value pairs.** The 10 synthetic supplier
contracts are written as real contract language (numbered clauses, legal
phrasing) so document extraction (section 15, Test 8) has to actually parse
sentences for SLA days, lead time, delivery terms, effective/expiration
dates — not just split on a label.

## `docs/` — ground truth, not source data

- `golden_entity_crosswalk.csv` — maps every master supplier/product/plant
  to its ERP A ID and ERP B ID. This is your **answer key** for scoring the
  AI schema-mapping / entity-resolution component. Do not feed it into the
  mapping model — use it only to evaluate output.
- `contracts_ground_truth.csv` — the true SLA/lead-time/delivery-term/date
  values used to generate each contract, for scoring document extraction.

## Loading into Snowflake

Run the SQL scripts in `sql/` in numeric order (`00` → `06`). Each script:
1. Creates its schema under database `SUPPLY_CHAIN_PLATFORM`
2. Creates a file format + internal stage
3. Creates tables with column comments explaining the SAP/Oracle-style
   field semantics (useful context for the AI schema-mapping step later)
4. `COPY INTO` from the stage

You'll need to `PUT` the local CSV/text files to each stage first (via
SnowSQL or drag-and-drop in Snowsight) — see `sql/00_setup_and_run_order.sql`
for the exact commands and file targets.

## Canonical ontology (Phase 1, items 3-4)

On top of the raw source data, `csv/ontology_core/`, `csv/ontology_goods/`,
`csv/ontology_manufacturing/`, `csv/ontology_services/`, and
`csv/ontology_graph/` contain the **canonical ontology**: ERP A + ERP B
resolved into one set of business entities, plus two adaptive extensions
and a unified dependency graph. Full detail in `docs/ontology_diagram.md`.

**Core entities** (`ontology_core/`): `supplier`, `product`, `plant`,
`customer`, `location`, `order` (+ `order_line`, unifying PO and SO),
`contract`, `transaction`. Suppliers/products/plants are **deduplicated**
across ERP A and ERP B using the same crosswalk described above — e.g. SAP
`LIFNR 0000100213` and Oracle-style `VENDOR_ID VEND-4007` both resolve to
`CANONICAL_SUPPLIER_ID CS-SUP-001`. This is exactly what Test 1 checks.

**Adaptive extensions**, each in its own schema, referencing core entities
by canonical ID only (no core table is modified):
- `ontology_goods/` — Warehouse + Inventory, unifying ERP A `LABST` and ERP B `QTY_ON_HAND`
- `ontology_manufacturing/` — Production Line, Bill of Materials, Production Order (net-new synthetic data; this is the "preferably manufacturing" industry module)
- `ontology_services/` — Service Provider, Service, Service Order, Milestone (small standalone dataset proving the ontology also hosts a services-based business)

**Dependency graph** (`ontology_graph/relationship_edges.csv`, ~3,400
edges): a single generic `(FROM_TYPE, FROM_ID, RELATIONSHIP, TO_TYPE,
TO_ID)` edge list spanning every module — `Supplier → supplies → Product`,
`Contract → governs → Supplier`, `Product → requires → Product` (BOM),
`Shipment → fulfills → Order`, etc. The SQL creates `EDGES_FORWARD` /
`EDGES_BACKWARD` views so this is traversable in both directions, which is
what Phase 4 impact analysis and the Ontology Explorer page need.

**Important caveat:** for Phase 1, the ERP A ↔ ERP B entity resolution
above is done *deterministically*, using the same crosswalk that generated
the synthetic data. Phase 2 replaces this with the actual governed
pipeline — AI-proposed mappings, confidence scores, a mapping registry, and
human-in-the-loop approval for anything uncertain. The canonical **schema**
you see here doesn't change; only *how it gets populated* does. This is
also why `docs/golden_entity_crosswalk.csv` stays useful going forward — as
the answer key to score Phase 2's AI mapping against.

## Phase 2 — Governance (mapping registry, confidence, human review, timezones)

`csv/governance/mapping_registry.csv` and `sql/12_mapping_registry.sql`,
`sql/13_timezone_normalization.sql` add:

- **`GOVERNANCE.MAPPING_REGISTRY`** — 49 AI-proposed mappings from ERP A/B
  raw columns to canonical entity.attribute, each with a confidence score
  (0–100) and a rationale explaining *why* that score, not just what it is
  — e.g. `ERP_A.EINDT → ORDER_LINE.promised_delivery_date` scores 72%
  because SAP overloads that field across several delivery-date semantics,
  while `ERP_B.PROMISE_DT` scores 91.5% for the same business concept
  because its name removes that ambiguity. Two fields (`SPERR`,
  `WAREHOUSE_ZONE`) score low deliberately — no canonical attribute exists
  for them yet, which is the correct outcome, not a bug.
- **Confidence-based governance**, exactly as spec'd: ≥90 auto-approved (40
  of 49), 60–89 pending human review (6), 45–59 needs clarification (1),
  <45 rejected (2) — thresholds live in `MAPPING_CONFIDENCE_THRESHOLDS`,
  not hardcoded, and `MAPPING_REGISTRY_RECLASSIFIED` recomputes live if
  they change.
- **Human-in-the-loop stored procedures**: `APPROVE_MAPPING`,
  `REJECT_MAPPING`, `MODIFY_MAPPING` — the three actions from section 8's
  review UI, callable directly in SQL today; the Streamlit "Human Review"
  page (Phase 5) will just be a UI wrapper over `HUMAN_REVIEW_QUEUE` and
  these three procedures.
- **The production mapping mechanism** (not just the static demo CSV): a
  `PROPOSE_MAPPING()` SQL function using `SNOWFLAKE.CORTEX.COMPLETE`, so a
  *new* source system gets proposals the same way — inspect
  `INFORMATION_SCHEMA`, sample values, and the canonical ontology
  description, ask Cortex, get the same JSON shape back. The 49 rows in
  the registry today were hand-authored to the same contract so the
  registry, governance tiers, and review workflow have real data to run
  against without requiring a live Snowflake connection to build this demo.
- **Timezone normalization** (`GOVERNANCE.SHIPMENT_EVENTS_UTC`,
  `WAREHOUSE_EVENTS_UTC`, `SHIPMENT_EVENT_TIMELINE`,
  `SHIPMENT_DELIVERY_TIMEZONE_SAFE`) — converts every local
  timestamp+timezone pair to canonical UTC via `CONVERT_TIMEZONE`, while
  preserving the original local value. `SHIPMENT_EVENT_TIMELINE` is the
  direct Test 3 check: event ordering computed on UTC timestamps must
  match the true chronology even when origin and destination timezones
  differ.

See `docs/test_cases.md` for the full spec Test 1–8 status and runnable
verification queries (Tests 1, 3, and 5 pass today; 2, 4, 6–8 need Phase
3–5 work).

## Phase 3 — Analytics (canonical metrics, semantic view, persona consistency)

`sql/14_canonical_metrics.sql` and `sql/15_semantic_view_conversational_analytics.sql` add:

- **`SEMANTIC_LAYER.CANONICAL_METRICS`** — the governed, single-source
  definition of On-Time Delivery Rate, Fill Rate, Days of Inventory, and
  Landed Cost (name, definition, formula, eligibility rule, owner,
  version). Nothing downstream is allowed to redefine these (guardrail
  #1/#2) — every metric view below implements exactly this text.
- **Fact views computed once, reused everywhere**:
  `FACT_SHIPMENT_OTD` (joins through the Phase 2 timezone-safe view, so
  OTD is never computed on naive local timestamps) and
  `FACT_ORDER_LINE_FULFILLMENT` (flags `PROMISE_DATE_MISSING` per line
  rather than silently coercing a NULL promise date into "on time" — Test
  6). Every persona-facing query is a `WHERE`/`GROUP BY` on top of these
  same two views, which is *how* consistency across personas is
  structurally guaranteed, not just claimed.
- **`METRIC_DAYS_OF_INVENTORY`** and **`METRIC_LANDED_COST_BY_PRODUCT`** —
  DOI returns `NULL` (not 0 or ∞) when there's no recent demand signal;
  Landed Cost uses a configurable `LANDED_COST_CONFIG` table
  (freight/duty/handling % by supplier country, with a default fallback)
  and is always labeled an *estimate*, per guardrail #5.
- **A native Snowflake `SEMANTIC VIEW`** (`SUPPLY_CHAIN_SEMANTIC_VIEW`) —
  what Cortex Analyst (or any NL interface) queries for conversational
  analytics. Persona vocabulary ("delivery reliability" / "OTD" /
  "delivered on time") is captured as `WITH SYNONYMS` on the *same*
  `on_time_delivery_rate` metric, which is the actual mechanism that makes
  three different phrasings resolve to one number.

**`docs/persona_consistency_demo.md`** and **`docs/answer_trust_layer_example.md`**
show this working end-to-end on the real synthetic data: Planning,
Procurement, and Logistics phrasings for Shenzhen Circuit Solutions all
return **86.4% OTD** from the same 22 eligible / 19 on-time shipments, and
a full four-metric trust-layer worked example (with an honestly-labeled
caveat on the Fill Rate number, which is deflated by a synthetic-data
linkage gap, not a governance bug — see the doc for detail).

## Phase 4 — Intelligence (dependency graph, impact analysis, financial impact, streams/tasks, schema drift)

`sql/16` through `sql/20` add:

- **`TRAVERSE_GRAPH()`** — a generic bidirectional N-hop walk over
  `RELATIONSHIP_EDGES` (Snowflake Scripting + recursive CTE), answering
  both section 16 examples: forward ("what customers depend on Supplier
  ABC") and backward ("which suppliers are responsible for delayed
  Customer XYZ orders") through the same procedure, just flipping
  `WALK_DIRECTION`.
- **`IMPACT_ANALYSIS_SHIPMENT()`** — traces a delayed shipment through
  products → (if a raw material) finished goods via Bill of Materials →
  production orders → affected sales/purchase orders → customers. Built
  and then **corrected mid-build**: the first version didn't scope by
  plant and produced a nonsensical company-wide, $30M "impact" for one
  shipment by sweeping in every order anywhere that happens to use the
  same generic raw material. The fixed version resolves the shipment's
  actual destination plant first (`Shipment→fulfills→Order→fulfilled_at→Plant`)
  and scopes every downstream step to that plant — a raw-material delay
  disrupts the plant it was headed to, not the whole company. Worked
  example with real traced numbers (1 plant, 6 production orders, 9
  orders, 4 customers) in `docs/impact_analysis_example.md`.
- **`FINANCIAL_IMPACT_ESTIMATE()`** — operational (production disruption),
  logistics (expedited shipping + inventory carrying), and
  customer/revenue impact, each from a configurable rate table
  (`FINANCIAL_IMPACT_CONFIG`), always computed on top of the corrected
  plant-scoped impact set, always labeled ESTIMATE.
- **Streams + Tasks + Dynamic Tables** for the near-real-time path:
  `CURRENT_SHIPMENT_STATUS` and `CURRENT_SHIPMENT_LOCATION` (Dynamic
  Tables, 5-minute target lag) stay fresh off the raw event tables without
  a manual batch job, and `PROCESS_SHIPMENT_DELAY_EVENTS` (a Task gated on
  `SYSTEM$STREAM_HAS_DATA`, so it costs nothing when nothing changed)
  automatically opens an `OPEN_EXCEPTIONS` row the moment a `DELAYED`
  event lands — giving Impact Analysis a real trigger instead of relying
  on someone remembering to run it.
- **Schema drift detection** — `TAKE_SCHEMA_SNAPSHOT()` /
  `DETECT_SCHEMA_DRIFT()` diff consecutive `INFORMATION_SCHEMA.COLUMNS`
  snapshots and cross-reference `MAPPING_REGISTRY` so a datatype change on
  a *mapped* column immediately surfaces which mappings are now at risk —
  the exact `EINDT DATE→VARCHAR` scenario from spec section 21 is the
  documented walkthrough at the bottom of `sql/20_schema_drift_detection.sql`.

Tests 1–7 now pass (see `docs/test_cases.md`); only Test 8 (document
extraction) remains, pending Phase 5.

## Phase 5 — Documents & Streamlit app

- `sql/21_document_extraction.sql` — Cortex-based contract extraction into
  `ONTOLOGY_CORE.CONTRACT`, with the same confidence tiers as schema mapping.
  `docs/document_extraction_example.md`: 100% field accuracy on the 10
  synthetic contracts (regex stand-in; they share one template, so this
  overstates real-world accuracy — the doc says why).
- `streamlit_app/` — 7 pages: Control Tower, Conversational Analytics,
  Ontology Explorer, Schema Mapping, Impact Analysis, Data/Metric Lineage,
  Human Review. All thin UIs over the SQL objects above. See `DEPLOY.md`.
- `docs/coco_lifecycle_and_demo_script.md` — CoCo prompts per stage, an
  evidence log to fill in, and the 10-step demo script.

**Not verified:** none of the SQL or the Streamlit app has been run against
a live Snowflake account. The Python files compile; the SQL is unexecuted.
Expect first-run fixes (semantic view syntax, grants, stage reads).

## What's intentionally NOT in this package yet

All spec phases are now drafted. Remaining work is validation: executing
everything in Snowflake, fixing what breaks, and recording real CoCo usage.

## Regenerating the data

```bash
bash run_all.sh        # run from the repo root; needs Python 3.10+, pandas, faker
```

ERP A/B, logistics, IoT, contracts, and the core ontology regenerate
**byte-identically** (all seeded). The manufacturing production orders,
services orders, and the graph edges derived from them were generated
before their sampling was seeded, so a fresh run produces equivalent but
**not identical** rows. The committed CSVs are the snapshot that the worked
examples in `docs/` (impact analysis: 1 plant / 6 production orders / 9
orders / 4 customers, etc.) were computed from — regenerating will change
those particular numbers.

`generators/` scripts use paths relative to the repo root.
