"""
SERVICES MODULE (adaptive ontology extension #2).
Small, standalone synthetic dataset - deliberately NOT derived from the
goods-oriented ERP data, to prove the ontology can host a services-based
business alongside a goods-based one without a redesign. Kept small since
the main demo narrative is goods/manufacturing; this exists to demonstrate
extensibility, not to be a fully fleshed-out domain.
"""
import random, os
from datetime import date, timedelta
import pandas as pd

random.seed(707)
OUT = "./csv/ontology_services"
os.makedirs(OUT, exist_ok=True)

PROVIDERS = ["Apex Facilities Maintenance", "Nimbus IT Managed Services",
             "Precision Equipment Calibration Co", "Guardian Security Services", "BrightPath Logistics Consulting"]
provider_rows = [{"CANONICAL_SERVICE_PROVIDER_ID": f"SVP-{i+1:03d}", "PROVIDER_NAME": p,
                  "COUNTRY": random.choice(["USA", "India", "Germany"])} for i, p in enumerate(PROVIDERS)]
pd.DataFrame(provider_rows).to_csv(f"{OUT}/service_provider.csv", index=False)

SERVICE_TYPES = ["Preventive Maintenance", "Equipment Calibration", "IT Helpdesk Support",
                  "On-site Security Coverage", "Logistics Process Audit"]
service_rows = [{"CANONICAL_SERVICE_ID": f"SVC-{i+1:03d}", "SERVICE_NAME": s,
                 "PROVIDER_ID": random.choice(provider_rows)["CANONICAL_SERVICE_PROVIDER_ID"]}
                for i, s in enumerate(SERVICE_TYPES)]
pd.DataFrame(service_rows).to_csv(f"{OUT}/service.csv", index=False)

plant_df = pd.read_csv("./csv/ontology_core/plant.csv")
order_rows, milestone_rows = [], []
for i in range(15):
    svc = random.choice(service_rows)
    plant = plant_df.sample(1, random_state=random.randint(1, 10**6)).iloc[0]
    start = date(2025, 9, 1) + timedelta(days=random.randint(0, 380))
    period_days = random.choice([30, 90, 180, 365])
    order_id = f"SVC-ORD-{2000+i}"
    order_rows.append({"CANONICAL_SERVICE_ORDER_ID": order_id, "SERVICE_ID": svc["CANONICAL_SERVICE_ID"],
                       "PLANT_ID": plant.CANONICAL_PLANT_ID, "SERVICE_PERIOD_START": start.isoformat(),
                       "SERVICE_PERIOD_END": (start + timedelta(days=period_days)).isoformat(),
                       "STATUS": random.choice(["ACTIVE", "COMPLETED", "PENDING_ACCEPTANCE"])})
    n_milestones = random.randint(1, 3)
    for m in range(n_milestones):
        m_date = start + timedelta(days=int(period_days * (m + 1) / (n_milestones + 1)))
        milestone_rows.append({"CANONICAL_SERVICE_ORDER_ID": order_id, "MILESTONE_SEQ": m + 1,
                              "MILESTONE_NAME": f"Milestone {m+1}", "DUE_DATE": m_date.isoformat(),
                              "ACCEPTANCE_STATUS": random.choice(["ACCEPTED", "PENDING", "REJECTED"])})
pd.DataFrame(order_rows).to_csv(f"{OUT}/service_order.csv", index=False)
pd.DataFrame(milestone_rows).to_csv(f"{OUT}/milestone.csv", index=False)

print("providers", len(provider_rows), "services", len(service_rows),
      "service_orders", len(order_rows), "milestones", len(milestone_rows))
