"""
Adaptive Supply Chain Intelligence & Governed Conversational Analytics
Home page: Executive Control Tower (spec section 22, page 1).
"""
import streamlit as st
from common import DB, run, page_header, confidence_badge

st.set_page_config(page_title="Supply Chain Control Tower", page_icon="🏭", layout="wide")
page_header("🏭 Executive Control Tower",
            "Governed KPIs, active exceptions, and estimated impact - one connected view across Planning, Procurement, and Logistics.")

# ---------------------------------------------------------------
# Headline KPIs - every number here reads from the SAME governed views
# every persona page reads from (SEMANTIC_LAYER.METRIC_*).
# ---------------------------------------------------------------
otd_df = run(f"SELECT AVG(OTD_PCT) AS AVG_OTD, SUM(ELIGIBLE_SHIPMENTS) AS ELIGIBLE FROM {DB}.SEMANTIC_LAYER.METRIC_OTD_BY_SUPPLIER")
fill_df = run(f"SELECT AVG(FILL_RATE_PCT) AS AVG_FILL FROM {DB}.SEMANTIC_LAYER.METRIC_FILL_RATE_BY_SUPPLIER")
doi_df = run(f"SELECT AVG(DAYS_OF_INVENTORY) AS AVG_DOI FROM {DB}.SEMANTIC_LAYER.METRIC_DAYS_OF_INVENTORY WHERE DAYS_OF_INVENTORY IS NOT NULL")
lc_df = run(f"SELECT AVG(LANDED_COST_ESTIMATE) AS AVG_LC FROM {DB}.SEMANTIC_LAYER.METRIC_LANDED_COST_BY_PRODUCT")

c1, c2, c3, c4 = st.columns(4)
c1.metric("On-Time Delivery (avg across suppliers)", f"{otd_df.AVG_OTD[0]:.1f}%" if not otd_df.empty else "n/a")
c2.metric("Fill Rate (avg across suppliers)", f"{fill_df.AVG_FILL[0]:.1f}%" if not fill_df.empty else "n/a")
c3.metric("Days of Inventory (avg)", f"{doi_df.AVG_DOI[0]:.0f} days" if not doi_df.empty else "n/a")
c4.metric("Landed Cost (avg, ESTIMATE)", f"${lc_df.AVG_LC[0]:.2f}" if not lc_df.empty else "n/a")

st.divider()

# ---------------------------------------------------------------
# Active exceptions
# ---------------------------------------------------------------
st.subheader("🚨 Active Exceptions")
exceptions = run(f"""
    SELECT EXCEPTION_ID, SHIPMENT_ID, EXCEPTION_TYPE, DETECTED_AT, DETAILS, STATUS
    FROM {DB}.INTELLIGENCE.OPEN_EXCEPTIONS WHERE STATUS = 'OPEN' ORDER BY DETECTED_AT DESC LIMIT 25
""")
if exceptions.empty:
    st.info("No open exceptions. (Exceptions are opened automatically by PROCESS_SHIPMENT_DELAY_EVENTS when a DELAYED event lands - see sql/19.)")
else:
    st.dataframe(exceptions, use_container_width=True, hide_index=True)
    st.caption("Go to **Impact Analysis** to trace the downstream effect and estimated cost of any of these.")

st.divider()

# ---------------------------------------------------------------
# Delayed / at-risk shipments, quick view
# ---------------------------------------------------------------
st.subheader("📦 Currently Delayed or At-Risk Shipments")
delayed = run(f"""
    SELECT SHIPMENT_ID, SOURCE_ERP, DIRECTION, CARRIER_ID, PROMISED_DELIVERY_DATE, STATUS
    FROM {DB}.RAW_LOGISTICS.SHIPMENTS WHERE STATUS IN ('DELAYED', 'IN_TRANSIT') ORDER BY PROMISED_DELIVERY_DATE ASC LIMIT 25
""")
st.dataframe(delayed, use_container_width=True, hide_index=True)

st.divider()
st.subheader("🗺️ Governance snapshot")
g1, g2, g3 = st.columns(3)
mreg = run(f"SELECT APPROVAL_STATUS, COUNT(*) AS N FROM {DB}.GOVERNANCE.MAPPING_REGISTRY GROUP BY APPROVAL_STATUS")
with g1:
    st.caption("Schema mappings by status")
    st.dataframe(mreg, hide_index=True, use_container_width=True)
drift = run(f"SELECT COUNT(*) AS N FROM {DB}.INTELLIGENCE.UNACKNOWLEDGED_SCHEMA_DRIFT")
with g2:
    st.metric("Unacknowledged schema drift events", int(drift.N[0]) if not drift.empty else 0)
contracts = run(f"SELECT EXTRACTION_STATUS, COUNT(*) AS N FROM {DB}.ONTOLOGY_CORE.CONTRACT GROUP BY EXTRACTION_STATUS")
with g3:
    st.caption("Contracts by extraction status")
    st.dataframe(contracts, hide_index=True, use_container_width=True)

st.caption("Use the sidebar to open Conversational Analytics, the Ontology Explorer, Schema Mapping, Impact Analysis, Data/Metric Lineage, or Human Review.")
