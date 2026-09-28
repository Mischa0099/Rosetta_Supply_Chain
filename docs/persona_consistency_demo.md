# Persona Consistency Demo (spec section 13, Test 2)

Three different personas ask the same underlying business question in
their own words. All three route through `SEMANTIC_LAYER.FACT_SHIPMENT_OTD`
via the `on_time_delivery_rate` metric on `SUPPLY_CHAIN_SEMANTIC_VIEW` —
none of them recompute the formula independently.

**Supplier used:** Shenzhen Circuit Solutions (`CS-SUP-003`)

| Persona | Question (their words) | Resolves to | Result |
|---|---|---|---|
| Planning | "What is Supplier Shenzhen Circuit Solutions's delivery reliability?" | `on_time_delivery_rate` filtered `supplier_name = 'Shenzhen Circuit Solutions'` | **86.4%** |
| Procurement | "What is Shenzhen Circuit Solutions's OTD?" | same metric, same filter | **86.4%** |
| Logistics | "How many Shenzhen Circuit Solutions shipments were delivered on time?" | `on_time_shipment_count` / `eligible_shipment_count`, same filter | **19 / 22** (= 86.4%) |

All three numbers agree because all three questions compile to the same
`WHERE supplier_name = 'Shenzhen Circuit Solutions'` filter over the same
`FACT_SHIPMENT_OTD` rows — Logistics' phrasing just asks for the raw counts
instead of the percentage, which is a display choice, not a different
calculation.

## Why this actually proves something

The three Python functions computing these numbers
(`planning_delivery_reliability`, `procurement_otd`,
`logistics_on_time_count` in `gen/13_compute_metrics_demo.py`) are named
differently to represent three different callers, but they read the exact
same `IS_ELIGIBLE` / `IS_ON_TIME` columns with the exact same filter. In
the live system this guarantee comes from all three personas' questions
being routed through the one `SUPPLY_CHAIN_SEMANTIC_VIEW` — a persona never
gets its own private query path.

## What would break this (and why the design prevents it)

- ❌ Procurement defining OTD as "delivered within promise date + 2 day
  grace period" while Logistics uses the strict definition → prevented
  because `IS_ON_TIME` is computed once, in `FACT_SHIPMENT_OTD`, not
  per-persona.
- ❌ Planning excluding in-transit shipments from the denominator while
  Procurement includes them as "late" → prevented because `IS_ELIGIBLE`
  (DELIVERED + non-null promise date) is also computed once, centrally.
- ❌ One persona's dashboard reading pre-Phase-2 raw ERP timestamps
  (naive local time) while another reads the UTC-normalized version →
  prevented because `FACT_SHIPMENT_OTD` always joins through
  `GOVERNANCE.SHIPMENT_DELIVERY_TIMEZONE_SAFE`.
