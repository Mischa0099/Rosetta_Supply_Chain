"""
Phase 1, items 3-4: Canonical Ontology + Basic Relationships.

Builds canonical CORE entity tables by resolving ERP A + ERP B (+ logistics
+ contracts) records to a single business representation, using the known
generation-time crosswalk as a stand-in for the AI-driven schema mapping
that Phase 2 will formalize (with confidence scores, a mapping registry,
and human-in-the-loop review). The OUTPUT SHAPE here (canonical entities +
relationship edges) is exactly what Phase 2's governed pipeline must also
produce - Phase 1 just gets us there deterministically first so the
ontology, semantic layer, and conversational analytics work have something
real to sit on top of.

NOTE: all source ID columns are read as dtype=str. Several IDs (LIFNR,
KUNNR) are zero-padded numeric strings (e.g. "0000100213"); pandas'
automatic numeric inference silently strips the leading zeros and turns
them into floats, breaking every downstream join. Reading everything as
string avoids that entire class of bug.
"""
import os, json
import pandas as pd
from importlib.machinery import SourceFileLoader
master = SourceFileLoader("master", "generators/00_master_entities.py").load_module()

SRC = "./csv"
OUT = "./csv/ontology_core"
os.makedirs(OUT, exist_ok=True)

gold = pd.read_csv("docs/golden_entity_crosswalk.csv", dtype=str)

erp_a_sup = pd.read_csv(f"{SRC}/erp_a/suppliers.csv", dtype=str)
erp_b_vnd = pd.read_csv(f"{SRC}/erp_b/vendors.csv", dtype=str)
erp_a_mat = pd.read_csv(f"{SRC}/erp_a/materials.csv", dtype=str)
erp_b_itm = pd.read_csv(f"{SRC}/erp_b/items.csv", dtype=str)
erp_a_plt = pd.read_csv(f"{SRC}/erp_a/plants.csv", dtype=str)
erp_b_loc = pd.read_csv(f"{SRC}/erp_b/locations.csv", dtype=str)
erp_a_cust = pd.read_csv(f"{SRC}/erp_a/customers.csv", dtype=str)
erp_b_cust = pd.read_csv(f"{SRC}/erp_b/customers.csv", dtype=str)

def blank(v):
    return v is None or (isinstance(v, float) and pd.isna(v)) or v == ""

# =====================================================================
# CANONICAL SUPPLIER  (dedup across ERP A LIFNR + ERP B VENDOR_ID)
# =====================================================================
sup_gold = gold[gold.entity_type == "Supplier"].reset_index(drop=True)
rows = []
for i, r in sup_gold.iterrows():
    canonical_id = f"CS-SUP-{i+1:03d}"
    country, tz, waers = None, None, None
    if not blank(r.erp_a_id):
        m = erp_a_sup[erp_a_sup.LIFNR == r.erp_a_id]
        if len(m): country, tz, waers = m.iloc[0].LAND1, m.iloc[0].ZTIMEZONE, m.iloc[0].WAERS
    if country is None and not blank(r.erp_b_id):
        m = erp_b_vnd[erp_b_vnd.VENDOR_ID == r.erp_b_id]
        if len(m): country, tz, waers = m.iloc[0].COUNTRY_CODE, m.iloc[0].TIME_ZONE, m.iloc[0].CURRENCY_CODE
    rows.append({
        "CANONICAL_SUPPLIER_ID": canonical_id, "SUPPLIER_NAME": r.real_name, "COUNTRY": country,
        "TIMEZONE": tz, "DEFAULT_CURRENCY": waers, "SOURCE_SYSTEMS": r.present_in,
        "ERP_A_SUPPLIER_ID": "" if blank(r.erp_a_id) else r.erp_a_id,
        "ERP_B_VENDOR_ID": "" if blank(r.erp_b_id) else r.erp_b_id,
        "MASTER_KEY": r.master_key,
    })
supplier_df = pd.DataFrame(rows)
supplier_df.to_csv(f"{OUT}/supplier.csv", index=False)

# =====================================================================
# CANONICAL PRODUCT  (dedup across ERP A MATNR + ERP B SKU)
# =====================================================================
prd_gold = gold[gold.entity_type == "Product"].reset_index(drop=True)
rows = []
for i, r in prd_gold.iterrows():
    canonical_id = f"CS-PRD-{i+1:03d}"
    uom, category = None, None
    if not blank(r.erp_a_id):
        m = erp_a_mat[erp_a_mat.MATNR == r.erp_a_id]
        if len(m): uom, category = m.iloc[0].MEINS, m.iloc[0].MTART
    if uom is None and not blank(r.erp_b_id):
        m = erp_b_itm[erp_b_itm.SKU == r.erp_b_id]
        if len(m): uom, category = m.iloc[0].UOM, m.iloc[0].ITEM_CATEGORY
    rows.append({
        "CANONICAL_PRODUCT_ID": canonical_id, "PRODUCT_NAME": r.real_name, "UNIT_OF_MEASURE": uom,
        "CATEGORY": category, "SOURCE_SYSTEMS": r.present_in,
        "ERP_A_MATERIAL_ID": "" if blank(r.erp_a_id) else r.erp_a_id,
        "ERP_B_SKU": "" if blank(r.erp_b_id) else r.erp_b_id,
        "MASTER_KEY": r.master_key,
    })
product_df = pd.DataFrame(rows)
product_df.to_csv(f"{OUT}/product.csv", index=False)

