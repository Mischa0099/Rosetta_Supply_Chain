"""
Phase 2: AI-Powered Schema Mapping + Mapping Registry (spec sections 7-8).

Proposes canonical-entity mappings for every notable source column in
ERP A and ERP B, with a confidence score and rationale, then applies
confidence-based governance (auto-approve / human review / reject).

In production this proposal step runs via SNOWFLAKE.CORTEX.COMPLETE over
each column's name, datatype, sample values, table context, and available
documentation (see sql/12_mapping_registry.sql for the live Cortex version
of this exact prompt/output contract). Here we hand-author the same output
shape so the registry, confidence governance, and human-review workflow
have real, inspectable data to run against without a live Cortex call.
Confidence scores are deliberately varied - some obvious (>=95), some
genuinely ambiguous (60-89, needs review), one rejected outright - to
exercise all three governance tiers (Test 5).
"""
import os, json
from datetime import datetime, timezone
import pandas as pd

OUT = "./csv/governance"
os.makedirs(OUT, exist_ok=True)

NOW = datetime.now(timezone.utc).isoformat()

# (source_system, source_table, source_column, canonical_entity, canonical_attribute,
#  transformation, confidence, rationale)
PROPOSALS = [
    # ---- ERP A (SAP-like) — high confidence, well-known SAP field names ----
    ("ERP_A", "SUPPLIERS", "LIFNR", "SUPPLIER", "supplier_id", "Zero-pad strip / direct copy", 99.4,
     "Exact match to standard SAP vendor-number field LIFNR; datatype and cardinality consistent with a supplier primary key."),
    ("ERP_A", "SUPPLIERS", "NAME1", "SUPPLIER", "supplier_name", "Direct copy", 98.1,
     "Standard SAP name field on vendor master (LFA1); free-text, one value per LIFNR."),
    ("ERP_A", "SUPPLIERS", "LAND1", "SUPPLIER", "country", "ISO-2 direct copy", 97.5,
     "Standard SAP 2-char country key; values match ISO 3166-1 alpha-2 pattern."),
    ("ERP_A", "SUPPLIERS", "ZTIMEZONE", "SUPPLIER", "timezone", "Direct copy", 88.0,
     "Custom Z-field, not a standard SAP field; name and IANA-formatted sample values strongly suggest timezone, but custom fields carry lower base confidence."),
    ("ERP_A", "SUPPLIERS", "WAERS", "SUPPLIER", "default_currency", "ISO-3 direct copy", 96.0,
     "Standard SAP currency key field; 3-letter ISO 4217 sample values."),
    ("ERP_A", "SUPPLIERS", "SPERR", "SUPPLIER", "(unmapped - block flag)", "N/A", 41.0,
     "No canonical attribute currently models a supplier hold/block status; flagging for ontology extension rather than forcing a mapping."),
    ("ERP_A", "MATERIALS", "MATNR", "PRODUCT", "product_id", "Direct copy", 99.1,
     "Exact match to standard SAP material-number field MATNR."),
    ("ERP_A", "MATERIALS", "MAKTX", "PRODUCT", "product_name", "Direct copy", 97.8,
     "Standard SAP material description field."),
    ("ERP_A", "MATERIALS", "MEINS", "PRODUCT", "unit_of_measure", "Direct copy", 95.5,
     "Standard SAP base-unit-of-measure field; short codes (EA/KG/M/L) match expected UoM domain."),
    ("ERP_A", "MATERIALS", "MTART", "PRODUCT", "category", "Direct copy", 76.0,
     "MTART is technically 'material type' in SAP, not category - close but not identical business meaning; needs review."),
    ("ERP_A", "PLANTS", "WERKS", "PLANT", "plant_id", "Direct copy", 99.0,
     "Exact match to standard SAP plant field WERKS."),
    ("ERP_A", "PLANTS", "NAME1", "PLANT", "plant_name", "Direct copy", 97.0,
     "Standard SAP plant description field."),
    ("ERP_A", "PLANTS", "ZTIMEZONE", "PLANT", "timezone", "Direct copy", 89.0,
     "Custom field, IANA-formatted sample values consistent with timezone."),
    ("ERP_A", "CUSTOMERS", "KUNNR", "CUSTOMER", "customer_id", "Zero-pad strip / direct copy", 98.8,
     "Exact match to standard SAP customer-number field KUNNR."),
    ("ERP_A", "CUSTOMERS", "NAME1", "CUSTOMER", "customer_name", "Direct copy", 97.9, "Standard SAP customer name field."),
    ("ERP_A", "PURCHASE_ORDERS", "EBELN", "ORDER", "order_id", "Direct copy, ORDER_TYPE=PURCHASE", 98.5,
     "Standard SAP purchasing document number."),
    ("ERP_A", "PURCHASE_ORDERS", "LIFNR", "ORDER", "supplier_id", "Direct copy (FK)", 98.0,
     "Header-level vendor reference, consistent with PURCHASE_ORDERS.SUPPLIER_ID."),
    ("ERP_A", "PURCHASE_ORDERS", "BEDAT", "ORDER", "order_date", "Direct copy", 94.0,
     "Standard SAP purchasing document date field."),
    ("ERP_A", "PURCHASE_ORDER_ITEMS", "EINDT", "ORDER_LINE", "promised_delivery_date", "Direct copy", 72.0,
     "EINDT is the SAP item delivery date, but SAP overloads this field across several delivery-date semantics (requested vs confirmed vs promised) depending on config; sample values and table context support 'promised' but this is not certain without business-process documentation - flagged for review."),
    ("ERP_A", "PURCHASE_ORDER_ITEMS", "MENGE", "ORDER_LINE", "quantity", "Direct copy", 96.5, "Standard SAP order quantity field."),
    ("ERP_A", "PURCHASE_ORDER_ITEMS", "NETPR", "ORDER_LINE", "unit_price", "Direct copy", 93.0, "Standard SAP net price field."),
    ("ERP_A", "SALES_ORDERS", "VBELN", "ORDER", "order_id", "Direct copy, ORDER_TYPE=SALES", 98.3, "Standard SAP sales document number."),
    ("ERP_A", "SALES_ORDERS", "KUNNR", "ORDER", "customer_id", "Direct copy (FK)", 97.6, "Sold-to party reference on sales order header."),
    ("ERP_A", "INVENTORY", "LABST", "INVENTORY", "quantity_on_hand", "Direct copy", 94.5,
     "Standard SAP unrestricted-use stock field (MARD-LABST)."),

    # ---- ERP B (Oracle/custom-like) — different naming, similar business meaning ----
    ("ERP_B", "VENDORS", "VENDOR_ID", "SUPPLIER", "supplier_id", "Direct copy", 99.2,
     "Self-descriptive field name; primary key pattern (VEND-#### ) unique per row."),
    ("ERP_B", "VENDORS", "VENDOR_NAME", "SUPPLIER", "supplier_name", "Direct copy", 98.7, "Self-descriptive; free-text, matches SUPPLIER_NAME cardinality."),
    ("ERP_B", "VENDORS", "COUNTRY_CODE", "SUPPLIER", "country", "Direct copy", 97.9, "ISO-2 pattern matches SUPPLIER.country."),
    ("ERP_B", "VENDORS", "TIME_ZONE", "SUPPLIER", "timezone", "Direct copy", 95.0, "Self-descriptive; IANA-formatted values."),
    ("ERP_B", "VENDORS", "CURRENCY_CODE", "SUPPLIER", "default_currency", "Direct copy", 96.2, "ISO-3 pattern matches SUPPLIER.default_currency."),
    ("ERP_B", "VENDORS", "STATUS", "SUPPLIER", "(unmapped - status flag)", "N/A", 38.0,
     "ACTIVE/HOLD values loosely parallel ERP_A.SPERR but no canonical attribute exists yet for either; same ontology-extension flag as SPERR, not auto-mapped."),
    ("ERP_B", "ITEMS", "SKU", "PRODUCT", "product_id", "Direct copy", 98.9, "Primary key pattern (SKU-XXX-####) unique per row."),
    ("ERP_B", "ITEMS", "ITEM_DESC", "PRODUCT", "product_name", "Direct copy", 97.4, "Self-descriptive free-text field."),
    ("ERP_B", "ITEMS", "UOM", "PRODUCT", "unit_of_measure", "Direct copy", 96.8, "Self-descriptive; short-code domain matches PRODUCT.unit_of_measure."),
    ("ERP_B", "ITEMS", "ITEM_CATEGORY", "PRODUCT", "category", "Direct copy", 91.0,
     "Self-descriptive and business meaning matches PRODUCT.category more directly than ERP_A's MTART did."),
    ("ERP_B", "LOCATIONS", "LOCATION_CODE", "PLANT", "plant_id", "Direct copy", 82.0,
     "LOCATIONS table maps to PLANT for this dataset, but 'location' is a broader concept than 'plant' in general - confidence reduced pending confirmation this source only carries plant-type locations (true here, but not guaranteed for a future source)."),
    ("ERP_B", "LOCATIONS", "LOCATION_NAME", "PLANT", "plant_name", "Direct copy", 81.0, "Same caveat as LOCATION_CODE."),
    ("ERP_B", "LOCATIONS", "TIME_ZONE", "PLANT", "timezone", "Direct copy", 93.0, "Self-descriptive; IANA-formatted values, high confidence independent of the entity-type caveat above."),
    ("ERP_B", "CUSTOMERS", "CUSTOMER_ID", "CUSTOMER", "customer_id", "Direct copy", 98.6, "Self-descriptive primary key."),
    ("ERP_B", "CUSTOMERS", "CUSTOMER_NAME", "CUSTOMER", "customer_name", "Direct copy", 97.7, "Self-descriptive free-text field."),
    ("ERP_B", "PURCHASE_ORDERS", "PO_NUMBER", "ORDER", "order_id", "Direct copy, ORDER_TYPE=PURCHASE", 98.4, "Self-descriptive primary key."),
    ("ERP_B", "PURCHASE_ORDERS", "VENDOR_ID", "ORDER", "supplier_id", "Direct copy (FK)", 97.8, "Header-level vendor reference."),
    ("ERP_B", "PURCHASE_ORDERS", "ORDER_DATE", "ORDER", "order_date", "Direct copy", 96.0, "Self-descriptive, unambiguous."),
    ("ERP_B", "PURCHASE_ORDER_LINES", "PROMISE_DT", "ORDER_LINE", "promised_delivery_date", "Direct copy", 91.5,
     "Field name explicitly says 'promise', removing the ambiguity that reduced ERP_A.EINDT's score - same business concept, clearer source naming."),
    ("ERP_B", "PURCHASE_ORDER_LINES", "QUANTITY", "ORDER_LINE", "quantity", "Direct copy", 97.0, "Self-descriptive, unambiguous."),
    ("ERP_B", "PURCHASE_ORDER_LINES", "UNIT_PRICE", "ORDER_LINE", "unit_price", "Direct copy", 96.5, "Self-descriptive, unambiguous."),
    ("ERP_B", "SALES_ORDERS", "ORDER_ID", "ORDER", "order_id", "Direct copy, ORDER_TYPE=SALES", 97.5,
     "Self-descriptive, but generic name 'ORDER_ID' is reused conceptually for both PO and SO in this source - confidence held just under 98 pending table-context confirmation (present here via source table name)."),
    ("ERP_B", "SALES_ORDERS", "CUSTOMER_ID", "ORDER", "customer_id", "Direct copy (FK)", 98.0, "Self-descriptive."),
    ("ERP_B", "INVENTORY_BALANCES", "QTY_ON_HAND", "INVENTORY", "quantity_on_hand", "Direct copy", 96.9, "Self-descriptive, unambiguous."),
    ("ERP_B", "INVENTORY_BALANCES", "WAREHOUSE_ZONE", "INVENTORY", "(unmapped - sub-location detail)", "N/A", 55.0,
     "Finer-grained than ERP_A's LGORT storage-location; both are sub-plant location detail with no canonical attribute yet - held for ontology extension rather than force-mapped, and treated as NEEDS_CLARIFICATION rather than a hard reject since it is likely useful once a sub-location attribute exists."),
]

