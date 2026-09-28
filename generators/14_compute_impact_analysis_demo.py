"""
Computes the impact-analysis + financial-impact worked example in Python,
mirroring sql/17_impact_analysis.sql and sql/18_financial_impact_estimation.sql
exactly, on the featured demo shipment (SHP-100001), so docs/ has real
traced numbers without a live Snowflake connection.
"""
import json
import pandas as pd

SRC = "./csv"
edges = pd.read_csv(f"{SRC}/ontology_graph/relationship_edges.csv", dtype=str)
product = pd.read_csv(f"{SRC}/ontology_core/product.csv", dtype=str)
plant = pd.read_csv(f"{SRC}/ontology_core/plant.csv", dtype=str)
customer = pd.read_csv(f"{SRC}/ontology_core/customer.csv", dtype=str)
order_line = pd.read_csv(f"{SRC}/ontology_core/order_line.csv", dtype=str)
order = pd.read_csv(f"{SRC}/ontology_core/order.csv", dtype=str)

SHIPMENT_ID = "SHP-100001"
DELAY_DAYS = 4

def edges_where(from_type=None, from_id=None, rel=None, to_type=None, to_id=None):
    df = edges
    if from_type: df = df[df.FROM_TYPE == from_type]
    if from_id: df = df[df.FROM_ID == from_id]
    if rel: df = df[df.RELATIONSHIP == rel]
    if to_type: df = df[df.TO_TYPE == to_type]
    if to_id: df = df[df.TO_ID == to_id]
    return df

# direct_products: Shipment -> transports -> Product
direct_products = set(edges_where(from_type="SHIPMENT", from_id=SHIPMENT_ID, rel="transports").TO_ID)

# destination_plant(s): Shipment -> fulfills -> Order -> fulfilled_at -> Plant
# SCOPING RULE: a delayed inbound shipment only disrupts production AT THE
# PLANT IT WAS HEADED TO - not every plant nationwide that happens to also
# use the same generic raw material. Without this scope, "requires"/"contains"
# would sweep in every unrelated order across the whole company that ever
# touches this product category, wildly overstating blast radius.
fulfilled_orders = set(edges_where(from_type="SHIPMENT", from_id=SHIPMENT_ID, rel="fulfills").TO_ID)
destination_plants = set()
for oid in fulfilled_orders:
    destination_plants |= set(edges_where(from_type="ORDER", from_id=oid, rel="fulfilled_at").TO_ID)

# finished_goods: Product -> requires -> (direct_products), SCOPED to finished
# goods actually manufactured at one of destination_plants
candidate_finished_goods = set()
for pid in direct_products:
    candidate_finished_goods |= set(edges_where(rel="requires", from_type="PRODUCT", to_id=pid).FROM_ID)
finished_goods = set()
for plt in destination_plants:
    produced_here = set(edges_where(from_type="PLANT", from_id=plt, rel="produces").TO_ID)
    finished_goods |= (candidate_finished_goods & produced_here)

all_affected_products = direct_products | finished_goods
affected_plants = destination_plants  # scoped, see rule above

# affected_production_orders: PRODUCTION_ORDER -> produces -> (finished_goods),
# already implicitly scoped since finished_goods is plant-scoped
affected_prod_orders = set()
for pid in finished_goods:
    affected_prod_orders |= set(edges_where(rel="produces", from_type="PRODUCTION_ORDER", to_id=pid).FROM_ID)

# affected_orders: order lines that need one of all_affected_products AT one
# of destination_plants specifically (line-level plant, not the generic
# order->contains->product graph edge, which is not plant-scoped)
ol_scope = order_line[order_line.PRODUCT_ID.isin(all_affected_products) & order_line.PLANT_ID.isin(destination_plants)]
affected_orders = set(ol_scope.CANONICAL_ORDER_ID)

