**Rosetta Chain**

One business language for every supply-chain system.

Rosetta Chain is a governed supply-chain intelligence layer built on Snowflake. It maps data from different ERPs into one canonical model, keeps metrics like on-time delivery identical for every team, and traces a delayed shipment to the plants, orders, and customers it affects, with an estimated cost.

Source systems can differ in schema, terminology, and structure. The business meaning and the governed metrics stay the same.

Status: working draft. The Python generators run and produce the data in this repo. The Snowflake SQL and the Streamlit app have not been run against a live Snowflake account yet. Expect small first-run fixes. See Known limitations.

The problem

SAP calls a supplier LIFNR. Another ERP calls it VENDOR_ID. One system stores times in local time and another in UTC. Planning says "delivery reliability", Procurement says "OTD", Logistics says "shipments delivered on time", and each team's number comes out slightly different.

Rosetta Chain resolves these differences in one place and shows its work.

What it does
Capability	How
AI-assisted schema mapping	Proposes source-column → canonical-attribute mappings with a confidence score and a written rationale.
Confidence-based governance	≥90 auto-approves, 60–89 goes to human review, below that needs clarification or is rejected. Thresholds live in a table, not in code.
Adaptive ontology	A common core, plus optional Goods, Manufacturing, and Services modules that never modify the core.
Governed metrics	On-Time Delivery, Fill Rate, Days of Inventory, and Landed Cost are each defined once. Every persona query reads the same fact views.
Conversational analytics	A native Snowflake Semantic View with persona synonyms, so different phrasings resolve to the same metric.
Timezone normalization	Local timestamps are converted to UTC while the originals are preserved, so on-time and event-ordering logic is correct across countries.
Dependency graph + impact analysis	Walk the graph in either direction. A delayed shipment is traced through raw materials, finished goods, production orders, orders, and customers.
Financial impact estimates	Operational, logistics, and revenue impact from configurable rates. Always labeled ESTIMATE.
Near-real-time events	Streams, Tasks, and Dynamic Tables. A DELAYED event opens an exception automatically.
Schema drift detection	Snapshot and diff of source schemas, cross-referenced to affected mappings.
Contract extraction	Cortex-based extraction of SLA, lead time, and dates, with the same confidence tiers.
Answer trust layer	Every answer exposes definition, formula, record counts, sources, lineage, and caveats.
Architecture
uncertain
important decisions
ERP A - SAP-likeERP B - Oracle-likeLogistics · IoT · Contracts
Ingestion & timezonenormalization
AI schema mapping+ mapping registry
Canonical ontologyCore + Goods /Manufacturing / Services
Dependency & impactgraph
Governed semantic layercanonical metrics
Conversational analytics
Impact analysis+ financial estimate
Trust · lineage · confidence
Human review
Repository layout
csv/               Synthetic data: ERP A/B, logistics, IoT, ontology, graph, governance
contracts/         10 synthetic supplier contracts (plain text)
sql/               Snowflake scripts, numbered in run order (00 → 21)
streamlit_app/     7-page Streamlit app + DEPLOY.md
generators/        Python scripts that build all of the data
docs/              Ontology diagram, test cases, worked examples, demo script
run_all.sh         Regenerate everything from scratch
Quick start

1. Regenerate the data (optional, it is already committed)

bash
bash run_all.sh          # from the repo root; Python 3.10+, pandas, faker

2. Load into Snowflake

Follow sql/00_setup_and_run_order.sql. It lists the PUT commands and the order for scripts 01–21. Each script creates its own schema, stage, and tables.

3. Deploy the app

See streamlit_app/DEPLOY.md. It targets Streamlit in Snowflake and also has a local option.

The demo story
Two ERPs with different columns. Show LIFNR next to VENDOR_ID.
Run schema mapping and show both resolving to supplier_id.
Show the canonical ontology, with one supplier carrying both source IDs.
Ask the same question as Planning, Procurement, and Logistics. All three return the same OTD.
Inject a delay event.
Traverse the graph from supplier to customer.
Run impact analysis and read out the estimated cost.
Show contract terms extracted and linked to the supplier.
Open the trust panel to see definition, lineage, and confidence.
Approve an ambiguous mapping in Human Review.

The full script is in docs/coco_lifecycle_and_demo_script.md.

Guardrails
Metric definitions are never invented or silently redefined.
Low-confidence mappings are never auto-approved.
Missing or poor-quality data is surfaced, not hidden.
Estimated financial impact is never presented as an accounting figure.
Facts, calculations, estimates, and AI interpretations are kept distinct.
Testing

Eight scenarios are defined in docs/test_cases.md: ERP mapping, metric consistency, timezones, impact propagation, low-confidence mapping, missing data, schema drift, and document extraction. Each has a runnable check. None has been executed in Snowflake yet.

Known limitations
Untested in Snowflake. The SQL and the Streamlit app have never run against a live account. Likely first-run issues are the CREATE SEMANTIC VIEW syntax, the stage-read view in sql/21, role grants, and COPY INTO column order.
Mappings are not live AI output. The 49-row mapping registry was hand-authored to the same output shape that the PROPOSE_MAPPING() Cortex function produces.
Fill Rate is deflated. In the synthetic data, many purchase-order lines have no linked shipment. The formula is correct, but the absolute number is a demo artifact.
Contract extraction accuracy is overstated. The 100% figure comes from 10 contracts that share one template.
Order value is a proxy. Sales-order lines carry no price, so revenue impact uses average purchase prices.
Data is snapshotted. The committed manufacturing and services CSVs were generated before their sampling was seeded. A fresh run_all.sh gives equivalent but not identical rows, and the impact-analysis example in docs/ will change.
Tech

Snowflake (Semantic Views, Cortex, Streams, Tasks, Dynamic Tables, Snowpark) · Streamlit · Python · pandas

License

No license has been chosen yet.
