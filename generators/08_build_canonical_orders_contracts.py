"""
Canonical ORDER (+ ORDER_LINE), CONTRACT, and TRANSACTION.
ORDER unifies Purchase Orders and Sales Orders from both ERPs into one
generic business concept (ORDER_TYPE = PURCHASE | SALES), matching the
ontology relationships:
  Supplier -> fulfills -> Purchase Order
  Purchase Order -> contains -> Product
  Order -> belongs_to -> Customer
"""
import os, json
import pandas as pd
from importlib.machinery import SourceFileLoader
master = SourceFileLoader("master", "generators/00_master_entities.py").load_module()

SRC = "./csv"
OUT = "./csv/ontology_core"

with open("generators/state/canonical_lookups.json") as f:
    lk = json.load(f)

erp_a_po = pd.read_csv(f"{SRC}/erp_a/purchase_orders.csv", dtype=str)
erp_a_poi = pd.read_csv(f"{SRC}/erp_a/purchase_order_items.csv", dtype=str)
erp_b_po = pd.read_csv(f"{SRC}/erp_b/purchase_orders.csv", dtype=str)
erp_b_pol = pd.read_csv(f"{SRC}/erp_b/purchase_order_lines.csv", dtype=str)
erp_a_so = pd.read_csv(f"{SRC}/erp_a/sales_orders.csv", dtype=str)
erp_a_soi = pd.read_csv(f"{SRC}/erp_a/sales_order_items.csv", dtype=str)
erp_b_so = pd.read_csv(f"{SRC}/erp_b/sales_orders.csv", dtype=str)
erp_b_sol = pd.read_csv(f"{SRC}/erp_b/sales_order_lines.csv", dtype=str)

orders, lines = [], []

# --- ERP A Purchase Orders ---
for _, po in erp_a_po.iterrows():
    orders.append({"CANONICAL_ORDER_ID": f"ORD-A-PO-{po.EBELN}", "ORDER_TYPE": "PURCHASE",
                    "SOURCE_SYSTEM": "ERP_A", "SOURCE_DOC_ID": po.EBELN,
                    "SUPPLIER_ID": lk["erp_a_lifnr_to_canonical"].get(po.LIFNR, ""),
                    "CUSTOMER_ID": "", "PLANT_ID": lk["erp_a_werks_to_canonical"].get(po.WERKS, ""),
                    "ORDER_DATE": po.BEDAT, "CURRENCY": po.WAERS})
for _, li in erp_a_poi.iterrows():
    matnr = str(li.MATNR).zfill(8)
    lines.append({"CANONICAL_ORDER_ID": f"ORD-A-PO-{li.EBELN}", "LINE_NUM": li.EBELP,
                  "PRODUCT_ID": lk["erp_a_material_to_canonical"].get(matnr, ""),
                  "PLANT_ID": lk["erp_a_werks_to_canonical"].get(li.WERKS, ""),
                  "QUANTITY": li.MENGE, "UNIT_PRICE": li.NETPR, "PROMISED_DATE": li.EINDT})

# --- ERP B Purchase Orders ---
for _, po in erp_b_po.iterrows():
    orders.append({"CANONICAL_ORDER_ID": f"ORD-B-PO-{po.PO_NUMBER}", "ORDER_TYPE": "PURCHASE",
                    "SOURCE_SYSTEM": "ERP_B", "SOURCE_DOC_ID": po.PO_NUMBER,
                    "SUPPLIER_ID": lk["erp_b_vendorid_to_canonical"].get(po.VENDOR_ID, ""),
                    "CUSTOMER_ID": "", "PLANT_ID": lk["erp_b_location_to_canonical"].get(po.LOCATION_CODE, ""),
                    "ORDER_DATE": po.ORDER_DATE, "CURRENCY": po.CURRENCY_CODE})
for _, li in erp_b_pol.iterrows():
    lines.append({"CANONICAL_ORDER_ID": f"ORD-B-PO-{li.PO_NUMBER}", "LINE_NUM": li.LINE_NUM,
                  "PRODUCT_ID": lk["erp_b_sku_to_canonical"].get(li.SKU, ""),
                  "PLANT_ID": lk["erp_b_location_to_canonical"].get(li.LOCATION_CODE, ""),
                  "QUANTITY": li.QUANTITY, "UNIT_PRICE": li.UNIT_PRICE, "PROMISED_DATE": li.PROMISE_DT})

# --- ERP A Sales Orders ---
for _, so in erp_a_so.iterrows():
    orders.append({"CANONICAL_ORDER_ID": f"ORD-A-SO-{so.VBELN}", "ORDER_TYPE": "SALES",
                    "SOURCE_SYSTEM": "ERP_A", "SOURCE_DOC_ID": so.VBELN, "SUPPLIER_ID": "",
                    "CUSTOMER_ID": lk["erp_a_kunnr_to_canonical"].get(str(so.KUNNR), ""),
                    "PLANT_ID": "", "ORDER_DATE": so.ERDAT, "CURRENCY": ""})
