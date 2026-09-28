"""
Ontology Explorer (spec section 22, page 3). Visualize
Supplier -> Part -> Plant -> Shipment -> Order -> Customer and traverse
the dependency graph in either direction.
"""
import streamlit as st
from common import DB, run, page_header

st.set_page_config(page_title="Ontology Explorer", page_icon="🕸️", layout="wide")
page_header("🕸️ Ontology Explorer", "Browse the canonical ontology and traverse the dependency graph in either direction.")

tab1, tab2 = st.tabs(["Static ontology diagram", "Live graph traversal"])

with tab1:
    st.graphviz_chart("""
    digraph {
        rankdir=LR;
        node [shape=box, style="rounded,filled", fillcolor="#eef2ff", fontname="Helvetica"];
        Supplier -> Product [label="supplies"];
        Supplier -> Order [label="fulfills"];
        Order -> Product [label="contains"];
        Order -> Plant [label="fulfilled_at"];
        Order -> Customer [label="belongs_to"];
        Shipment -> Order [label="fulfills"];
        Shipment -> Product [label="transports"];
        Customer -> Shipment [label="receives"];
        Contract -> Supplier [label="governs"];
        Product -> Warehouse [label="stored_at"];
        Warehouse -> Plant [label="located_at"];
        Plant -> Product [label="produces"];
        Product -> Product [label="requires (BOM)"];
        ProductionOrder -> Product [label="produces"];
        ProductionLine -> Plant [label="located_at"];
    }
    """)
    st.caption("Full detail (including the Manufacturing and Services adaptive modules) in docs/ontology_diagram.md.")

with tab2:
    col1, col2, col3 = st.columns(3)
    entity_type = col1.selectbox("Entity type", ["SUPPLIER", "PRODUCT", "PLANT", "CUSTOMER", "ORDER", "SHIPMENT"])
    entity_table = {"SUPPLIER": "SUPPLIER", "PRODUCT": "PRODUCT", "PLANT": "PLANT", "CUSTOMER": "CUSTOMER"}
    if entity_type in entity_table:
        id_col = f"CANONICAL_{entity_type}_ID"
        name_col = {"SUPPLIER": "SUPPLIER_NAME", "PRODUCT": "PRODUCT_NAME", "PLANT": "PLANT_NAME", "CUSTOMER": "CUSTOMER_NAME"}[entity_type]
        options = run(f"SELECT {id_col}, {name_col} FROM {DB}.ONTOLOGY_CORE.{entity_table[entity_type]} ORDER BY {name_col}")
        label_map = dict(zip(options[name_col], options[id_col]))
        picked_name = col2.selectbox("Entity", list(label_map.keys()))
        entity_id = label_map[picked_name]
    else:
        entity_id = col2.text_input("Entity ID", placeholder="e.g. SHP-100001 or ORD-A-PO-4500000129")

    direction = col3.radio("Direction", ["FORWARD", "BACKWARD"], horizontal=True,
                           help="FORWARD: what does this entity lead to? BACKWARD: what leads to this entity?")
    max_hops = st.slider("Max hops", 1, 6, 3)

    if st.button("Traverse", type="primary") and entity_id:
        result = run(f"CALL {DB}.INTELLIGENCE.TRAVERSE_GRAPH('{entity_type}', '{entity_id}', '{direction}', {max_hops})")
        if result.empty:
            st.info("No connected entities found within that hop limit.")
        else:
            st.dataframe(result, use_container_width=True, hide_index=True)
            st.caption(f"{len(result)} connected entities found, up to {max_hops} hops {direction.lower()} from {entity_id}.")
