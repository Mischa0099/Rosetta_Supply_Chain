"""
ERP B — Custom/Oracle-like schema.
Represents substantially the same business concepts as ERP A, but with
different field names (vendor_id, sku, location_code, promise_dt, ...).
12 of the 18 real suppliers and 26 of the 40 real products overlap with ERP A
under DIFFERENT ID schemes and NAMES that are only similar, not identical
(e.g. minor punctuation/suffix differences), to make AI schema/entity
mapping a genuine (not trivial) task.
"""
import random, os, json
from datetime import date, timedelta
import pandas as pd
from importlib.machinery import SourceFileLoader
master = SourceFileLoader("master", os.path.join(os.path.dirname(__file__), "00_master_entities.py")).load_module()

random.seed(202)
OUT = "./csv/erp_b"
os.makedirs(OUT, exist_ok=True)

def light_name_variant(name):
    """Introduce a small, realistic naming variation between ERP systems."""
    suffixes = {"Ltd": "Ltd.", "Inc": "Inc.", "Corp": "Corporation", "GmbH": "GmbH ",
                "SA": "S.A.", "Group": "Grp", "Works": "Wrks"}
    for k, v in suffixes.items():
        if name.endswith(k):
            return name[: -len(k)] + v
    return name  # some names pass through unchanged (realistic - not every field drifts)

# ---- VENDORS ----
suppliers_b = [s for s in master.master_suppliers if s["in_erp_b"]]
rows = []
vendor_id = {}
for i, s in enumerate(suppliers_b):
    vid = f"VEND-{4000+i*13+7}"
    vendor_id[s["master_key"]] = vid
    rows.append({
        "VENDOR_ID": vid, "VENDOR_NAME": light_name_variant(s["name"]),
        "COUNTRY_CODE": s["country"][:2].upper() if s["country"] != "South Korea" else "KR",
        "CURRENCY_CODE": random.choice(["USD", "EUR", "INR", "CNY"]),
        "TIME_ZONE": s["timezone"],
        "CREATED_DATE": (date(2023, 1, 1) + timedelta(days=random.randint(0, 300))).isoformat(),
        "STATUS": "ACTIVE" if random.random() > 0.05 else "HOLD",
    })
pd.DataFrame(rows).to_csv(f"{OUT}/vendors.csv", index=False)

# ---- ITEMS ----
products_b = [p for p in master.master_products if p["in_erp_b"]]
rows = []
sku_id = {}
for i, p in enumerate(products_b):
    sku = f"SKU-{p['category'][:3].upper()}-{1000+i*7+3}"
    sku_id[p["master_key"]] = sku
    rows.append({"SKU": sku, "ITEM_DESC": p["name"], "UOM": p["unit_of_measure"],
                 "ITEM_CATEGORY": p["category"],
                 "CREATED_DATE": (date(2023, 1, 1) + timedelta(days=random.randint(0, 300))).isoformat()})
pd.DataFrame(rows).to_csv(f"{OUT}/items.csv", index=False)

# ---- LOCATIONS (== plants, same real plants as ERP A under different codes) ----
rows = []
location_code = {}
for i, pl in enumerate(master.master_plants):
    loc = f"LOC-{pl['name'].split()[0][:3].upper()}"
    location_code[pl["master_key"]] = loc
    rows.append({"LOCATION_CODE": loc, "LOCATION_NAME": pl["name"],
                 "COUNTRY_CODE": pl["country"][:2].upper() if pl["country"] != "South Korea" else "KR",
                 "TIME_ZONE": pl["timezone"]})
pd.DataFrame(rows).to_csv(f"{OUT}/locations.csv", index=False)

# ---- CUSTOMERS (different customer base than ERP A - different region/division) ----
CUSTOMER_NAMES_B = ["Meadowbrook Retailers", "Silverline Auto Group", "Trident Industrial Buyers",
                     "Coral Bay Distribution", "Falcon Point Manufacturing", "Union Square Wholesale",
                     "Brightstar Electronics Retail", "Canyon Ridge Supply Co", "Metro Consumer Group",
                     "Ashford Machinery Buyers", "Pinehill Auto Parts", "Riverside Appliance Co",
                     "Westgate Distributors", "Oakmont Industrial"]
rows = []
customer_id = {}
for i, name in enumerate(CUSTOMER_NAMES_B):
    cid = f"CUST-{500+i*9+2}"
    customer_id[name] = cid
    country, tz = random.choice(master.COUNTRIES_TZ)
    rows.append({"CUSTOMER_ID": cid, "CUSTOMER_NAME": name,
                 "COUNTRY_CODE": country[:2].upper() if country != "South Korea" else "KR", "TIME_ZONE": tz})
