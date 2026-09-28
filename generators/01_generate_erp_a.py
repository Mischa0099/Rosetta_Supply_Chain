"""
ERP A — SAP-like schema.
Field names intentionally mimic real SAP conventions (LIFNR, MATNR, WERKS, EINDT, ...).
"""
import random, csv, os
from datetime import date, timedelta
import pandas as pd
from importlib import import_module
import sys
sys.path.insert(0, os.path.dirname(__file__))
from importlib.machinery import SourceFileLoader
master = SourceFileLoader("master", os.path.join(os.path.dirname(__file__), "00_master_entities.py")).load_module()

random.seed(101)
OUT = "./csv/erp_a"
os.makedirs(OUT, exist_ok=True)

# ---- SUPPLIERS (LFA1) ----
suppliers_a = [s for s in master.master_suppliers if s["in_erp_a"]]
rows = []
supplier_lifnr = {}
for i, s in enumerate(suppliers_a):
    lifnr = f"{100000 + i*37 + 213:010d}"  # SAP-style zero-padded 10 digit vendor number
    supplier_lifnr[s["master_key"]] = lifnr
    rows.append({
        "LIFNR": lifnr, "NAME1": s["name"], "LAND1": s["country"][:2].upper() if s["country"]!="South Korea" else "KR",
        "ORT01": None, "WAERS": random.choice(["USD","EUR","INR","CNY"]),
        "ZTIMEZONE": s["timezone"], "ERDAT": (date(2023,1,1)+timedelta(days=random.randint(0,300))).isoformat(),
        "SPERR": "" if random.random() > 0.05 else "X",  # blocked flag - data quality edge case
    })
pd.DataFrame(rows).to_csv(f"{OUT}/suppliers.csv", index=False)

# ---- MATERIALS (MARA) ----
materials_a = [p for p in master.master_products if p["in_erp_a"]]
rows = []
material_matnr = {}
for i, p in enumerate(materials_a):
    matnr = f"{10000000 + i*91 + 17:08d}"
    material_matnr[p["master_key"]] = matnr
    rows.append({
        "MATNR": matnr, "MAKTX": p["name"], "MEINS": p["unit_of_measure"],
        "MTART": p["category"][:4].upper(), "ERDAT": (date(2023,1,1)+timedelta(days=random.randint(0,300))).isoformat(),
    })
pd.DataFrame(rows).to_csv(f"{OUT}/materials.csv", index=False)

# ---- PLANTS (T001W) ----
rows = []
plant_werks = {}
for i, pl in enumerate(master.master_plants):
    werks = f"PL{i+1:02d}"
    plant_werks[pl["master_key"]] = werks
    rows.append({"WERKS": werks, "NAME1": pl["name"], "LAND1": pl["country"][:2].upper() if pl["country"]!="South Korea" else "KR", "ZTIMEZONE": pl["timezone"]})
pd.DataFrame(rows).to_csv(f"{OUT}/plants.csv", index=False)

# ---- CUSTOMERS (KNA1) ----
rows = []
customer_kunnr = {}
CUSTOMER_NAMES_A = ["Northline Retail Group","Cascade Home Goods","Ironforge Machinery Co","Bluepeak Electronics",
                     "Harborview Distributors","Sunrise Auto Parts","Vertex Manufacturing","Golden Gate Appliances",
                     "Redwood Industrial Supply","Lakeshore Consumer Products","Prairie Wholesale Inc","Summit Retail Chain"]
for i, name in enumerate(CUSTOMER_NAMES_A):
    kunnr = f"{200000+i*23+5:010d}"
    customer_kunnr[name] = kunnr
    country, tz = random.choice(master.COUNTRIES_TZ)
    rows.append({"KUNNR": kunnr, "NAME1": name, "LAND1": country[:2].upper() if country!="South Korea" else "KR", "ZTIMEZONE": tz})
pd.DataFrame(rows).to_csv(f"{OUT}/customers.csv", index=False)

