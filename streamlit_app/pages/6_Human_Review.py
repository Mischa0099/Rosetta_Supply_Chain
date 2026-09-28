"""
Human Review (spec section 8, 22 page 7). Everything the platform refused
to decide on its own: uncertain schema mappings, low-confidence contract
extractions, and unacknowledged schema drift. Nothing here is auto-approved.
"""
import streamlit as st
from common import DB, run, call_scalar_proc, page_header, confidence_badge

st.set_page_config(page_title="Human Review", page_icon="🧑‍⚖️", layout="wide")
page_header("🧑‍⚖️ Human Review", "Decisions the system deliberately did not make on its own.")

reviewer = st.text_input("Your name/email (recorded on every decision)", placeholder="jane.procurement@company.com")

tab1, tab2, tab3 = st.tabs(["Schema mappings", "Contract extractions", "Schema drift"])

# ---------------------------------------------------------------
with tab1:
    queue = run(f"SELECT * FROM {DB}.GOVERNANCE.HUMAN_REVIEW_QUEUE")
    st.caption(f"{len(queue)} mapping(s) awaiting a decision.")
    if queue.empty:
        st.success("Queue is empty.")
    for _, r in queue.iterrows():
        with st.container(border=True):
            st.markdown(f"**{r.SOURCE_SYSTEM}.{r.SOURCE_TABLE}.{r.SOURCE_COLUMN}** → "
                        f"**{r.CANONICAL_ENTITY}.{r.CANONICAL_ATTRIBUTE}**  ·  {confidence_badge(r.CONFIDENCE_SCORE)}")
            st.write(f"*Reason:* {r.RATIONALE}")
            c1, c2, c3 = st.columns(3)
            if c1.button("Approve", key=f"a_{r.MAPPING_ID}", disabled=not reviewer):
                st.success(call_scalar_proc(f"CALL {DB}.GOVERNANCE.APPROVE_MAPPING('{r.MAPPING_ID}', '{reviewer}')"))
                st.rerun()
            reason = c2.text_input("Rejection reason", key=f"rr_{r.MAPPING_ID}", label_visibility="collapsed", placeholder="Reason if rejecting")
            if c2.button("Reject", key=f"r_{r.MAPPING_ID}", disabled=not (reviewer and reason)):
                st.success(call_scalar_proc(f"CALL {DB}.GOVERNANCE.REJECT_MAPPING('{r.MAPPING_ID}', '{reviewer}', '{reason}')"))
                st.rerun()
            with c3.popover("Modify mapping"):
                ne = st.text_input("Entity", value=r.CANONICAL_ENTITY, key=f"ne_{r.MAPPING_ID}")
                na = st.text_input("Attribute", value=r.CANONICAL_ATTRIBUTE, key=f"na_{r.MAPPING_ID}")
                if st.button("Save", key=f"m_{r.MAPPING_ID}", disabled=not reviewer):
                    st.success(call_scalar_proc(f"CALL {DB}.GOVERNANCE.MODIFY_MAPPING('{r.MAPPING_ID}', '{reviewer}', '{ne}', '{na}')"))
                    st.rerun()

# ---------------------------------------------------------------
with tab2:
    contracts = run(f"""SELECT c.CANONICAL_CONTRACT_ID, s.SUPPLIER_NAME, c.SLA_DAYS, c.LEAD_TIME_DAYS, c.DELIVERY_TERM,
                               c.EXTRACTION_CONFIDENCE, c.EXTRACTION_STATUS
                        FROM {DB}.ONTOLOGY_CORE.CONTRACT c
                        LEFT JOIN {DB}.ONTOLOGY_CORE.SUPPLIER s ON s.CANONICAL_SUPPLIER_ID = c.SUPPLIER_ID
                        WHERE c.EXTRACTION_STATUS IN ('PENDING_REVIEW', 'NEEDS_CLARIFICATION', 'PENDING_AI_EXTRACTION')
                        ORDER BY c.EXTRACTION_CONFIDENCE""")
    if contracts.empty:
        st.success("No contract extractions awaiting review.")
    else:
        st.dataframe(contracts, use_container_width=True, hide_index=True)
        st.caption("Rows showing PENDING_AI_EXTRACTION haven't had sql/21 run yet. "
                   "After CALL APPLY_CONTRACT_EXTRACTION(), sub-90% confidence rows land here.")

# ---------------------------------------------------------------
with tab3:
    drift = run(f"SELECT * FROM {DB}.INTELLIGENCE.UNACKNOWLEDGED_SCHEMA_DRIFT")
    if drift.empty:
        st.success("No unacknowledged schema drift.")
    else:
        st.error(f"{len(drift)} schema change(s) detected that may break mappings or metrics.")
        st.dataframe(drift, use_container_width=True, hide_index=True)
        st.caption("AFFECTED_MAPPING_IDS lists registry rows referencing the changed column - re-review those first.")