# =====================================================================
# CANONICAL PLANT  (all 6 plants exist in both ERPs, different codes)
# =====================================================================
plt_gold = gold[gold.entity_type == "Plant"].reset_index(drop=True)
rows = []
for i, r in plt_gold.iterrows():
    canonical_id = f"CS-PLT-{i+1:03d}"
    m = erp_a_plt[erp_a_plt.WERKS == r.erp_a_id]
    country, tz = (m.iloc[0].LAND1, m.iloc[0].ZTIMEZONE) if len(m) else (None, None)
    rows.append({
        "CANONICAL_PLANT_ID": canonical_id, "PLANT_NAME": r.real_name, "COUNTRY": country, "TIMEZONE": tz,
        "ERP_A_WERKS": r.erp_a_id, "ERP_B_LOCATION_CODE": r.erp_b_id, "MASTER_KEY": r.master_key,
    })
plant_df = pd.DataFrame(rows)
plant_df.to_csv(f"{OUT}/plant.csv", index=False)

# =====================================================================
# CANONICAL CUSTOMER  (no intentional overlap between ERPs - different
# regional customer bases - so this is a straight union, not a dedup)
# =====================================================================
rows = []
ctr = 1
cust_a_map, cust_b_map = {}, {}
for _, r in erp_a_cust.iterrows():
    cid = f"CS-CUS-{ctr:03d}"; ctr += 1
    cust_a_map[r.KUNNR] = cid
    rows.append({"CANONICAL_CUSTOMER_ID": cid, "CUSTOMER_NAME": r.NAME1, "COUNTRY": r.LAND1,
                 "TIMEZONE": r.ZTIMEZONE, "SOURCE_SYSTEM": "ERP_A", "ERP_A_KUNNR": r.KUNNR, "ERP_B_CUSTOMER_ID": ""})
for _, r in erp_b_cust.iterrows():
    cid = f"CS-CUS-{ctr:03d}"; ctr += 1
    cust_b_map[r.CUSTOMER_ID] = cid
    rows.append({"CANONICAL_CUSTOMER_ID": cid, "CUSTOMER_NAME": r.CUSTOMER_NAME, "COUNTRY": r.COUNTRY_CODE,
                 "TIMEZONE": r.TIME_ZONE, "SOURCE_SYSTEM": "ERP_B", "ERP_A_KUNNR": "", "ERP_B_CUSTOMER_ID": r.CUSTOMER_ID})
customer_df = pd.DataFrame(rows)
customer_df.to_csv(f"{OUT}/customer.csv", index=False)

# =====================================================================
# CANONICAL LOCATION  (superset used by Shipment origin/destination:
# every Plant + every Supplier + every Customer is also a "Location")
# =====================================================================
rows = []
for _, r in plant_df.iterrows():
    rows.append({"CANONICAL_LOCATION_ID": f"LOC-{r.CANONICAL_PLANT_ID}", "LOCATION_NAME": r.PLANT_NAME,
                 "LOCATION_TYPE": "PLANT", "COUNTRY": r.COUNTRY, "TIMEZONE": r.TIMEZONE,
                 "REFERENCED_ENTITY_ID": r.CANONICAL_PLANT_ID})
for _, r in supplier_df.iterrows():
    rows.append({"CANONICAL_LOCATION_ID": f"LOC-{r.CANONICAL_SUPPLIER_ID}", "LOCATION_NAME": r.SUPPLIER_NAME,
                 "LOCATION_TYPE": "SUPPLIER_SITE", "COUNTRY": r.COUNTRY, "TIMEZONE": r.TIMEZONE,
                 "REFERENCED_ENTITY_ID": r.CANONICAL_SUPPLIER_ID})
for _, r in customer_df.iterrows():
    rows.append({"CANONICAL_LOCATION_ID": f"LOC-{r.CANONICAL_CUSTOMER_ID}", "LOCATION_NAME": r.CUSTOMER_NAME,
                 "LOCATION_TYPE": "CUSTOMER_SITE", "COUNTRY": r.COUNTRY, "TIMEZONE": r.TIMEZONE,
                 "REFERENCED_ENTITY_ID": r.CANONICAL_CUSTOMER_ID})
location_df = pd.DataFrame(rows)
location_df.to_csv(f"{OUT}/location.csv", index=False)

print("supplier", len(supplier_df), "product", len(product_df), "plant", len(plant_df),
      "customer", len(customer_df), "location", len(location_df))
print("suppliers missing country (should be 0):", supplier_df.COUNTRY.isna().sum())

# Save lookup maps for downstream scripts (orders, contracts, graph)
lookups = {
    "erp_a_lifnr_to_canonical": {r.ERP_A_SUPPLIER_ID: r.CANONICAL_SUPPLIER_ID for _, r in supplier_df.iterrows() if r.ERP_A_SUPPLIER_ID},
    "erp_b_vendorid_to_canonical": {r.ERP_B_VENDOR_ID: r.CANONICAL_SUPPLIER_ID for _, r in supplier_df.iterrows() if r.ERP_B_VENDOR_ID},
    "erp_a_material_to_canonical": {r.ERP_A_MATERIAL_ID: r.CANONICAL_PRODUCT_ID for _, r in product_df.iterrows() if r.ERP_A_MATERIAL_ID},
    "erp_b_sku_to_canonical": {r.ERP_B_SKU: r.CANONICAL_PRODUCT_ID for _, r in product_df.iterrows() if r.ERP_B_SKU},
    "erp_a_werks_to_canonical": dict(zip(plant_df.ERP_A_WERKS, plant_df.CANONICAL_PLANT_ID)),
    "erp_b_location_to_canonical": dict(zip(plant_df.ERP_B_LOCATION_CODE, plant_df.CANONICAL_PLANT_ID)),
    "erp_a_kunnr_to_canonical": cust_a_map,
    "erp_b_customerid_to_canonical": cust_b_map,
}
with open("generators/state/canonical_lookups.json", "w") as f:
    json.dump(lookups, f, indent=2)
