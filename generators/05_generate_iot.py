"""
IoT / near-real-time operational events: location_updates, temperature_readings,
warehouse_events. Designed to demonstrate incremental/near-real-time ingestion
(Snowflake streams/tasks/dynamic tables) layered on top of batch ERP + logistics data.
"""
import random, os, json
from datetime import datetime, timedelta
import pandas as pd
from zoneinfo import ZoneInfo
from importlib.machinery import SourceFileLoader
master = SourceFileLoader("master", os.path.join(os.path.dirname(__file__), "00_master_entities.py")).load_module()

random.seed(404)
OUT = "./csv/iot"
os.makedirs(OUT, exist_ok=True)

ship_df = pd.read_csv("./csv/logistics/shipments.csv")
in_transit = ship_df[ship_df["STATUS"].isin(["IN_TRANSIT", "DELAYED", "ARRIVED"])].sample(
    min(60, len(ship_df)), random_state=1)

# ---- LOCATION UPDATES (GPS pings for in-transit shipments) ----
rows = []
now = datetime(2026, 9, 27, 9, 0, 0, tzinfo=ZoneInfo("UTC"))
for _, s in in_transit.iterrows():
    n_pings = random.randint(3, 10)
    for k in range(n_pings):
        ts = now - timedelta(hours=random.randint(1, 240))
        rows.append({
            "SHIPMENT_ID": s["SHIPMENT_ID"], "EVENT_TIMESTAMP_UTC": ts.isoformat(),
            "LATITUDE": round(random.uniform(-55, 65), 5), "LONGITUDE": round(random.uniform(-170, 175), 5),
            "SPEED_KMH": round(random.uniform(0, 95), 1) if s["ORIGIN_TIMEZONE"] != s["DEST_TIMEZONE"] else round(random.uniform(0, 60), 1),
        })
pd.DataFrame(rows).sort_values("EVENT_TIMESTAMP_UTC").to_csv(f"{OUT}/location_updates.csv", index=False)

# ---- TEMPERATURE READINGS (cold-chain sensitive shipments only) ----
rows = []
cold_chain_shipments = in_transit.sample(min(20, len(in_transit)), random_state=2)
for _, s in cold_chain_shipments.iterrows():
    base_temp = random.uniform(2, 6)  # target cold-chain range
    n_readings = random.randint(10, 30)
    for k in range(n_readings):
        ts = now - timedelta(hours=random.randint(1, 240))
        excursion = random.random() < 0.06  # occasional temp excursion -> data quality / risk signal
        temp = round(base_temp + (random.uniform(4, 9) if excursion else random.uniform(-1, 1)), 2)
        rows.append({"SHIPMENT_ID": s["SHIPMENT_ID"], "EVENT_TIMESTAMP_UTC": ts.isoformat(),
                     "TEMPERATURE_C": temp, "EXCURSION_FLAG": excursion})
pd.DataFrame(rows).sort_values("EVENT_TIMESTAMP_UTC").to_csv(f"{OUT}/temperature_readings.csv", index=False)

# ---- WAREHOUSE EVENTS (per plant) ----
rows = []
WH_EVENT_TYPES = ["INBOUND_RECEIPT", "PUTAWAY", "PICK", "PACK", "OUTBOUND_DISPATCH", "CYCLE_COUNT", "STOCK_ADJUSTMENT"]
for pl in master.master_plants:
    tz = ZoneInfo(pl["timezone"])
    for k in range(random.randint(40, 70)):
        ts = (datetime(2026, 9, 27, 9, 0, 0, tzinfo=ZoneInfo("UTC")) - timedelta(hours=random.randint(1, 720))).astimezone(tz)
        rows.append({"PLANT_MASTER_KEY": pl["master_key"], "PLANT_NAME": pl["name"],
                     "EVENT_LOCAL_TIMESTAMP": ts.isoformat(), "EVENT_TIMEZONE": pl["timezone"],
                     "EVENT_TYPE": random.choice(WH_EVENT_TYPES), "QUANTITY": random.randint(1, 800)})
pd.DataFrame(rows).sort_values("EVENT_LOCAL_TIMESTAMP").to_csv(f"{OUT}/warehouse_events.csv", index=False)

# ---- SHIPMENT STATUS EVENTS (IoT-detected, independent of TMS-reported events - can conflict!) ----
rows = []
for _, s in in_transit.iterrows():
    for k in range(random.randint(1, 4)):
        ts = now - timedelta(hours=random.randint(1, 200))
        rows.append({"SHIPMENT_ID": s["SHIPMENT_ID"], "EVENT_TIMESTAMP_UTC": ts.isoformat(),
                     "DETECTED_STATUS": random.choice(["MOVING", "STOPPED", "AT_PORT", "AT_CUSTOMS", "AT_WAREHOUSE"]),
                     "SOURCE_DEVICE": f"IOT-TRACKER-{random.randint(1000,9999)}"})
pd.DataFrame(rows).sort_values("EVENT_TIMESTAMP_UTC").to_csv(f"{OUT}/shipment_status_events.csv", index=False)

print("IoT data generated: location_updates, temperature_readings, warehouse_events, shipment_status_events")
for fname in ["location_updates", "temperature_readings", "warehouse_events", "shipment_status_events"]:
    print(" -", fname, len(pd.read_csv(f"{OUT}/{fname}.csv")))
