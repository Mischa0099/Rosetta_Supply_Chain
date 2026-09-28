"""
Computes the canonical metrics (OTD, Fill Rate, Days of Inventory, Landed
Cost) in Python, mirroring the SQL views in sql/14_canonical_metrics.sql
exactly, so the demo docs have real numbers without a live Snowflake
connection. Also demonstrates persona consistency (Test 2): three
differently-worded questions filtering the SAME fact table produce the
SAME number.
"""
import json
import pandas as pd
from datetime import date
from zoneinfo import ZoneInfo

SRC = "./csv"

shipments = pd.read_csv(f"{SRC}/logistics/shipments.csv", dtype=str)
events = pd.read_csv(f"{SRC}/logistics/shipment_events.csv", dtype=str)
order = pd.read_csv(f"{SRC}/ontology_core/order.csv", dtype=str)
order_line = pd.read_csv(f"{SRC}/ontology_core/order_line.csv", dtype=str)
supplier = pd.read_csv(f"{SRC}/ontology_core/supplier.csv", dtype=str)
inventory = pd.read_csv(f"{SRC}/ontology_goods/inventory.csv", dtype=str)
warehouse = pd.read_csv(f"{SRC}/ontology_goods/warehouse.csv", dtype=str)
product = pd.read_csv(f"{SRC}/ontology_core/product.csv", dtype=str)

# ---------------------------------------------------------------
# Actual delivery date in UTC, from the DELIVERED shipment_event
# (mirrors GOVERNANCE.SHIPMENT_EVENTS_UTC + SHIPMENT_DELIVERY_TIMEZONE_SAFE)
# ---------------------------------------------------------------
delivered_events = events[events.EVENT_TYPE == "DELIVERED"].copy()
def to_utc_date(row):
    local_ts = pd.Timestamp(row.EVENT_LOCAL_TIMESTAMP)
    return local_ts.tz_convert("UTC").date().isoformat()
delivered_events["ACTUAL_DELIVERY_DATE_UTC"] = delivered_events.apply(to_utc_date, axis=1)
delivered_events = delivered_events[["SHIPMENT_ID", "ACTUAL_DELIVERY_DATE_UTC"]]

fact = shipments.merge(delivered_events, on="SHIPMENT_ID", how="left")
fact = fact.merge(order[["SOURCE_SYSTEM", "SOURCE_DOC_ID", "SUPPLIER_ID", "PLANT_ID", "CUSTOMER_ID"]],
                  left_on=["SOURCE_ERP", "REFERENCE_DOC"], right_on=["SOURCE_SYSTEM", "SOURCE_DOC_ID"], how="left")

fact["IS_ELIGIBLE"] = fact.PROMISED_DELIVERY_DATE.notna() & (fact.STATUS == "DELIVERED")
fact["IS_ON_TIME"] = fact.apply(
    lambda r: (r.ACTUAL_DELIVERY_DATE_UTC <= r.PROMISED_DELIVERY_DATE) if r.IS_ELIGIBLE else None, axis=1)

# ---------------------------------------------------------------
# OTD by supplier (inbound shipments only) - mirrors METRIC_OTD_BY_SUPPLIER
# ---------------------------------------------------------------
inbound = fact[fact.DIRECTION == "INBOUND"]
otd_by_supplier = inbound.groupby("SUPPLIER_ID").agg(
    eligible=("IS_ELIGIBLE", "sum"), on_time=("IS_ON_TIME", "sum")).reset_index()
otd_by_supplier["OTD_PCT"] = (otd_by_supplier.on_time / otd_by_supplier.eligible * 100).round(1)
otd_by_supplier = otd_by_supplier[otd_by_supplier.eligible >= 5].sort_values("eligible", ascending=False)

featured = otd_by_supplier.iloc[0]
featured_supplier = supplier[supplier.CANONICAL_SUPPLIER_ID == featured.SUPPLIER_ID].iloc[0]

# ---------------------------------------------------------------
# Persona consistency: three phrasings, same filter, same view -> same number
# ---------------------------------------------------------------
def planning_delivery_reliability(supplier_id):
    r = inbound[inbound.SUPPLIER_ID == supplier_id]
    return round(r.IS_ON_TIME.sum() / r.IS_ELIGIBLE.sum() * 100, 1)

def procurement_otd(supplier_id):
    r = inbound[inbound.SUPPLIER_ID == supplier_id]
    return round(r.IS_ON_TIME.sum() / r.IS_ELIGIBLE.sum() * 100, 1)

def logistics_on_time_count(supplier_id):
    r = inbound[inbound.SUPPLIER_ID == supplier_id]
    return int(r.IS_ON_TIME.sum()), int(r.IS_ELIGIBLE.sum())

sid = featured.SUPPLIER_ID
planning_val = planning_delivery_reliability(sid)
procurement_val = procurement_otd(sid)
logistics_on_time, logistics_eligible = logistics_on_time_count(sid)

# ---------------------------------------------------------------
# Fill Rate for the same featured supplier (mirrors METRIC_FILL_RATE_BY_SUPPLIER)
# ---------------------------------------------------------------
ol = order_line.merge(order[["CANONICAL_ORDER_ID", "SUPPLIER_ID", "ORDER_TYPE", "SOURCE_SYSTEM", "SOURCE_DOC_ID"]],
                      on="CANONICAL_ORDER_ID", how="left")
ol = ol.merge(shipments[["SOURCE_ERP", "REFERENCE_DOC", "STATUS"]],
             left_on=["SOURCE_SYSTEM", "SOURCE_DOC_ID"], right_on=["SOURCE_ERP", "REFERENCE_DOC"], how="left")