pd.DataFrame(rows).to_csv(f"{OUT}/customers.csv", index=False)

# ---- PURCHASE ORDERS + LINES ----
po_rows, pol_rows = [], []
po_ctr = 900000
for i in range(120):
    po_ctr += random.randint(1, 4)
    po_number = f"PO-{po_ctr}"
    sup = random.choice(suppliers_b)
    loc = random.choice(master.master_plants)
    order_date = date(2025, 6, 1) + timedelta(days=random.randint(0, 480))
    po_rows.append({"PO_NUMBER": po_number, "VENDOR_ID": vendor_id[sup["master_key"]],
                     "LOCATION_CODE": location_code[loc["master_key"]], "ORDER_DATE": order_date.isoformat(),
                     "CURRENCY_CODE": random.choice(["USD", "EUR", "INR"]), "PO_TYPE": "STANDARD"})
    n_items = random.randint(1, 4)
    chosen = random.sample(products_b, min(n_items, len(products_b)))
    for j, it in enumerate(chosen, start=1):
        lead = random.randint(3, 25)
        promise_dt = order_date + timedelta(days=lead)
        promise_val = "" if random.random() < 0.02 else promise_dt.isoformat()
        pol_rows.append({"PO_NUMBER": po_number, "LINE_NUM": j, "SKU": sku_id[it["master_key"]],
                          "LOCATION_CODE": location_code[loc["master_key"]],
                          "QUANTITY": random.randint(10, 2000), "UNIT_PRICE": round(random.uniform(2, 850), 2),
                          "PROMISE_DT": promise_val})
pd.DataFrame(po_rows).to_csv(f"{OUT}/purchase_orders.csv", index=False)
pd.DataFrame(pol_rows).to_csv(f"{OUT}/purchase_order_lines.csv", index=False)

# ---- SALES ORDERS + LINES ----
so_rows, sol_rows = [], []
so_ctr = 700000
for i in range(75):
    so_ctr += random.randint(1, 4)
    order_id = f"SO-{so_ctr}"
    cust = random.choice(CUSTOMER_NAMES_B)
    order_date = date(2025, 6, 1) + timedelta(days=random.randint(0, 480))
    so_rows.append({"ORDER_ID": order_id, "CUSTOMER_ID": customer_id[cust], "ORDER_DATE": order_date.isoformat(),
                     "ORDER_TYPE": "STANDARD"})
    n_items = random.randint(1, 3)
    chosen = random.sample(products_b, min(n_items, len(products_b)))
    loc = random.choice(master.master_plants)
    for j, it in enumerate(chosen, start=1):
        sol_rows.append({"ORDER_ID": order_id, "LINE_NUM": j, "SKU": sku_id[it["master_key"]],
                          "LOCATION_CODE": location_code[loc["master_key"]], "QTY_ORDERED": random.randint(5, 500)})
pd.DataFrame(so_rows).to_csv(f"{OUT}/sales_orders.csv", index=False)
pd.DataFrame(sol_rows).to_csv(f"{OUT}/sales_order_lines.csv", index=False)

# ---- INVENTORY BALANCES ----
rows = []
for it in products_b:
    for loc in random.sample(master.master_plants, random.randint(1, 3)):
        rows.append({"SKU": sku_id[it["master_key"]], "LOCATION_CODE": location_code[loc["master_key"]],
                     "WAREHOUSE_ZONE": random.choice(["A", "B", "C"]), "QTY_ON_HAND": random.randint(0, 5000)})
pd.DataFrame(rows).to_csv(f"{OUT}/inventory_balances.csv", index=False)

crosswalk = {"vendor_id": vendor_id, "sku_id": sku_id, "location_code": location_code,
             "customer_id": customer_id, "po_numbers": [r["PO_NUMBER"] for r in po_rows],
             "so_numbers": [r["ORDER_ID"] for r in so_rows]}
with open("generators/state/erp_b_crosswalk.json", "w") as f:
    json.dump(crosswalk, f, indent=2)

print("ERP B generated: suppliers", len(suppliers_b), "products", len(products_b), "plants", len(master.master_plants),
      "customers", len(CUSTOMER_NAMES_B), "POs", len(po_rows), "PO lines", len(pol_rows),
      "SOs", len(so_rows), "SO lines", len(sol_rows), "inventory rows", len(rows))