rows = []
for i, (sysname, tbl, col, entity, attr, transform, conf, rationale) in enumerate(PROPOSALS, start=1):
    if conf >= 90:
        status = "AUTO_APPROVED"
    elif conf >= 60:
        status = "PENDING_REVIEW"
    else:
        status = "NEEDS_CLARIFICATION" if conf >= 45 else "REJECTED"
    rows.append({
        "MAPPING_ID": f"MAP-{i:04d}",
        "SOURCE_SYSTEM": sysname, "SOURCE_TABLE": tbl, "SOURCE_COLUMN": col,
        "CANONICAL_ENTITY": entity, "CANONICAL_ATTRIBUTE": attr,
        "TRANSFORMATION": transform, "CONFIDENCE_SCORE": conf,
        "RATIONALE": rationale, "APPROVAL_STATUS": status,
        "APPROVED_BY": "" if status != "AUTO_APPROVED" else "SYSTEM_AUTO_APPROVAL",
        "MAPPING_VERSION": 1, "CREATED_AT": NOW, "UPDATED_AT": NOW,
    })

df = pd.DataFrame(rows)
df.to_csv(f"{OUT}/mapping_registry.csv", index=False)

print(df.APPROVAL_STATUS.value_counts())
print(f"\nTotal proposals: {len(df)}")
print(f"Avg confidence: {df.CONFIDENCE_SCORE.mean():.1f}")
