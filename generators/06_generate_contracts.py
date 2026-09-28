"""
Synthetic supplier contracts (unstructured text) for the document-extraction
component (section 15) and Test 8. Written in a realistic prose/clause style
so extraction has to actually parse language, not just split on labels.
A ground-truth manifest is kept separately in docs/ to score extraction accuracy.
"""
import random, os, csv, json
from datetime import date, timedelta
import pandas as pd

random.seed(505)
OUT = "./contracts"
os.makedirs(OUT, exist_ok=True)

df = pd.read_csv("docs/golden_entity_crosswalk.csv")
suppliers = df[df["entity_type"] == "Supplier"].sample(10, random_state=7).to_dict("records")

DELIVERY_TERMS = ["FOB Origin", "FOB Destination", "DDP", "CIF", "Ex Works", "DAP"]
PRODUCT_POOL = ["steel brackets", "circuit boards", "rubber gaskets", "bearing assemblies",
                "plastic housings", "fastener kits", "wiring harnesses", "sensor modules",
                "aluminum panels", "hydraulic valves"]

manifest_rows = []
for i, s in enumerate(suppliers, start=1):
    contract_id = f"C{100 + i}"
    effective = date(2026, 1, 1) - timedelta(days=random.randint(0, 400))
    term_months = random.choice([12, 18, 24, 36])
    expiration = date(effective.year + term_months // 12, effective.month, 1) if effective.month == 1 else effective.replace(
        year=effective.year + (term_months // 12), day=min(effective.day, 28))
    sla_days = random.choice([3, 5, 7, 10, 14])
    lead_time_days = random.choice([7, 10, 14, 21, 30])
    delivery_term = random.choice(DELIVERY_TERMS)
    penalty_pct = random.choice([1, 1.5, 2, 2.5])
    products = random.sample(PRODUCT_POOL, random.randint(1, 3))
    currency = random.choice(["USD", "EUR", "INR"])
    min_otd = random.choice([90, 92, 95, 97])

    text = f"""SUPPLY AGREEMENT

Contract Reference: {contract_id}
Supplier: {s['real_name']}
Buyer: Adaptive Supply Chain Intelligence Corp ("Buyer")

1. TERM
This Agreement is effective as of {effective.strftime('%B %d, %Y')} ("Effective Date") and shall
remain in force for a period of {term_months} months, expiring on
{expiration.strftime('%B %d, %Y')} ("Expiration Date"), unless terminated earlier in accordance
with the provisions herein.

2. SCOPE OF SUPPLY
The Supplier agrees to manufacture and deliver the following product categories to Buyer's
designated plants: {', '.join(products)}.

3. DELIVERY TERMS
All shipments under this Agreement shall be delivered {delivery_term}. The standard
manufacturing and shipment lead time shall not exceed {lead_time_days} days from the date of
Buyer's purchase order confirmation.

4. SERVICE LEVEL AGREEMENT
Supplier shall deliver all purchase orders within {sla_days} days of the promised delivery date
communicated at order confirmation. Supplier shall maintain a minimum on-time delivery (OTD)
performance of {min_otd}% measured on a rolling quarterly basis, calculated as the number of
shipments delivered on or before the promised delivery date divided by total eligible shipments
in the period.

5. PRICING AND CURRENCY
All prices under this Agreement are denominated in {currency} and are subject to review on each
anniversary of the Effective Date.

6. PENALTIES
In the event Supplier fails to meet the SLA defined in Section 4 for any given calendar quarter,
Buyer may assess a service credit equal to {penalty_pct}% of the affected purchase order value.

7. GOVERNING LAW
This Agreement shall be governed by the laws applicable to the Buyer's principal place of
business.

Signed,
Buyer Procurement Representative                    Supplier Authorized Representative
"""
    with open(f"{OUT}/contract_{contract_id}.txt", "w") as f:
        f.write(text)

    manifest_rows.append({
        "contract_id": contract_id, "supplier_real_name": s["real_name"],
        "supplier_master_key": s["master_key"], "effective_date": effective.isoformat(),
        "expiration_date": expiration.isoformat(), "term_months": term_months,
        "sla_days": sla_days, "lead_time_days": lead_time_days, "delivery_term": delivery_term,
        "min_otd_pct": min_otd, "penalty_pct": penalty_pct, "currency": currency,
        "applicable_products": "; ".join(products),
    })

pd.DataFrame(manifest_rows).to_csv("docs/contracts_ground_truth.csv", index=False)
print(f"Generated {len(manifest_rows)} synthetic contracts")
