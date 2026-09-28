"""
Data / Metric Lineage (spec section 14, 22 page 6). The Answer Trust
Layer: for a chosen metric + filter, show value, definition, formula,
eligibility rule, record counts, source systems, lineage, and any data
quality caveats - so a person can inspect WHY an answer was produced.
"""
import streamlit as st
from common import DB, run, page_header

st.set_page_config(page_title="Data & Metric Lineage", page_icon="🧬", layout="wide")
page_header("🧬 Data & Metric Lineage", "Where did this number come from? Definition, formula, records, sources, and caveats.")

metrics = run(f"SELECT * FROM {DB}.SEMANTIC_LAYER.CANONICAL_METRICS ORDER BY METRIC_NAME")
metric_name = st.selectbox("Metric", metrics.METRIC_NAME.tolist())
m = metrics[metrics.METRIC_NAME == metric_name].iloc[0]

with st.container(border=True):
    st.subheader(f"📐 {m.METRIC_NAME} (v{m.VERSION})")
    st.markdown(f"**Definition:** {m.DEFINITION}")
    st.code(m.FORMULA, language="text")
    st.markdown(f"**Eligibility rule:** {m.ELIGIBILITY_RULE}")
    st.caption(f"Owner: {m.OWNER}")

st.divider()
st.subheader("Worked answer with full trust panel")

if metric_name == "On-Time Delivery Rate":
    suppliers = run(f"""
        SELECT s.CANONICAL_SUPPLIER_ID, s.SUPPLIER_NAME, m.ELIGIBLE_SHIPMENTS, m.ON_TIME_SHIPMENTS, m.OTD_PCT
        FROM {DB}.SEMANTIC_LAYER.METRIC_OTD_BY_SUPPLIER m
        JOIN {DB}.ONTOLOGY_CORE.SUPPLIER s ON s.CANONICAL_SUPPLIER_ID = m.SUPPLIER_ID
        WHERE m.ELIGIBLE_SHIPMENTS > 0 ORDER BY s.SUPPLIER_NAME""")
    pick = st.selectbox("Supplier", suppliers.SUPPLIER_NAME.tolist())
    r = suppliers[suppliers.SUPPLIER_NAME == pick].iloc[0]
    c1, c2, c3 = st.columns(3)
    c1.metric("OTD", f"{r.OTD_PCT:.1f}%")
    c2.metric("Eligible shipments", int(r.ELIGIBLE_SHIPMENTS))
    c3.metric("On-time shipments", int(r.ON_TIME_SHIPMENTS))
    st.markdown("""
| Trust field | Value |
|---|---|
| **Source systems** | RAW_LOGISTICS.SHIPMENTS + SHIPMENT_EVENTS (timezone-normalized) + ONTOLOGY_CORE.ORDERS (ERP A + ERP B) |
| **Lineage** | Supplier → Order (PURCHASE) → Shipment → Shipment Event (DELIVERED, UTC-normalized) |
| **Filters** | `direction = INBOUND`, `supplier = selected` |
""")
    sid = r.CANONICAL_SUPPLIER_ID
    st.caption("Mapping confidence of contributing source fields:")
    contrib = run(f"""SELECT SOURCE_SYSTEM, SOURCE_TABLE, SOURCE_COLUMN, CANONICAL_ATTRIBUTE, CONFIDENCE_SCORE, APPROVAL_STATUS
                      FROM {DB}.GOVERNANCE.MAPPING_REGISTRY
                      WHERE CANONICAL_ATTRIBUTE IN ('supplier_id','promised_delivery_date','order_id')""")
    st.dataframe(contrib, use_container_width=True, hide_index=True)
    weakest = contrib.CONFIDENCE_SCORE.min()
    if weakest < 90:
        st.warning(f"⚠️ Lowest contributing mapping confidence is {weakest:.1f}% — answer confidence is bounded by it. "
                   "See Human Review for pending mappings.")

elif metric_name == "Fill Rate":
    df = run(f"""SELECT s.SUPPLIER_NAME, f.TOTAL_QUANTITY_ORDERED, f.TOTAL_QUANTITY_DELIVERED, f.FILL_RATE_PCT,
                        f.LINES_WITH_MISSING_PROMISE_DATE
                 FROM {DB}.SEMANTIC_LAYER.METRIC_FILL_RATE_BY_SUPPLIER f
                 JOIN {DB}.ONTOLOGY_CORE.SUPPLIER s ON s.CANONICAL_SUPPLIER_ID = f.SUPPLIER_ID ORDER BY s.SUPPLIER_NAME""")
    st.dataframe(df, use_container_width=True, hide_index=True)
    st.warning("Data-quality caveat: in this synthetic dataset, many PO lines have no linked fulfilling shipment, "
               "which deflates Fill Rate. The formula is correct; the absolute number is a demo artifact.")

elif metric_name == "Days of Inventory":
    df = run(f"""SELECT p.PRODUCT_NAME, pl.PLANT_NAME, d.QUANTITY_ON_HAND, d.AVG_DAILY_DEMAND, d.DAYS_OF_INVENTORY
                 FROM {DB}.SEMANTIC_LAYER.METRIC_DAYS_OF_INVENTORY d
                 JOIN {DB}.ONTOLOGY_CORE.PRODUCT p ON p.CANONICAL_PRODUCT_ID = d.PRODUCT_ID
                 JOIN {DB}.ONTOLOGY_CORE.PLANT pl ON pl.CANONICAL_PLANT_ID = d.PLANT_ID
                 ORDER BY d.DAYS_OF_INVENTORY DESC NULLS LAST LIMIT 50""")
    st.dataframe(df, use_container_width=True, hide_index=True)
    st.caption("NULL Days of Inventory means no demand in the trailing 90 days — shown as NULL, never as 0 or infinity.")

else:  # Landed Cost
    df = run(f"""SELECT p.PRODUCT_NAME, s.SUPPLIER_NAME, l.AVG_UNIT_PRICE, l.FREIGHT_PCT, l.DUTY_PCT, l.HANDLING_PCT,
                        l.USED_DEFAULT_CONFIG, l.LANDED_COST_ESTIMATE
                 FROM {DB}.SEMANTIC_LAYER.METRIC_LANDED_COST_BY_PRODUCT l
                 JOIN {DB}.ONTOLOGY_CORE.PRODUCT p ON p.CANONICAL_PRODUCT_ID = l.PRODUCT_ID
                 JOIN {DB}.ONTOLOGY_CORE.SUPPLIER s ON s.CANONICAL_SUPPLIER_ID = l.SUPPLIER_ID
                 ORDER BY p.PRODUCT_NAME LIMIT 50""")
    st.dataframe(df, use_container_width=True, hide_index=True)
    st.caption("⚠️ ESTIMATE — percent-of-cost model, not actual freight invoices. Rows with USED_DEFAULT_CONFIG = TRUE fell back to default rates.")

st.divider()
st.subheader("Timezone check (Test 3)")
tz = run(f"SELECT COUNT(*) AS MISORDERED FROM {DB}.GOVERNANCE.SHIPMENT_EVENT_TIMELINE WHERE CORRECT_SEQUENCE != SOURCE_RECORDED_SEQUENCE")
n = int(tz.MISORDERED[0]) if not tz.empty else 0
st.metric("Shipment events whose UTC order differs from source-recorded order", n)
st.caption("Nonzero means naive local-time ordering would have misordered events — exactly what UTC normalization prevents.")
