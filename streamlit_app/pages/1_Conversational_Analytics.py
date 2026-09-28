"""
Conversational Analytics (spec section 12, 22 page 2). Natural-language
questions against the governed semantic layer - never against raw ERP
columns. Primary path: Cortex Analyst on SUPPLY_CHAIN_SEMANTIC_VIEW.
Fallback path (if Cortex Analyst isn't enabled on this account): pattern-
match common question shapes onto the same governed metric views used
everywhere else in the app, so the app still works end-to-end.
"""
import json
import re
import streamlit as st
from common import DB, run, get_session, page_header

st.set_page_config(page_title="Conversational Analytics", page_icon="💬", layout="wide")
page_header("💬 Conversational Analytics",
            "Ask a question the way Planning, Procurement, or Logistics would. Every answer traces back to a governed metric definition - see the Trust Panel under each response.")

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

with st.expander("Example questions (persona wording, same governed metrics)"):
    st.markdown("""
- *Planning:* "What is Supplier Shenzhen Circuit Solutions's delivery reliability?"
- *Procurement:* "What is Shenzhen Circuit Solutions's OTD?"
- *Logistics:* "How many Shenzhen Circuit Solutions shipments were delivered on time?"
- "What is our landed cost for Heavy-Duty Steel Bracket?"
- "What plants are experiencing inventory risk?"
- "What happens if Shipment SHP-100001 is delayed by another 4 days?"
""")


def try_cortex_analyst(question: str):
    """Primary path: Cortex Analyst REST API against the semantic view.
    Returns None if Cortex Analyst isn't available/enabled, so the caller
    can fall back gracefully rather than erroring the whole page."""
    session = get_session()
    try:
        # Cortex Analyst is invoked via REST (_snowflake internal helper
        # inside Streamlit-in-Snowflake) rather than a SQL function.
        import _snowflake
        request_body = {
            "messages": [{"role": "user", "content": [{"type": "text", "text": question}]}],
            "semantic_view": f"{DB}.SEMANTIC_LAYER.SUPPLY_CHAIN_SEMANTIC_VIEW",
        }
        resp = _snowflake.send_snow_api_request(
            "POST", "/api/v2/cortex/analyst/message", {}, {}, request_body, {}, 30000)
        if resp["status"] != 200:
            return None
        content = json.loads(resp["content"])
        return content
    except Exception:
        return None