# affected_customers: ORDER -> belongs_to -> Customer
affected_customers = set()
for oid in affected_orders:
    affected_customers |= set(edges_where(from_type="ORDER", from_id=oid, rel="belongs_to").TO_ID)

def name_lookup(df, id_col, name_col, ids):
    return df[df[id_col].isin(ids)][[id_col, name_col]].to_dict("records")

result = {
    "shipment_id": SHIPMENT_ID, "delay_days": DELAY_DAYS,
    "direct_products": name_lookup(product, "CANONICAL_PRODUCT_ID", "PRODUCT_NAME", direct_products),
    "downstream_finished_goods": name_lookup(product, "CANONICAL_PRODUCT_ID", "PRODUCT_NAME", finished_goods),
    "affected_plants": name_lookup(plant, "CANONICAL_PLANT_ID", "PLANT_NAME", affected_plants),
    "affected_production_orders": sorted(affected_prod_orders),
    "affected_orders": sorted(affected_orders),
    "affected_customers": name_lookup(customer, "CANONICAL_CUSTOMER_ID", "CUSTOMER_NAME", affected_customers),
}

# ---------------------------------------------------------------
# Financial impact estimate (mirrors sql/18_financial_impact_estimation.sql)
# ---------------------------------------------------------------
ol = order_line.copy()
ol["UNIT_PRICE"] = pd.to_numeric(ol.UNIT_PRICE, errors="coerce")
ol["QUANTITY"] = pd.to_numeric(ol.QUANTITY, errors="coerce")
po_lines = ol.merge(order[["CANONICAL_ORDER_ID", "ORDER_TYPE"]], on="CANONICAL_ORDER_ID")
po_lines = po_lines[po_lines.ORDER_TYPE == "PURCHASE"]
avg_price_by_product = po_lines.groupby("PRODUCT_ID").UNIT_PRICE.mean()

def estimated_order_value(order_id):
    lines = order_line[order_line.CANONICAL_ORDER_ID == order_id].copy()
    lines["QUANTITY"] = pd.to_numeric(lines.QUANTITY, errors="coerce")
    lines["proxy_price"] = lines.PRODUCT_ID.map(avg_price_by_product).fillna(0)
    return (lines.QUANTITY * lines.proxy_price).sum()

total_order_value = sum(estimated_order_value(oid) for oid in affected_orders)

RATES = {"PRODUCTION_DISRUPTION_PER_PLANT_PER_DAY": 5000, "EXPEDITED_SHIPPING_PCT": 0.15,
        "INVENTORY_CARRYING_ANNUAL_PCT": 0.20, "REVENUE_AT_RISK_PCT": 0.10}

operational_impact = len(affected_plants) * RATES["PRODUCTION_DISRUPTION_PER_PLANT_PER_DAY"] * DELAY_DAYS
logistics_expedite = total_order_value * RATES["EXPEDITED_SHIPPING_PCT"]
logistics_carrying = total_order_value * RATES["INVENTORY_CARRYING_ANNUAL_PCT"] * (DELAY_DAYS / 365.0)
logistics_impact = logistics_expedite + logistics_carrying
customer_revenue_impact = total_order_value * RATES["REVENUE_AT_RISK_PCT"]
total_impact = operational_impact + logistics_impact + customer_revenue_impact

result["financial_impact"] = {
    "estimated_total_affected_order_value_proxy": round(total_order_value, 2),
    "operational_impact_production_disruption": round(operational_impact, 2),
    "logistics_impact_expedited_shipping": round(logistics_expedite, 2),
    "logistics_impact_inventory_carrying": round(logistics_carrying, 2),
    "logistics_impact_total": round(logistics_impact, 2),
    "customer_revenue_impact": round(customer_revenue_impact, 2),
    "estimated_total_impact": round(total_impact, 2),
}

with open("generators/state/impact_analysis_demo_results.json", "w") as f:
    json.dump(result, f, indent=2, default=str)

print(json.dumps(result, indent=2, default=str))
