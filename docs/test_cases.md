# Testing Scenarios (spec section 24) — status & runnable checks

| # | Test | Status | How to verify |
|---|---|---|---|
| 1 | ERP Mapping — SAP LIFNR and Custom ERP VENDOR_NO map to the same canonical Supplier ID | ✅ Built | `SELECT * FROM ONTOLOGY_CORE.SUPPLIER WHERE SOURCE_SYSTEMS='ERP_A+ERP_B' LIMIT 5;` — each row has both `ERP_A_SUPPLIER_ID` and `ERP_B_VENDOR_ID` populated against one `CANONICAL_SUPPLIER_ID`. Score against `RAW_DOCUMENTS.GOLDEN_ENTITY_CROSSWALK_ANSWER_KEY`. |
| 2 | Metric Consistency — Planning/Procurement/Logistics get the same OTD for equivalent filters | ✅ Built | `docs/persona_consistency_demo.md` — three phrasings, same `FACT_SHIPMENT_OTD` filter, all resolve to 86.4% for Shenzhen Circuit Solutions. |
| 3 | Time Zones — equivalent timestamps from different countries produce the same event chronology | ✅ Built | `SELECT * FROM GOVERNANCE.SHIPMENT_EVENT_TIMELINE WHERE CORRECT_SEQUENCE != SOURCE_RECORDED_SEQUENCE;` should return 0 rows once events are read through the UTC-normalized view. |
| 4 | Impact Propagation — a delayed shipment correctly identifies affected parts, plants, orders, customers | ✅ Built | `docs/impact_analysis_example.md` — `SHP-100001` traced to 1 plant, 6 production orders, 9 orders, 4 customers, all plant-scoped (not company-wide). `SELECT * FROM TABLE(INTELLIGENCE.IMPACT_ANALYSIS_SHIPMENT('SHP-100001'));` |
| 5 | Low Confidence Mapping — an ambiguous field requires human approval | ✅ Built | `SELECT * FROM GOVERNANCE.MAPPING_REGISTRY WHERE SOURCE_COLUMN='EINDT' AND SOURCE_SYSTEM='ERP_A';` → `CONFIDENCE_SCORE=72.0`, `APPROVAL_STATUS='PENDING_REVIEW'`, never auto-approved. |
| 6 | Missing Data — missing promised delivery dates should not silently produce an incorrect OTD | ✅ Built | `SEMANTIC_LAYER.FACT_ORDER_LINE_FULFILLMENT.PROMISE_DATE_MISSING` flags every such line; `METRIC_FILL_RATE_BY_SUPPLIER.LINES_WITH_MISSING_PROMISE_DATE` surfaces the count rather than silently coercing NULL to on-time. `METRIC_DAYS_OF_INVENTORY` similarly returns `NULL` (not 0 or infinity) when there's no recent demand data. |
| 7 | Schema Drift — changing a source datatype triggers a warning | ✅ Built | `CALL INTELLIGENCE.TAKE_SCHEMA_SNAPSHOT();` before/after a source change, then `CALL INTELLIGENCE.DETECT_SCHEMA_DRIFT();` and check `INTELLIGENCE.UNACKNOWLEDGED_SCHEMA_DRIFT` — full walkthrough with the exact `EINDT DATE→VARCHAR` example from the spec is in `sql/20_schema_drift_detection.sql`. |
| 8 | Document Extraction — contract SLA info is extracted and linked to the right supplier | ✅ Built | `docs/document_extraction_example.md` — 100% field accuracy across 10 contracts / 8 fields each (caveat: synthetic contracts share one template; see doc for why production accuracy will be lower and why confidence governance still matters). Live path: `sql/21_document_extraction.sql` → `CALL APPLY_CONTRACT_EXTRACTION();`. |

## Quick verification queries

```sql
-- Test 1: entity resolution accuracy against the golden answer key
SELECT g.entity_type, COUNT(*) AS total,
       SUM(IFF(g.present_in='ERP_A+ERP_B' AND s.ERP_A_SUPPLIER_ID IS NOT NULL AND s.ERP_B_VENDOR_ID IS NOT NULL, 1, 0)) AS correctly_deduped
FROM RAW_DOCUMENTS.GOLDEN_ENTITY_CROSSWALK_ANSWER_KEY g
LEFT JOIN ONTOLOGY_CORE.SUPPLIER s ON g.master_key = s.MASTER_KEY
WHERE g.entity_type = 'Supplier'
GROUP BY g.entity_type;

-- Test 3: chronology check (see docs table above)
SELECT * FROM GOVERNANCE.SHIPMENT_EVENT_TIMELINE
WHERE CORRECT_SEQUENCE != SOURCE_RECORDED_SEQUENCE;

-- Test 5: confirm the registry never auto-approves a sub-90 mapping
SELECT * FROM GOVERNANCE.MAPPING_REGISTRY
WHERE CONFIDENCE_SCORE < 90 AND APPROVAL_STATUS = 'AUTO_APPROVED';
-- Expect 0 rows.
```
