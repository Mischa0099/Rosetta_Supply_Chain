"""
Schema Mapping (spec section 22, page 4). Source field -> Canonical field
-> Confidence -> Approval status, with drill-in detail.
"""
import streamlit as st
from common import DB, run, page_header, confidence_badge

st.set_page_config(page_title="Schema Mapping", page_icon="🔗", layout="wide")
page_header("🔗 Schema Mapping", "AI-proposed mappings from every source column to the canonical ontology, with confidence-based governance.")

registry = run(f"SELECT * FROM {DB}.GOVERNANCE.MAPPING_REGISTRY ORDER BY SOURCE_SYSTEM, SOURCE_TABLE, CONFIDENCE_SCORE DESC")

c1, c2, c3 = st.columns(3)
c1.metric("Total mappings", len(registry))
c2.metric("Auto-approved", int((registry.APPROVAL_STATUS.isin(["AUTO_APPROVED", "APPROVED"])).sum()))
c3.metric("Needing attention", int((registry.APPROVAL_STATUS.isin(["PENDING_REVIEW", "NEEDS_CLARIFICATION"])).sum()))

st.divider()

source_filter = st.multiselect("Source system", sorted(registry.SOURCE_SYSTEM.unique()), default=list(registry.SOURCE_SYSTEM.unique()))
status_filter = st.multiselect("Approval status", sorted(registry.APPROVAL_STATUS.unique()), default=list(registry.APPROVAL_STATUS.unique()))

filtered = registry[registry.SOURCE_SYSTEM.isin(source_filter) & registry.APPROVAL_STATUS.isin(status_filter)].copy()
filtered["CONFIDENCE"] = filtered.CONFIDENCE_SCORE.apply(confidence_badge)

st.dataframe(
    filtered[["MAPPING_ID", "SOURCE_SYSTEM", "SOURCE_TABLE", "SOURCE_COLUMN", "CANONICAL_ENTITY",
              "CANONICAL_ATTRIBUTE", "CONFIDENCE", "APPROVAL_STATUS"]],
    use_container_width=True, hide_index=True, height=420,
)

st.divider()
st.subheader("Inspect / act on a mapping")
mapping_id = st.selectbox("Mapping ID", filtered.MAPPING_ID.tolist())
row = registry[registry.MAPPING_ID == mapping_id].iloc[0]

col1, col2 = st.columns([2, 1])
with col1:
    st.markdown(f"**{row.SOURCE_SYSTEM}.{row.SOURCE_TABLE}.{row.SOURCE_COLUMN}** → **{row.CANONICAL_ENTITY}.{row.CANONICAL_ATTRIBUTE}**")
    st.write(row.RATIONALE)
    st.caption(f"Transformation: {row.TRANSFORMATION} · Version {row.MAPPING_VERSION} · Confidence {confidence_badge(row.CONFIDENCE_SCORE)}")
with col2:
    st.metric("Status", row.APPROVAL_STATUS)

reviewer = st.text_input("Your name/email (reviewer identity)", placeholder="jane.procurement@company.com")
b1, b2, b3 = st.columns(3)
if b1.button("✅ Approve", disabled=not reviewer):
    from common import call_scalar_proc
    msg = call_scalar_proc(f"CALL {DB}.GOVERNANCE.APPROVE_MAPPING('{mapping_id}', '{reviewer}')")
    st.success(msg)
    st.rerun()
if b2.button("❌ Reject", disabled=not reviewer):
    reason = st.session_state.get("reject_reason", "No reason given")
    from common import call_scalar_proc
    msg = call_scalar_proc(f"CALL {DB}.GOVERNANCE.REJECT_MAPPING('{mapping_id}', '{reviewer}', '{reason}')")
    st.success(msg)
    st.rerun()
with b3.popover("✏️ Modify"):
    new_entity = st.text_input("New canonical entity", value=row.CANONICAL_ENTITY)
    new_attr = st.text_input("New canonical attribute", value=row.CANONICAL_ATTRIBUTE)
    if st.button("Save modification", disabled=not reviewer):
        from common import call_scalar_proc
        msg = call_scalar_proc(f"CALL {DB}.GOVERNANCE.MODIFY_MAPPING('{mapping_id}', '{reviewer}', '{new_entity}', '{new_attr}')")
        st.success(msg)
        st.rerun()
