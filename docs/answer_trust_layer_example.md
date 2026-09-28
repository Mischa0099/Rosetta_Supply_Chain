# Answer Trust Layer — worked examples (spec section 14)

Every governed answer exposes metric name, definition, formula, period,
source systems, record counts, lineage, confidence, and filters — not just
the number. Computed from the actual synthetic dataset
(`gen/13_compute_metrics_demo.py`).

## On-Time Delivery — Shenzhen Circuit Solutions

| Field | Value |
|---|---|
| **Metric** | On-Time Delivery Rate |
| **Value** | **86.4%** |
| **Definition** | Share of eligible shipments delivered on or before the promised delivery date |
| **Formula** | `SUM(is_on_time) / COUNT(eligible_shipments)` |
| **Eligibility rule** | Non-null `PROMISED_DELIVERY_DATE` AND `STATUS = DELIVERED`; in-transit shipments excluded from denominator, not counted as late |
| **Period** | All available data (no date filter applied) |
| **Source systems** | RAW_LOGISTICS.SHIPMENTS + RAW_LOGISTICS.SHIPMENT_EVENTS (timezone-normalized via GOVERNANCE.SHIPMENT_DELIVERY_TIMEZONE_SAFE) |
| **Eligible shipments** | 22 |
| **On-time shipments** | 19 |
| **Lineage** | Supplier → Order (PURCHASE) → Shipment → Shipment Event (DELIVERED) |
| **Confidence** | High — all contributing fields (`LIFNR`→supplier_id, promise/actual dates) are `AUTO_APPROVED` mappings in the registry (≥91%) |
| **Filters applied** | `supplier_name = 'Shenzhen Circuit Solutions'`, `direction = 'INBOUND'` |

## Fill Rate — Shenzhen Circuit Solutions

| Field | Value |
|---|---|
| **Metric** | Fill Rate |
| **Value** | 37.9% *(see caveat below)* |
| **Definition** | Share of ordered quantity actually delivered |
| **Formula** | `SUM(quantity_delivered) / SUM(quantity_ordered)` |
| **Total ordered** | 83,553 units |
| **Total delivered** | 31,684 units |
| **Lines with missing promise date** | 0 (flagged separately when present — Test 6) |
| **Confidence** | Medium — see caveat |

**Caveat, stated plainly rather than hidden (guardrail #3, #9):** in this
synthetic dataset, shipments are generated independently of purchase
orders rather than guaranteeing one fulfilling shipment per PO line, so
many PO lines here have no linked shipment at all and register as
zero-delivered. That's a synthetic-data linkage gap, not a real fill-rate
signal — a production connector would tie every PO line to its actual
fulfilling shipment(s) (potentially several, for split shipments), and
this number would be materially higher. The **formula and governance
logic are real and correct**; this particular number is a demonstration
artifact and should not be read as a business finding.

## Days of Inventory — Standard Chemical Coating @ Columbus Plant

| Field | Value |
|---|---|
| **Metric** | Days of Inventory |
| **Value** | 576.9 days |
| **Formula** | `quantity_on_hand / average_daily_demand` (90-day trailing demand) |
| **Quantity on hand** | 2,814 units |
| **Avg daily demand (90d)** | 4.88 units/day |
| **Interpretation flag** | 576.9 days is unusually high — worth a Planning review (excess stock or a demand-signal gap), not silently presented as "fine" |

## Landed Cost — Heavy-Duty Steel Bracket (from Shenzhen Circuit Solutions)

| Field | Value |
|---|---|
| **Metric** | Landed Cost |
| **Value** | **$380.58 (ESTIMATE)** |
| **Formula** | `unit_price × (1 + freight_pct + duty_pct + handling_pct)` |
| **Avg unit price** | $345.98 |
| **Freight / Duty / Handling** | 6% / 2% / 2% (UK-origin config) |
| **Label** | Explicitly marked **ESTIMATE** — this is a percent-of-cost model, not actual freight invoices (guardrail #5) |

---

These four examples are what the Trust/Lineage panel and the "Data/Metric
Lineage" Streamlit page (Phase 5) render for any governed answer — the
conversational analytics layer (Phase 3/5) is responsible for populating
this same structure for whatever metric+filter combination a person asks
about, never a bespoke one-off explanation per question.
