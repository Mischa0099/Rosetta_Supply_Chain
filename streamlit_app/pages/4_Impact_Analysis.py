"""
Impact Analysis (spec section 17-18, 22 page 5). Select a shipment and a
delay duration, see downstream affected entities and an ESTIMATED
financial impact. Thin UI over IMPACT_ANALYSIS_SHIPMENT() and
FINANCIAL_IMPACT_ESTIMATE() - no impact logic lives in this file.
"""
import streamlit as st
from common import DB, run, page_header

st.set_page_config(page_title="Impact Analysis", page_icon="💥", layout="wide")
page_header("💥 Impact Analysis", "Pick a shipment, set a delay, see what it touches and what it might cost. All financial figures are ESTIMATES.")

shipments = run(f"""
    SELECT SHIPMENT_ID, STATUS, DIRECTION, PROMISED_DELIVERY_DATE
    FROM {DB}.RAW_LOGISTICS.SHIPMENTS
    WHERE STATUS IN ('DELAYED', 'IN_TRANSIT') AND DIRECTION = 'INBOUND'
    ORDER BY PROMISED_DELIVERY_DATE
""")
if shipments.empty:
    st.info("No delayed/in-transit inbound shipments found.")
    st.stop()

col1, col2 = st.columns([2, 1])
shipment_id = col1.selectbox(
    "Shipment", shipments.SHIPMENT_ID.tolist(),
    format_func=lambda s: f"{s} — {shipments[shipments.SHIPMENT_ID == s].STATUS.iloc[0]}, promised {shipments[shipments.SHIPMENT_ID == s].PROMISED_DELIVERY_DATE.iloc[0]}")
delay_days = col2.slider("Delay (days)", 1, 21, 4)

if st.button("Run impact analysis", type="primary"):
    impact = run(f"SELECT * FROM TABLE({DB}.INTELLIGENCE.IMPACT_ANALYSIS_SHIPMENT('{shipment_id}'))")
    financial = run(f"SELECT * FROM TABLE({DB}.INTELLIGENCE.FINANCIAL_IMPACT_ESTIMATE('{shipment_id}', {delay_days}))")

    if impact.empty:
        st.warning("No downstream entities found for this shipment - it may not be linked to an order in the ontology graph.")
        st.stop()

    counts = impact.groupby("IMPACT_CATEGORY").ENTITY_ID.nunique()
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Delay", f"{delay_days} days")
    m2.metric("Affected plants", int(counts.get("AFFECTED_PLANT", 0)))
    m3.metric("Production orders", int(counts.get("AFFECTED_PRODUCTION_ORDER", 0)))
    m4.metric("Affected orders", int(counts.get("AFFECTED_ORDER", 0)))
    m5.metric("Affected customers", int(counts.get("AFFECTED_CUSTOMER", 0)))

    st.divider()

    left, right = st.columns([3, 2])
    with left:
        st.subheader("Downstream chain")
        # Visual: Shipment -> Products -> Plant -> Production Orders -> Orders -> Customers
        def names(cat, limit=4):
            rows = impact[impact.IMPACT_CATEGORY == cat].ENTITY_NAME.tolist()
            more = f" +{len(rows) - limit} more" if len(rows) > limit else ""
            return "\\n".join(rows[:limit]) + more if rows else "(none)"
        st.graphviz_chart(f"""
        digraph {{
            rankdir=LR; node [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=10];
            S [label="Shipment\\n{shipment_id}", fillcolor="#fee2e2"];
            P [label="Products\\n{names('DIRECT_PRODUCT')}", fillcolor="#fef3c7"];
            FG [label="Finished goods\\n{names('DOWNSTREAM_FINISHED_GOOD')}", fillcolor="#fef3c7"];
            PL [label="Plant\\n{names('AFFECTED_PLANT')}", fillcolor="#dbeafe"];
            PO [label="Production orders\\n{names('AFFECTED_PRODUCTION_ORDER', 3)}", fillcolor="#dbeafe"];
            O [label="Orders\\n{int(counts.get('AFFECTED_ORDER', 0))} affected", fillcolor="#dcfce7"];
            C [label="Customers\\n{names('AFFECTED_CUSTOMER')}", fillcolor="#dcfce7"];
            S -> P -> FG -> PL -> PO -> O -> C;
        }}
        """)
    with right:
        st.subheader("Estimated financial impact")
        st.caption("⚠️ ESTIMATE — configurable-rate model, not an accounting figure.")
        st.dataframe(financial, use_container_width=True, hide_index=True)
        total = financial.ESTIMATED_AMOUNT.sum()
        st.metric("Estimated total impact (ESTIMATE)", f"${total:,.0f}")

    with st.expander("All affected entities (detail)"):
        st.dataframe(impact, use_container_width=True, hide_index=True)

    with st.expander("How this was computed"):
        st.markdown("""
Traversal is scoped to the shipment's **destination plant** (Shipment → fulfills → Order → fulfilled_at → Plant),
so a raw-material delay only affects the plant it was headed to - not every plant that buys the same category
of part. Rates come from `INTELLIGENCE.FINANCIAL_IMPACT_CONFIG`; order value uses each product's average
purchase price as a proxy because sales-order lines carry no price in this dataset.
""")
