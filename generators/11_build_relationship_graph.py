"""
Dependency / relationship graph: a single generic edge list spanning the
whole ontology (core + Goods + Manufacturing + Services). This is what
Phase 4 (Dependency Graph, Impact Analysis) and the Ontology Explorer /
Impact Analysis Streamlit pages traverse - both forward and backward,
since every edge is stored once and can be queried in either direction.

Edge shape: (FROM_TYPE, FROM_ID, RELATIONSHIP, TO_TYPE, TO_ID)
"""
import os
import pandas as pd

SRC = "./csv"
OUT = "./csv/ontology_graph"
os.makedirs(OUT, exist_ok=True)

supplier = pd.read_csv(f"{SRC}/ontology_core/supplier.csv", dtype=str)
product = pd.read_csv(f"{SRC}/ontology_core/product.csv", dtype=str)
plant = pd.read_csv(f"{SRC}/ontology_core/plant.csv", dtype=str)
customer = pd.read_csv(f"{SRC}/ontology_core/customer.csv", dtype=str)
order = pd.read_csv(f"{SRC}/ontology_core/order.csv", dtype=str)
order_line = pd.read_csv(f"{SRC}/ontology_core/order_line.csv", dtype=str)
contract = pd.read_csv(f"{SRC}/ontology_core/contract.csv", dtype=str)
shipments = pd.read_csv(f"{SRC}/logistics/shipments.csv", dtype=str)
warehouse = pd.read_csv(f"{SRC}/ontology_goods/warehouse.csv", dtype=str)
inventory = pd.read_csv(f"{SRC}/ontology_goods/inventory.csv", dtype=str)
bom = pd.read_csv(f"{SRC}/ontology_manufacturing/bill_of_materials.csv", dtype=str)
prod_line = pd.read_csv(f"{SRC}/ontology_manufacturing/production_line.csv", dtype=str)
prod_order = pd.read_csv(f"{SRC}/ontology_manufacturing/production_order.csv", dtype=str)

edges = []
def add(from_type, from_id, rel, to_type, to_id):
    if pd.isna(from_id) or pd.isna(to_id) or from_id == "" or to_id == "":
        return
    edges.append({"FROM_TYPE": from_type, "FROM_ID": from_id, "RELATIONSHIP": rel,
                  "TO_TYPE": to_type, "TO_ID": to_id})

# Supplier -> fulfills -> Order (purchase orders only)
for _, o in order[order.ORDER_TYPE == "PURCHASE"].iterrows():
    add("SUPPLIER", o.SUPPLIER_ID, "fulfills", "ORDER", o.CANONICAL_ORDER_ID)

# Order -> contains -> Product  (via order lines)
for _, li in order_line.iterrows():
    add("ORDER", li.CANONICAL_ORDER_ID, "contains", "PRODUCT", li.PRODUCT_ID)

# Order -> belongs_to -> Customer (sales orders)
for _, o in order[order.ORDER_TYPE == "SALES"].iterrows():
    add("ORDER", o.CANONICAL_ORDER_ID, "belongs_to", "CUSTOMER", o.CUSTOMER_ID)

# Order -> fulfilled_at -> Plant
for _, o in order.iterrows():
    if pd.notna(o.PLANT_ID) and o.PLANT_ID != "":
        add("ORDER", o.CANONICAL_ORDER_ID, "fulfilled_at", "PLANT", o.PLANT_ID)

# Supplier -> supplies -> Product (derived: any product a supplier's PO lines contain)
po_lines_with_supplier = order_line.merge(order[order.ORDER_TYPE == "PURCHASE"][["CANONICAL_ORDER_ID", "SUPPLIER_ID"]],
                                          on="CANONICAL_ORDER_ID", how="inner")
for _, r in po_lines_with_supplier.drop_duplicates(subset=["SUPPLIER_ID", "PRODUCT_ID"]).iterrows():
    add("SUPPLIER", r.SUPPLIER_ID, "supplies", "PRODUCT", r.PRODUCT_ID)

# Contract -> governs -> Supplier
for _, c in contract.iterrows():
    add("CONTRACT", c.CANONICAL_CONTRACT_ID, "governs", "SUPPLIER", c.SUPPLIER_ID)

