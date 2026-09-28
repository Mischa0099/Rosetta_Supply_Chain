# Impact Analysis — worked example (spec sections 17-18, Test 4)

**Scenario:** Shipment `SHP-100001` (inbound, Shenzhen/Seoul-area supplier →
Columbus Plant) is running behind — currently `IN_TRANSIT`, promised
2026-03-31. We estimate a **4-day delay**.

Computed by `gen/14_compute_impact_analysis_demo.py`, mirroring
`sql/17_impact_analysis.sql` and `sql/18_financial_impact_estimation.sql`
exactly — real traversal over the actual `RELATIONSHIP_EDGES` graph, not
hand-picked numbers.

## Traversal

| Step | Result |
|---|---|
| **Products directly on this shipment** | Standard Aluminum Panel, Standard Steel Bracket, Standard Industrial Gas Cylinder |
| **Destination plant** (Shipment → fulfills → Order → fulfilled_at → Plant) | Columbus Plant only |
| **Downstream finished goods** (BOM `requires`, scoped to what Columbus actually produces) | Heavy-Duty Battery Pack |
| **Affected plants** | **1** (Columbus Plant) |
| **Affected production orders** | **6** (`PRD-ORD-1003`, `1007`, `1015`, `1029`, `1030`, `1058`) |
| **Affected orders** | **9** (6 purchase orders across ERP A/B for these products at Columbus, 3 sales orders needing them) |
| **Affected customers** | **4** (Northline Retail Group, Redwood Industrial Supply, Lakeshore Consumer Products, Falcon Point Manufacturing) |

**Why this is scoped to one plant, not company-wide:** an earlier version
of this traversal walked `Product → requires → Product` and
`Order → contains → Product` without a plant filter, which swept in every
order anywhere in the company that ever touches the same generic raw
material — a nonsensical multi-plant, 130+-order, $30M "impact" for one
shipment. The corrected version resolves the shipment's actual destination
plant first and scopes every downstream step (finished goods, production
orders, order lines) to that plant. A raw-material delay disrupts the
plant it was headed to — not every plant that happens to buy the same
category of part.

## Financial impact estimate

| Category | Estimated amount | Basis |
|---|---|---|
| **Operational impact** (production disruption) | **$20,000** | 1 affected plant × $5,000/day × 4 days |
| **Logistics impact** (expedited shipping) | $1,297,049 | Affected order value × 15% expedite premium |
| **Logistics impact** (inventory carrying) | $18,952 | Affected order value × 20% annual rate × 4/365 days |
| **Logistics impact, total** | **$1,316,001** | |
| **Customer/revenue impact** | **$864,699** | Affected order value × 10% at-risk share (conservative) |
| **Estimated total impact** | **≈ $2.20M** | Sum of the above — **ESTIMATE**, not an accounting figure |

Affected order value proxy: **$8,646,991** — summed from the 9 affected
orders using each product's average purchase price as a stand-in for
order value (see `sql/18_financial_impact_estimation.sql` for why sales
order lines don't carry their own price in this dataset).

**Every number above is explicitly labeled ESTIMATE.** None of it should
ever be presented as, or mistaken for, an actual accounting/GL figure
(guardrail #5) — it's a directional sizing to help someone triage whether
a 4-day delay on this shipment is a shrug or a fire drill.

## How this feeds the rest of the platform

- The Streamlit **Impact Analysis** page (Phase 5) is a thin UI over
  `TABLE(IMPACT_ANALYSIS_SHIPMENT(shipment_id))` and
  `TABLE(FINANCIAL_IMPACT_ESTIMATE(shipment_id, delay_days))` — no new
  logic, just a picker for `shipment_id`/`delay_days` and a rendered table.
- The near-real-time event pipeline (`sql/19_...`) automatically opens an
  `OPEN_EXCEPTIONS` row the moment a `DELAYED` event lands, so this
  traversal has a natural trigger rather than requiring someone to
  remember to run it.
