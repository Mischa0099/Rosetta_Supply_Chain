"""
Logistics domain: carriers, shipments, shipment_events.
Shipments fulfill PO items (inbound, supplier->plant) or SO items (outbound,
plant->customer), drawn from BOTH ERP A and ERP B so the logistics layer sits
"above" both source systems (realistic: one TMS serves the whole company).

Timestamps are deliberately generated in the LOCAL timezone of the origin/
destination and stored alongside their timezone offset (not pre-converted to
UTC) - this is what section 9 (Time-Zone Normalization) needs to fix downstream.
"""
import random, os, json, csv
from datetime import datetime, timedelta, date
import pandas as pd
from zoneinfo import ZoneInfo
from importlib.machinery import SourceFileLoader
master = SourceFileLoader("master", os.path.join(os.path.dirname(__file__), "00_master_entities.py")).load_module()

random.seed(303)
OUT = "./csv/logistics"
os.makedirs(OUT, exist_ok=True)

with open("generators/state/erp_a_crosswalk.json") as f: a = json.load(f)
with open("generators/state/erp_b_crosswalk.json") as f: b = json.load(f)

CARRIERS = [
    ("CAR-001", "Global Freight Lines", "Ocean"), ("CAR-002", "SkyBridge Air Cargo", "Air"),
    ("CAR-003", "TransCon Trucking", "Road"), ("CAR-004", "RailForward Logistics", "Rail"),
    ("CAR-005", "Meridian Express", "Road"), ("CAR-006", "Pacific Container Lines", "Ocean"),
]
pd.DataFrame([{"CARRIER_ID": c, "CARRIER_NAME": n, "MODE": m} for c, n, m in CARRIERS]).to_csv(f"{OUT}/carriers.csv", index=False)

plant_tz = {pl["master_key"]: pl["timezone"] for pl in master.master_plants}
plant_werks_rev = {v: k for k, v in a["plant_werks"].items()}
plant_loc_rev = {v: k for k, v in b["location_code"].items()}

def local_ts(day, tz_name, hour_range=(6, 20)):
    naive = datetime(day.year, day.month, day.day, random.randint(*hour_range), random.randint(0, 59), random.randint(0, 59))
    return naive.replace(tzinfo=ZoneInfo(tz_name))

shipments, events = [], []
STATUSES_FLOW = ["CREATED", "PICKED_UP", "DEPARTED", "CUSTOMS_CLEARED", "IN_TRANSIT", "ARRIVED", "DELIVERED"]

ship_ctr = 100000
for i in range(260):
    ship_ctr += random.randint(1, 3)
    shipment_id = f"SHP-{ship_ctr}"
    source_erp = random.choice(["ERP_A", "ERP_B"])
    direction = random.choice(["INBOUND", "OUTBOUND"])  # inbound = supplier->plant, outbound = plant->customer

    if source_erp == "ERP_A":
        plant_key = random.choice(list(a["plant_werks"].keys()))
        origin_tz = plant_tz[plant_key] if direction == "OUTBOUND" else random.choice(list(master.COUNTRIES_TZ))[1]
        ref_po_so = random.choice(a["po_numbers"]) if direction == "INBOUND" else random.choice(a["so_numbers"])
        origin_name = "Plant:" + a["plant_werks"][plant_key] if direction == "OUTBOUND" else "Supplier(ERP_A)"
        dest_name = "Customer(ERP_A)" if direction == "OUTBOUND" else "Plant:" + a["plant_werks"][plant_key]
    else:
        plant_key = random.choice(list(b["location_code"].keys()))
        origin_tz = plant_tz[plant_key] if direction == "OUTBOUND" else random.choice(list(master.COUNTRIES_TZ))[1]
        ref_po_so = random.choice(b["po_numbers"]) if direction == "INBOUND" else random.choice(b["so_numbers"])
        origin_name = "Location:" + b["location_code"][plant_key] if direction == "OUTBOUND" else "Vendor(ERP_B)"
        dest_name = "Customer(ERP_B)" if direction == "OUTBOUND" else "Location:" + b["location_code"][plant_key]

    dest_country, dest_tz = random.choice(master.COUNTRIES_TZ)
    carrier = random.choice(CARRIERS)

    created_day = date(2025, 9, 1) + timedelta(days=random.randint(0, 380))
    transit_days_planned = random.randint(3, 21)
    promised_dt = created_day + timedelta(days=transit_days_planned)

    # ~22% of shipments run late (some due to a genuine delay event we inject later)
    is_late = random.random() < 0.22
    actual_slip = random.randint(1, 7) if is_late else random.randint(-2, 0)
    actual_arrival_day = promised_dt + timedelta(days=actual_slip)

    status = random.choices(["DELIVERED", "IN_TRANSIT", "DELAYED", "ARRIVED"], weights=[70, 15, 10, 5])[0]

    shipments.append({
        "SHIPMENT_ID": shipment_id, "SOURCE_ERP": source_erp, "DIRECTION": direction,
        "REFERENCE_DOC": ref_po_so, "CARRIER_ID": carrier[0], "ORIGIN": origin_name, "DESTINATION": dest_name,
        "ORIGIN_TIMEZONE": origin_tz, "DEST_TIMEZONE": dest_tz,
        "PROMISED_DELIVERY_DATE": promised_dt.isoformat(),
        "ESTIMATED_DELIVERY_DATE": (promised_dt + timedelta(days=random.randint(-1, 2))).isoformat(),
        "ACTUAL_DELIVERY_DATE": actual_arrival_day.isoformat() if status == "DELIVERED" else "",
        "STATUS": status,
    })

    # generate the event chain with LOCAL timestamps (not yet UTC-normalized)
    t = created_day
    seq_statuses = STATUSES_FLOW if status != "DELAYED" else ["CREATED", "PICKED_UP", "DEPARTED", "CUSTOMS_CLEARED", "DELAYED"]
    day_cursor = created_day
    for k, st in enumerate(seq_statuses):
        day_cursor = day_cursor + timedelta(days=random.randint(0, max(1, transit_days_planned // len(seq_statuses))))
        tz_for_event = origin_tz if k < len(seq_statuses) // 2 else dest_tz
        ts = local_ts(day_cursor, tz_for_event)
        events.append({
            "SHIPMENT_ID": shipment_id, "EVENT_SEQ": k + 1, "EVENT_TYPE": st,
            "EVENT_LOCAL_TIMESTAMP": ts.isoformat(), "EVENT_TIMEZONE": tz_for_event,
            "NOTES": "Customs delay reported" if st == "DELAYED" else "",
        })
    if status == "DELIVERED":
        ts = local_ts(actual_arrival_day, dest_tz)
        events.append({"SHIPMENT_ID": shipment_id, "EVENT_SEQ": len(seq_statuses) + 1, "EVENT_TYPE": "DELIVERED",
                       "EVENT_LOCAL_TIMESTAMP": ts.isoformat(), "EVENT_TIMEZONE": dest_tz, "NOTES": ""})

pd.DataFrame(shipments).to_csv(f"{OUT}/shipments.csv", index=False)
pd.DataFrame(events).to_csv(f"{OUT}/shipment_events.csv", index=False)

# Pick one deliberately "featured" delayed shipment for the impact-analysis demo (S123-style)
featured = next(s for s in shipments if s["STATUS"] in ("DELAYED", "IN_TRANSIT"))
with open("generators/state/featured_shipment.json", "w") as f:
    json.dump(featured, f, indent=2)

print("Shipments:", len(shipments), "Events:", len(events))
print("Featured delayed shipment for demo:", featured["SHIPMENT_ID"], "ref:", featured["REFERENCE_DOC"])
