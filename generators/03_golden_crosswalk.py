"""
Human-authored GROUND TRUTH crosswalk between ERP A and ERP B IDs for the same
real-world entity. This is NOT part of either source system - it's an answer
key for validating the AI schema-mapping / entity-resolution component
(Test 1 in the spec: SAP LIFNR and Custom ERP VENDOR_NO -> same canonical ID).
Keep this out of the raw ingestion path; only use it to score mapping accuracy.
"""
import json, os
import pandas as pd
from importlib.machinery import SourceFileLoader
master = SourceFileLoader("master", os.path.join(os.path.dirname(__file__), "00_master_entities.py")).load_module()

with open("generators/state/erp_a_crosswalk.json") as f:
    a = json.load(f)
with open("generators/state/erp_b_crosswalk.json") as f:
    b = json.load(f)

rows = []
for s in master.master_suppliers:
    mk = s["master_key"]
    rows.append({
        "master_key": mk, "entity_type": "Supplier", "real_name": s["name"],
        "erp_a_id": a["supplier_lifnr"].get(mk, ""), "erp_b_id": b["vendor_id"].get(mk, ""),
        "present_in": ("ERP_A+ERP_B" if mk in a["supplier_lifnr"] and mk in b["vendor_id"]
                        else "ERP_A_only" if mk in a["supplier_lifnr"] else "ERP_B_only"),
    })
for p in master.master_products:
    mk = p["master_key"]
    rows.append({
        "master_key": mk, "entity_type": "Product", "real_name": p["name"],
        "erp_a_id": a["material_matnr"].get(mk, ""), "erp_b_id": b["sku_id"].get(mk, ""),
        "present_in": ("ERP_A+ERP_B" if mk in a["material_matnr"] and mk in b["sku_id"]
                        else "ERP_A_only" if mk in a["material_matnr"] else "ERP_B_only"),
    })
for pl in master.master_plants:
    mk = pl["master_key"]
    rows.append({
        "master_key": mk, "entity_type": "Plant", "real_name": pl["name"],
        "erp_a_id": a["plant_werks"].get(mk, ""), "erp_b_id": b["location_code"].get(mk, ""),
        "present_in": "ERP_A+ERP_B",
    })

df = pd.DataFrame(rows)
os.makedirs("docs", exist_ok=True)
df.to_csv("docs/golden_entity_crosswalk.csv", index=False)
print(df["present_in"].value_counts())
print(df.head(10).to_string())