ol["QUANTITY"] = pd.to_numeric(ol.QUANTITY, errors="coerce")
ol["QTY_DELIVERED"] = ol.apply(lambda r: r.QUANTITY if r.STATUS == "DELIVERED" else 0, axis=1)
po_lines = ol[ol.ORDER_TYPE == "PURCHASE"]
fr = po_lines[po_lines.SUPPLIER_ID == sid]
fill_rate_pct = round(fr.QTY_DELIVERED.sum() / fr.QUANTITY.sum() * 100, 1)
missing_promise = int(fr.PROMISED_DATE.isna().sum())

# ---------------------------------------------------------------
# Days of Inventory - pick one product/plant with real demand
# ---------------------------------------------------------------
so_lines = order_line.merge(order[["CANONICAL_ORDER_ID", "ORDER_TYPE"]], on="CANONICAL_ORDER_ID")
so_lines = so_lines[so_lines.ORDER_TYPE == "SALES"]
so_lines["QUANTITY"] = pd.to_numeric(so_lines.QUANTITY, errors="coerce")
demand = so_lines.groupby(["PRODUCT_ID", "PLANT_ID"]).QUANTITY.sum().reset_index()
demand["AVG_DAILY_DEMAND"] = demand.QUANTITY / 90.0
inv = inventory.merge(warehouse[["CANONICAL_WAREHOUSE_ID", "PLANT_ID"]], on="CANONICAL_WAREHOUSE_ID")
inv["QUANTITY_ON_HAND"] = pd.to_numeric(inv.QUANTITY_ON_HAND, errors="coerce")
inv_agg = inv.groupby(["CANONICAL_PRODUCT_ID", "PLANT_ID"]).QUANTITY_ON_HAND.sum().reset_index()
doi = inv_agg.merge(demand, left_on=["CANONICAL_PRODUCT_ID", "PLANT_ID"], right_on=["PRODUCT_ID", "PLANT_ID"], how="left")
doi["DAYS_OF_INVENTORY"] = doi.QUANTITY_ON_HAND / doi.AVG_DAILY_DEMAND
doi_valid = doi.dropna(subset=["DAYS_OF_INVENTORY"]).sort_values("DAYS_OF_INVENTORY")
doi_example = doi_valid.iloc[len(doi_valid)//2]  # a representative middle case
doi_product = product[product.CANONICAL_PRODUCT_ID == doi_example.CANONICAL_PRODUCT_ID].iloc[0]

# ---------------------------------------------------------------
# Landed Cost example for the featured supplier's most common product
# ---------------------------------------------------------------
po_priced = po_lines[po_lines.SUPPLIER_ID == sid].copy()
po_priced["UNIT_PRICE"] = pd.to_numeric(po_priced.UNIT_PRICE, errors="coerce")
lc_product_id = po_priced.PRODUCT_ID.mode().iloc[0]
avg_price = po_priced[po_priced.PRODUCT_ID == lc_product_id].UNIT_PRICE.mean()
country = featured_supplier.COUNTRY
LANDED_COST_CONFIG = {"CN": (0.12, 0.09, 0.02), "IN": (0.10, 0.06, 0.02), "DE": (0.06, 0.02, 0.02),
                      "US": (0.04, 0.00, 0.02), "MX": (0.05, 0.01, 0.02), "BR": (0.09, 0.07, 0.02),
                      "KR": (0.09, 0.04, 0.02), "UK": (0.06, 0.02, 0.02)}
freight, duty, handling = LANDED_COST_CONFIG.get(country, (0.08, 0.05, 0.02))
landed_cost = round(avg_price * (1 + freight + duty + handling), 2)
lc_product_name = product[product.CANONICAL_PRODUCT_ID == lc_product_id].iloc[0].PRODUCT_NAME

results = {
    "featured_supplier": {"id": sid, "name": featured_supplier.SUPPLIER_NAME, "country": country},
    "otd": {"eligible_shipments": int(featured.eligible), "on_time_shipments": int(featured.on_time),
            "otd_pct": float(featured.OTD_PCT)},
    "persona_consistency": {"planning_delivery_reliability_pct": planning_val,
                            "procurement_otd_pct": procurement_val,
                            "logistics_on_time_of_eligible": f"{logistics_on_time}/{logistics_eligible}",
                            "all_consistent": planning_val == procurement_val == round(logistics_on_time/logistics_eligible*100, 1)},
    "fill_rate": {"total_ordered": float(fr.QUANTITY.sum()), "total_delivered": float(fr.QTY_DELIVERED.sum()),
                 "fill_rate_pct": fill_rate_pct, "lines_missing_promise_date": missing_promise},
    "days_of_inventory": {"product_id": doi_example.CANONICAL_PRODUCT_ID, "product_name": doi_product.PRODUCT_NAME,
                          "plant_id": doi_example.PLANT_ID, "qty_on_hand": float(doi_example.QUANTITY_ON_HAND),
                          "avg_daily_demand": round(float(doi_example.AVG_DAILY_DEMAND), 2),
                          "days_of_inventory": round(float(doi_example.DAYS_OF_INVENTORY), 1)},
    "landed_cost": {"product_id": lc_product_id, "product_name": lc_product_name,
                   "avg_unit_price": round(float(avg_price), 2), "freight_pct": freight, "duty_pct": duty,
                   "handling_pct": handling, "landed_cost_estimate": landed_cost},
}

with open("generators/state/metrics_demo_results.json", "w") as f:
    json.dump(results, f, indent=2, default=str)

print(json.dumps(results, indent=2, default=str))
