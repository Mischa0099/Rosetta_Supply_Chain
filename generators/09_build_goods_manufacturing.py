"""
Adaptive ontology extensions on top of the CORE ontology:
  - GOODS module   : Warehouse, canonical Inventory (unifies ERP A LABST + ERP B QTY_ON_HAND)
  - MANUFACTURING industry extension : Production Line, Bill of Materials,
    Production Order (net-new synthetic data - no source system had these;
    demonstrates that an industry module can be layered on without touching
    the core ontology or the Goods module).
"""
import os, json, random
from datetime import date, timedelta
import pandas as pd

random.seed(606)
SRC = "./csv"
OUT_GOODS = "./csv/ontology_goods"
OUT_MFG = "./csv/ontology_manufacturing"

with open("generators/state/canonical_lookups.json") as f:
    lk = json.load(f)

plant_df = pd.read_csv(f"{SRC}/ontology_core/plant.csv", dtype=str)
product_df = pd.read_csv(f"{SRC}/ontology_core/product.csv", dtype=str)

# =====================================================================
# GOODS MODULE: WAREHOUSE  (one warehouse per plant, matching the
# ERP A storage-location / ERP B warehouse-zone data already in inventory)
# =====================================================================
rows = []
for _, p in plant_df.iterrows():
    rows.append({"CANONICAL_WAREHOUSE_ID": f"WH-{p.CANONICAL_PLANT_ID}", "WAREHOUSE_NAME": f"{p.PLANT_NAME} Warehouse",
                "PLANT_ID": p.CANONICAL_PLANT_ID, "COUNTRY": p.COUNTRY})
warehouse_df = pd.DataFrame(rows)
warehouse_df.to_csv(f"{OUT_GOODS}/warehouse.csv", index=False)

# =====================================================================
# GOODS MODULE: INVENTORY (canonical) - unify ERP A INVENTORY (LABST)
# + ERP B INVENTORY_BALANCES (QTY_ON_HAND) into one governed representation
# =====================================================================
erp_a_inv = pd.read_csv(f"{SRC}/erp_a/inventory.csv", dtype=str)
erp_b_inv = pd.read_csv(f"{SRC}/erp_b/inventory_balances.csv", dtype=str)
rows = []
for _, r in erp_a_inv.iterrows():
    matnr = str(r.MATNR).zfill(8)
    prod_id = lk["erp_a_material_to_canonical"].get(matnr, "")
    plant_id = lk["erp_a_werks_to_canonical"].get(r.WERKS, "")
    if not prod_id or not plant_id:
        continue
    rows.append({"CANONICAL_PRODUCT_ID": prod_id, "CANONICAL_WAREHOUSE_ID": f"WH-{plant_id}",
                "QUANTITY_ON_HAND": r.LABST, "SOURCE_SYSTEM": "ERP_A", "SOURCE_STORAGE_LOCATION": r.LGORT})
for _, r in erp_b_inv.iterrows():
    prod_id = lk["erp_b_sku_to_canonical"].get(r.SKU, "")
    plant_id = lk["erp_b_location_to_canonical"].get(r.LOCATION_CODE, "")
    if not prod_id or not plant_id:
        continue
    rows.append({"CANONICAL_PRODUCT_ID": prod_id, "CANONICAL_WAREHOUSE_ID": f"WH-{plant_id}",
                "QUANTITY_ON_HAND": r.QTY_ON_HAND, "SOURCE_SYSTEM": "ERP_B", "SOURCE_STORAGE_LOCATION": r.WAREHOUSE_ZONE})
inventory_df = pd.DataFrame(rows)
inventory_df.to_csv(f"{OUT_GOODS}/inventory.csv", index=False)
print("warehouse", len(warehouse_df), "inventory", len(inventory_df))

# =====================================================================
# MANUFACTURING INDUSTRY EXTENSION (net-new synthetic data)
# =====================================================================
# Production lines: 2-3 per plant
line_rows = []
for _, p in plant_df.iterrows():
    for k in range(random.randint(2, 3)):
        line_rows.append({"CANONICAL_PRODUCTION_LINE_ID": f"PL-{p.CANONICAL_PLANT_ID}-{k+1:02d}",
                          "PLANT_ID": p.CANONICAL_PLANT_ID, "LINE_NAME": f"Line {k+1}",
                          "CAPACITY_UNITS_PER_DAY": random.randint(200, 3000)})
line_df = pd.DataFrame(line_rows)
line_df.to_csv(f"{OUT_MFG}/production_line.csv", index=False)

# Bill of Materials: pick ~12 products as "finished goods", each consumes 2-4
# other products as "raw materials" (simple synthetic BOM, not physically
# validated - fine for demo purposes)
finished_goods = product_df.sample(min(12, len(product_df)), random_state=11)
raw_material_pool = product_df[~product_df.CANONICAL_PRODUCT_ID.isin(finished_goods.CANONICAL_PRODUCT_ID)]
bom_rows = []
for _, fg in finished_goods.iterrows():
    n_components = random.randint(2, 4)
    components = raw_material_pool.sample(min(n_components, len(raw_material_pool)), random_state=random.randint(1, 9999))
    for _, comp in components.iterrows():
        bom_rows.append({"FINISHED_GOOD_PRODUCT_ID": fg.CANONICAL_PRODUCT_ID,
                         "RAW_MATERIAL_PRODUCT_ID": comp.CANONICAL_PRODUCT_ID,
                         "QUANTITY_PER_UNIT": round(random.uniform(0.5, 5), 2)})
bom_df = pd.DataFrame(bom_rows)
bom_df.to_csv(f"{OUT_MFG}/bill_of_materials.csv", index=False)

# Production orders: tie to a production line + finished good, with a
# planned/actual completion date (feeds impact analysis: a delayed raw
# material shipment can affect a production order, which affects sales orders)
po_rows = []
for i in range(60):
    line = line_df.sample(1, random_state=random.randint(1, 10**6)).iloc[0]
    fg = finished_goods.sample(1, random_state=random.randint(1, 10**6)).iloc[0]
    planned_start = date(2025, 9, 1) + timedelta(days=random.randint(0, 380))
    duration = random.randint(2, 10)
    po_rows.append({
        "CANONICAL_PRODUCTION_ORDER_ID": f"PRD-ORD-{1000+i}",
        "PRODUCTION_LINE_ID": line.CANONICAL_PRODUCTION_LINE_ID, "PLANT_ID": line.PLANT_ID,
        "FINISHED_GOOD_PRODUCT_ID": fg.CANONICAL_PRODUCT_ID,
        "PLANNED_QUANTITY": random.randint(100, 5000),
        "PLANNED_START_DATE": planned_start.isoformat(),
        "PLANNED_COMPLETION_DATE": (planned_start + timedelta(days=duration)).isoformat(),
        "STATUS": random.choices(["PLANNED", "IN_PROGRESS", "COMPLETED", "DELAYED"], weights=[15, 20, 55, 10])[0],
    })
prod_order_df = pd.DataFrame(po_rows)
prod_order_df.to_csv(f"{OUT_MFG}/production_order.csv", index=False)

print("production_line", len(line_df), "bill_of_materials", len(bom_df), "production_order", len(prod_order_df))
