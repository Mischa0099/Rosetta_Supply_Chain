"""
Master 'real world' entities that get realized differently in ERP A (SAP-like)
and ERP B (Oracle/custom-like). This is what makes schema mapping + entity
resolution demonstrable: the SAME real supplier/material/plant exists under
two different ID schemes and slightly different naming conventions.
"""
import random
from faker import Faker

random.seed(42)
fake = Faker()
Faker.seed(42)

# ---------------------------------------------------------------
# SUPPLIERS (real-world master list)
# 18 real suppliers total.
#   - 12 appear in BOTH ERP A and ERP B  -> entity resolution / mapping test
#   -  3 appear ONLY in ERP A
#   -  3 appear ONLY in ERP B
# ---------------------------------------------------------------
SUPPLIER_NAMES = [
    "Meridian Steel Works", "Pacific Components Ltd", "Nordic Precision Parts",
    "Anand Auto Components", "Shenzhen Circuit Solutions", "Rhineland Fasteners GmbH",
    "Atlas Packaging Group", "Delta Plastics Inc", "Kyoto Machine Tools",
    "Sierra Electronics Corp", "BlueRiver Chemicals", "Continental Bearings SA",
    "Summit Forge & Casting", "Everest Rubber Industries", "Orion Semiconductor",
    "Coastal Logistics Supply", "Highland Textile Mills", "Vantage Industrial Gases",
]
random.shuffle(SUPPLIER_NAMES)
BOTH_SUPPLIERS = SUPPLIER_NAMES[:12]
ERP_A_ONLY_SUPPLIERS = SUPPLIER_NAMES[12:15]
ERP_B_ONLY_SUPPLIERS = SUPPLIER_NAMES[15:18]

COUNTRIES_TZ = [
    ("USA", "America/New_York"), ("USA", "America/Chicago"), ("Germany", "Europe/Berlin"),
    ("India", "Asia/Kolkata"), ("China", "Asia/Shanghai"), ("Japan", "Asia/Tokyo"),
    ("Mexico", "America/Mexico_City"), ("Brazil", "America/Sao_Paulo"),
    ("UK", "Europe/London"), ("South Korea", "Asia/Seoul"),
]

master_suppliers = []
for i, name in enumerate(SUPPLIER_NAMES):
    country, tz = random.choice(COUNTRIES_TZ)
    master_suppliers.append({
        "master_key": f"MS-SUP-{i+1:03d}",
        "name": name,
        "country": country,
        "timezone": tz,
        "in_erp_a": name in BOTH_SUPPLIERS or name in ERP_A_ONLY_SUPPLIERS,
        "in_erp_b": name in BOTH_SUPPLIERS or name in ERP_B_ONLY_SUPPLIERS,
    })

# ---------------------------------------------------------------
# MATERIALS / PRODUCTS (real-world master list)
# 40 real products. 26 appear in BOTH ERPs, 7 only in A, 7 only in B.
# ---------------------------------------------------------------
PRODUCT_CATEGORIES = ["Steel Bracket", "Circuit Board", "Rubber Gasket", "Bearing Assembly",
                       "Plastic Housing", "Fastener Kit", "Wiring Harness", "Sensor Module",
                       "Aluminum Panel", "Hydraulic Valve", "Motor Coil", "Gear Assembly",
                       "Battery Pack", "Display Unit", "Cooling Fan", "Chemical Coating",
                       "Textile Roll", "Industrial Gas Cylinder", "Machined Shaft", "Forged Flange"]

master_products = []
pid = 1
for cat in PRODUCT_CATEGORIES:
    for variant in ["Standard", "Heavy-Duty"]:
        master_products.append({
            "master_key": f"MS-PRD-{pid:03d}",
            "name": f"{variant} {cat}",
            "category": cat.split()[-1] if len(cat.split()) <= 2 else cat,
            "unit_of_measure": random.choice(["EA", "KG", "M", "L"]),
        })
        pid += 1

random.shuffle(master_products)
BOTH_PRODUCTS = master_products[:26]
ERP_A_ONLY_PRODUCTS = master_products[26:33]
ERP_B_ONLY_PRODUCTS = master_products[33:40]
for p in master_products:
    p["in_erp_a"] = p in BOTH_PRODUCTS or p in ERP_A_ONLY_PRODUCTS
    p["in_erp_b"] = p in BOTH_PRODUCTS or p in ERP_B_ONLY_PRODUCTS

# ---------------------------------------------------------------
# PLANTS (real-world master list) - 6 plants, all shared across both ERPs
# (a company's own plants are usually visible in every internal system)
# ---------------------------------------------------------------
PLANT_DEFS = [
    ("Columbus Plant", "USA", "America/New_York"),
    ("Guadalajara Plant", "Mexico", "America/Mexico_City"),
    ("Pune Plant", "India", "Asia/Kolkata"),
    ("Shenzhen Plant", "China", "Asia/Shanghai"),
    ("Stuttgart Plant", "Germany", "Europe/Berlin"),
    ("Sao Paulo Plant", "Brazil", "America/Sao_Paulo"),
]
master_plants = []
for i, (name, country, tz) in enumerate(PLANT_DEFS):
    master_plants.append({
        "master_key": f"MS-PLT-{i+1:03d}",
        "name": name, "country": country, "timezone": tz,
    })

if __name__ == "__main__":
    print(f"Suppliers: {len(master_suppliers)} (both={len(BOTH_SUPPLIERS)}, "
          f"A-only={len(ERP_A_ONLY_SUPPLIERS)}, B-only={len(ERP_B_ONLY_SUPPLIERS)})")
    print(f"Products: {len(master_products)} (both={len(BOTH_PRODUCTS)}, "
          f"A-only={len(ERP_A_ONLY_PRODUCTS)}, B-only={len(ERP_B_ONLY_PRODUCTS)})")
    print(f"Plants: {len(master_plants)}")