def fallback_router(question: str):
    """Pattern-match the question onto a governed view + filter. This is
    intentionally simple (not a general NL engine) - it exists so the demo
    works even without Cortex Analyst enabled, using the EXACT same views
    everything else in the app uses."""
    q = question.lower()

    supplier_match = run(f"SELECT CANONICAL_SUPPLIER_ID, SUPPLIER_NAME FROM {DB}.ONTOLOGY_CORE.SUPPLIER")
    for _, row in supplier_match.iterrows():
        if row.SUPPLIER_NAME.lower() in q:
            if any(k in q for k in ["otd", "on-time", "on time", "reliability", "delivered on time"]):
                df = run(f"""SELECT s.SUPPLIER_NAME, m.ELIGIBLE_SHIPMENTS, m.ON_TIME_SHIPMENTS, m.OTD_PCT
                             FROM {DB}.SEMANTIC_LAYER.METRIC_OTD_BY_SUPPLIER m
                             JOIN {DB}.ONTOLOGY_CORE.SUPPLIER s ON s.CANONICAL_SUPPLIER_ID = m.SUPPLIER_ID
                             WHERE m.SUPPLIER_ID = '{row.CANONICAL_SUPPLIER_ID}'""")
                return "on_time_delivery_rate", df
            if "fill rate" in q:
                df = run(f"""SELECT s.SUPPLIER_NAME, m.* FROM {DB}.SEMANTIC_LAYER.METRIC_FILL_RATE_BY_SUPPLIER m
                             JOIN {DB}.ONTOLOGY_CORE.SUPPLIER s ON s.CANONICAL_SUPPLIER_ID = m.SUPPLIER_ID
                             WHERE m.SUPPLIER_ID = '{row.CANONICAL_SUPPLIER_ID}'""")
                return "fill_rate", df

    product_match = run(f"SELECT CANONICAL_PRODUCT_ID, PRODUCT_NAME FROM {DB}.ONTOLOGY_CORE.PRODUCT")
    for _, row in product_match.iterrows():
        if row.PRODUCT_NAME.lower() in q and "landed cost" in q:
            df = run(f"""SELECT p.PRODUCT_NAME, s.SUPPLIER_NAME, m.LANDED_COST_ESTIMATE
                         FROM {DB}.SEMANTIC_LAYER.METRIC_LANDED_COST_BY_PRODUCT m
                         JOIN {DB}.ONTOLOGY_CORE.PRODUCT p ON p.CANONICAL_PRODUCT_ID = m.PRODUCT_ID
                         JOIN {DB}.ONTOLOGY_CORE.SUPPLIER s ON s.CANONICAL_SUPPLIER_ID = m.SUPPLIER_ID
                         WHERE m.PRODUCT_ID = '{row.CANONICAL_PRODUCT_ID}'""")
            return "landed_cost", df

    if "inventory risk" in q or "days of inventory" in q:
        df = run(f"""SELECT p.PRODUCT_NAME, pl.PLANT_NAME, d.QUANTITY_ON_HAND, d.DAYS_OF_INVENTORY
                     FROM {DB}.SEMANTIC_LAYER.METRIC_DAYS_OF_INVENTORY d
                     JOIN {DB}.ONTOLOGY_CORE.PRODUCT p ON p.CANONICAL_PRODUCT_ID = d.PRODUCT_ID
                     JOIN {DB}.ONTOLOGY_CORE.PLANT pl ON pl.CANONICAL_PLANT_ID = d.PLANT_ID
                     WHERE d.DAYS_OF_INVENTORY IS NOT NULL
                     ORDER BY d.DAYS_OF_INVENTORY DESC LIMIT 10""")
        return "days_of_inventory", df

    shipment_match = re.search(r"(SHP-\d+)", question, re.IGNORECASE)
    delay_match = re.search(r"(\d+)\s*day", question)
    if shipment_match and ("delay" in q or "impact" in q):
        sid = shipment_match.group(1).upper()
        days = int(delay_match.group(1)) if delay_match else 4
        impact = run(f"SELECT * FROM TABLE({DB}.INTELLIGENCE.IMPACT_ANALYSIS_SHIPMENT('{sid}'))")
        financial = run(f"SELECT * FROM TABLE({DB}.INTELLIGENCE.FINANCIAL_IMPACT_ESTIMATE('{sid}', {days}))")
        return "impact_analysis", (impact, financial)

    return None, None


question = st.chat_input("Ask a supply-chain question...")

for msg in st.session_state.chat_history:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

if question:
    st.session_state.chat_history.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.write(question)

    with st.chat_message("assistant"):
        analyst_result = try_cortex_analyst(question)
        if analyst_result:
            st.write(analyst_result)
            metric_name = "cortex_analyst"
        else:
            metric_name, data = fallback_router(question)
            if metric_name is None:
                st.warning("Couldn't confidently route this question to a governed metric. "
                          "Try naming a supplier/product explicitly, or rephrase using OTD, "
                          "fill rate, landed cost, days of inventory, or a shipment ID + delay.")
            elif metric_name == "impact_analysis":
                impact, financial = data
                st.write("**Downstream impact:**")
                st.dataframe(impact, use_container_width=True, hide_index=True)
                st.write("**Estimated financial impact (ESTIMATE, not an accounting figure):**")
                st.dataframe(financial, use_container_width=True, hide_index=True)
            else:
                st.dataframe(data, use_container_width=True, hide_index=True)

        if metric_name and metric_name not in ("cortex_analyst", None):
            with st.expander("🔍 Trust panel — definition, formula, lineage"):
                defn = run(f"SELECT * FROM {DB}.SEMANTIC_LAYER.CANONICAL_METRICS WHERE METRIC_NAME ILIKE '%{metric_name.replace('_', ' ')}%'")
                if not defn.empty:
                    st.dataframe(defn, use_container_width=True, hide_index=True)
                else:
                    st.caption("See docs/impact_analysis_example.md and sql/17-18 for the governed impact-analysis and financial-impact-estimate definitions.")

    st.session_state.chat_history.append({"role": "assistant", "content": f"[{metric_name or 'no match'}]"})