for _, li in erp_a_soi.iterrows():
    matnr = str(li.MATNR).zfill(8)
    lines.append({"CANONICAL_ORDER_ID": f"ORD-A-SO-{li.VBELN}", "LINE_NUM": li.POSNR,
                  "PRODUCT_ID": lk["erp_a_material_to_canonical"].get(matnr, ""),
                  "PLANT_ID": lk["erp_a_werks_to_canonical"].get(li.WERKS, ""),
                  "QUANTITY": li.KWMENG, "UNIT_PRICE": "", "PROMISED_DATE": ""})

# --- ERP B Sales Orders ---
for _, so in erp_b_so.iterrows():
    orders.append({"CANONICAL_ORDER_ID": f"ORD-B-SO-{so.ORDER_ID}", "ORDER_TYPE": "SALES",
                    "SOURCE_SYSTEM": "ERP_B", "SOURCE_DOC_ID": so.ORDER_ID, "SUPPLIER_ID": "",
                    "CUSTOMER_ID": lk["erp_b_customerid_to_canonical"].get(so.CUSTOMER_ID, ""),
                    "PLANT_ID": "", "ORDER_DATE": so.ORDER_DATE, "CURRENCY": ""})
for _, li in erp_b_sol.iterrows():
    lines.append({"CANONICAL_ORDER_ID": f"ORD-B-SO-{li.ORDER_ID}", "LINE_NUM": li.LINE_NUM,
                  "PRODUCT_ID": lk["erp_b_sku_to_canonical"].get(li.SKU, ""),
                  "PLANT_ID": lk["erp_b_location_to_canonical"].get(li.LOCATION_CODE, ""),
                  "QUANTITY": li.QTY_ORDERED, "UNIT_PRICE": "", "PROMISED_DATE": ""})

order_df = pd.DataFrame(orders)
line_df = pd.DataFrame(lines)
order_df.to_csv(f"{OUT}/order.csv", index=False)
line_df.to_csv(f"{OUT}/order_line.csv", index=False)
print("orders", len(order_df), "order lines", len(line_df))

# =====================================================================
# CANONICAL CONTRACT  (structured record; Phase 5 doc-extraction will
# populate this table for real - for now, use the contract ground truth
# as the structured output shape)
# =====================================================================
contracts_gt = pd.read_csv("docs/contracts_ground_truth.csv", dtype=str)
sup_lookup_by_name = {}
supplier_df = pd.read_csv(f"{OUT}/supplier.csv", dtype=str)
name_to_id = dict(zip(supplier_df.SUPPLIER_NAME, supplier_df.CANONICAL_SUPPLIER_ID))
rows = []
for _, c in contracts_gt.iterrows():
    rows.append({
        "CANONICAL_CONTRACT_ID": f"CS-CON-{c.contract_id}", "SOURCE_CONTRACT_ID": c.contract_id,
        "SUPPLIER_ID": name_to_id.get(c.supplier_real_name, ""),
        "EFFECTIVE_DATE": c.effective_date, "EXPIRATION_DATE": c.expiration_date,
        "SLA_DAYS": c.sla_days, "LEAD_TIME_DAYS": c.lead_time_days, "DELIVERY_TERM": c.delivery_term,
        "MIN_OTD_PCT": c.min_otd_pct, "PENALTY_PCT": c.penalty_pct, "CURRENCY": c.currency,
        "APPLICABLE_PRODUCTS": c.applicable_products,
        "EXTRACTION_CONFIDENCE": 0.0,  # placeholder: Phase 5 extraction will populate a real score
        "EXTRACTION_STATUS": "PENDING_AI_EXTRACTION",
    })
contract_df = pd.DataFrame(rows)
contract_df.to_csv(f"{OUT}/contract.csv", index=False)
print("contracts", len(contract_df))

# =====================================================================
# CANONICAL TRANSACTION  (lightweight event log: order-created events,
# used for lineage/timeline views; shipment events already live in the
# logistics domain and get pulled into the graph separately)
# =====================================================================
rows = []
for _, o in order_df.iterrows():
    rows.append({"TRANSACTION_ID": f"TXN-{o.CANONICAL_ORDER_ID}", "TRANSACTION_TYPE": f"{o.ORDER_TYPE}_ORDER_CREATED",
                "RELATED_ENTITY_TYPE": "ORDER", "RELATED_ENTITY_ID": o.CANONICAL_ORDER_ID,
                "TRANSACTION_DATE": o.ORDER_DATE, "SOURCE_SYSTEM": o.SOURCE_SYSTEM})
txn_df = pd.DataFrame(rows)
txn_df.to_csv(f"{OUT}/transaction.csv", index=False)
print("transactions", len(txn_df))