# ---- PURCHASE ORDERS (EKKO) + ITEMS (EKPO) ----
po_rows, poi_rows = [], []
ebeln_ctr = 4500000000
for i in range(140):
    ebeln_ctr += random.randint(1,3)
    ebeln = str(ebeln_ctr)
    sup = random.choice(suppliers_a)
    plant = random.choice(master.master_plants)
    bedat = date(2025,6,1) + timedelta(days=random.randint(0, 480))
    waers = random.choice(["USD","EUR","INR"])
    po_rows.append({"EBELN": ebeln, "LIFNR": supplier_lifnr[sup["master_key"]], "WERKS": plant_werks[plant["master_key"]],
                     "BEDAT": bedat.isoformat(), "WAERS": waers, "BSART": "NB"})
    n_items = random.randint(1,4)
    chosen_mats = random.sample(materials_a, min(n_items, len(materials_a)))
    for j, mat in enumerate(chosen_mats, start=1):
        lead = random.randint(3, 25)
        eindt = bedat + timedelta(days=lead)
        # inject occasional missing delivery date (data quality test case)
        eindt_val = "" if random.random() < 0.02 else eindt.isoformat()
        menge = random.randint(10, 2000)
        netpr = round(random.uniform(2, 850), 2)
        poi_rows.append({"EBELN": ebeln, "EBELP": f"{j*10:05d}", "MATNR": material_matnr[mat["master_key"]],
                          "WERKS": plant_werks[plant["master_key"]], "MENGE": menge, "MEINS": mat["unit_of_measure"],
                          "NETPR": netpr, "EINDT": eindt_val})
pd.DataFrame(po_rows).to_csv(f"{OUT}/purchase_orders.csv", index=False)
pd.DataFrame(poi_rows).to_csv(f"{OUT}/purchase_order_items.csv", index=False)

# ---- SALES ORDERS (VBAK) + ITEMS (VBAP) ----
so_rows, soi_rows = [], []
vbeln_ctr = 6000000000
for i in range(90):
    vbeln_ctr += random.randint(1,3)
    vbeln = str(vbeln_ctr)
    cust = random.choice(CUSTOMER_NAMES_A)
    erdat = date(2025,6,1) + timedelta(days=random.randint(0, 480))
    so_rows.append({"VBELN": vbeln, "KUNNR": customer_kunnr[cust], "ERDAT": erdat.isoformat(), "AUART": "OR"})
    n_items = random.randint(1,3)
    chosen_mats = random.sample(materials_a, min(n_items, len(materials_a)))
    plant = random.choice(master.master_plants)
    for j, mat in enumerate(chosen_mats, start=1):
        soi_rows.append({"VBELN": vbeln, "POSNR": f"{j*10:05d}", "MATNR": material_matnr[mat["master_key"]],
                          "WERKS": plant_werks[plant["master_key"]], "KWMENG": random.randint(5, 500)})
pd.DataFrame(so_rows).to_csv(f"{OUT}/sales_orders.csv", index=False)
pd.DataFrame(soi_rows).to_csv(f"{OUT}/sales_order_items.csv", index=False)

# ---- INVENTORY (per material x plant) ----
inv_rows = []
for mat in materials_a:
    for plant in random.sample(master.master_plants, random.randint(1,3)):
        inv_rows.append({"MATNR": material_matnr[mat["master_key"]], "WERKS": plant_werks[plant["master_key"]],
                          "LGORT": random.choice(["0001","0002","FERT"]), "LABST": random.randint(0, 5000)})
pd.DataFrame(inv_rows).to_csv(f"{OUT}/inventory.csv", index=False)

# Persist ID crosswalks for use by later scripts (logistics/IoT/contracts need real IDs)
import json
crosswalk = {
    "supplier_lifnr": supplier_lifnr, "material_matnr": material_matnr,
    "plant_werks": plant_werks, "customer_kunnr": customer_kunnr,
    "po_numbers": [r["EBELN"] for r in po_rows], "so_numbers": [r["VBELN"] for r in so_rows],
}
os.makedirs("generators/state", exist_ok=True)
with open("generators/state/erp_a_crosswalk.json","w") as f:
    json.dump(crosswalk, f, indent=2)

print("ERP A generated:", {k: len(v) if isinstance(v, list) else len(v) for k,v in crosswalk.items()})
print("suppliers", len(suppliers_a), "materials", len(materials_a), "plants", len(master.master_plants),
      "customers", len(CUSTOMER_NAMES_A), "POs", len(po_rows), "PO items", len(poi_rows),
      "SOs", len(so_rows), "SO items", len(soi_rows), "inventory rows", len(inv_rows))