# Shipment -> fulfills -> Order  (REFERENCE_DOC is the source doc id; map back to canonical order id)
order_by_source = {(row.SOURCE_SYSTEM, str(row.SOURCE_DOC_ID)): row.CANONICAL_ORDER_ID for _, row in order.iterrows()}
for _, s in shipments.iterrows():
    key = (s.SOURCE_ERP, str(s.REFERENCE_DOC))
    canon_order = order_by_source.get(key)
    if canon_order:
        add("SHIPMENT", s.SHIPMENT_ID, "fulfills", "ORDER", canon_order)
        # Shipment -> transports -> Product  (all products on that order)
        for pid in order_line[order_line.CANONICAL_ORDER_ID == canon_order].PRODUCT_ID.unique():
            add("SHIPMENT", s.SHIPMENT_ID, "transports", "PRODUCT", pid)
        # Customer -> receives -> Shipment (outbound only)
        ord_row = order[order.CANONICAL_ORDER_ID == canon_order].iloc[0]
        if s.DIRECTION == "OUTBOUND" and pd.notna(ord_row.CUSTOMER_ID) and ord_row.CUSTOMER_ID != "":
            add("CUSTOMER", ord_row.CUSTOMER_ID, "receives", "SHIPMENT", s.SHIPMENT_ID)

# Product -> stored_at -> Warehouse ; Product -> produced_at -> Plant (via manufacturing)
for _, inv in inventory.drop_duplicates(subset=["CANONICAL_PRODUCT_ID", "CANONICAL_WAREHOUSE_ID"]).iterrows():
    add("PRODUCT", inv.CANONICAL_PRODUCT_ID, "stored_at", "WAREHOUSE", inv.CANONICAL_WAREHOUSE_ID)

warehouse_to_plant = dict(zip(warehouse.CANONICAL_WAREHOUSE_ID, warehouse.PLANT_ID))
for wh_id, plant_id in warehouse_to_plant.items():
    add("WAREHOUSE", wh_id, "located_at", "PLANT", plant_id)

# Plant -> produces -> Product (finished goods, via production orders)
for _, po in prod_order.drop_duplicates(subset=["PLANT_ID", "FINISHED_GOOD_PRODUCT_ID"]).iterrows():
    add("PLANT", po.PLANT_ID, "produces", "PRODUCT", po.FINISHED_GOOD_PRODUCT_ID)
    add("PRODUCT", po.FINISHED_GOOD_PRODUCT_ID, "manufactured_at", "PLANT", po.PLANT_ID)

# Production Order -> uses_line -> Production Line ; Production Line -> located_at -> Plant
for _, po in prod_order.iterrows():
    add("PRODUCTION_ORDER", po.CANONICAL_PRODUCTION_ORDER_ID, "uses_line", "PRODUCTION_LINE", po.PRODUCTION_LINE_ID)
for _, pl in prod_line.iterrows():
    add("PRODUCTION_LINE", pl.CANONICAL_PRODUCTION_LINE_ID, "located_at", "PLANT", pl.PLANT_ID)

# Bill of Materials: FinishedGood -> requires -> RawMaterial (Product-to-Product dependency;
# this is the key edge that lets impact analysis trace "delayed raw material -> affected finished good")
for _, b in bom.iterrows():
    add("PRODUCT", b.FINISHED_GOOD_PRODUCT_ID, "requires", "PRODUCT", b.RAW_MATERIAL_PRODUCT_ID)

# Production Order -> produces -> FinishedGood Product
for _, po in prod_order.iterrows():
    add("PRODUCTION_ORDER", po.CANONICAL_PRODUCTION_ORDER_ID, "produces", "PRODUCT", po.FINISHED_GOOD_PRODUCT_ID)

edge_df = pd.DataFrame(edges).drop_duplicates()
edge_df.to_csv(f"{OUT}/relationship_edges.csv", index=False)

print("Total edges:", len(edge_df))
print(edge_df.groupby(["FROM_TYPE", "RELATIONSHIP", "TO_TYPE"]).size().sort_values(ascending=False))
