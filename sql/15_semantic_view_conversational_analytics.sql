-- =====================================================================
-- PHASE 3: GOVERNED SEMANTIC VIEW (spec section 11-12)
-- A native Snowflake Semantic View so Cortex Analyst (or any NL interface)
-- can translate natural-language questions into queries against the
-- SAME governed facts/metrics defined in 14_canonical_metrics.sql - never
-- against raw ERP_A/ERP_B columns directly, and never re-deriving a
-- metric formula inline.
--
-- Persona wording is captured via WITH SYNONYMS on each dimension/metric,
-- which is how "delivery reliability" (Planning), "OTD" (Procurement) and
-- "delivered on time" (Logistics) all resolve to the SAME
-- on_time_delivery_rate metric (section 13, Test 2).
-- =====================================================================

USE DATABASE SUPPLY_CHAIN_PLATFORM;
USE SCHEMA SUPPLY_CHAIN_PLATFORM.SEMANTIC_LAYER;

CREATE OR REPLACE SEMANTIC VIEW SUPPLY_CHAIN_SEMANTIC_VIEW
  TABLES (
    supplier AS SUPPLY_CHAIN_PLATFORM.ONTOLOGY_CORE.SUPPLIER
        PRIMARY KEY (CANONICAL_SUPPLIER_ID)
        WITH SYNONYMS ('vendor', 'vendors', 'suppliers')
        COMMENT = 'Canonical supplier, deduplicated across ERP A and ERP B',

    product AS SUPPLY_CHAIN_PLATFORM.ONTOLOGY_CORE.PRODUCT
        PRIMARY KEY (CANONICAL_PRODUCT_ID)
        WITH SYNONYMS ('item', 'material', 'sku', 'part')
        COMMENT = 'Canonical product/material, deduplicated across ERP A and ERP B',

    plant AS SUPPLY_CHAIN_PLATFORM.ONTOLOGY_CORE.PLANT
        PRIMARY KEY (CANONICAL_PLANT_ID)
        WITH SYNONYMS ('factory', 'facility', 'location', 'site')
        COMMENT = 'Canonical manufacturing plant',

    customer AS SUPPLY_CHAIN_PLATFORM.ONTOLOGY_CORE.CUSTOMER
        PRIMARY KEY (CANONICAL_CUSTOMER_ID)
        WITH SYNONYMS ('client', 'buyer', 'account')
        COMMENT = 'Canonical customer',

    shipment_otd AS SUPPLY_CHAIN_PLATFORM.SEMANTIC_LAYER.FACT_SHIPMENT_OTD
        PRIMARY KEY (SHIPMENT_ID)
        COMMENT = 'One row per shipment with governed on-time-delivery eligibility/outcome already computed on timezone-normalized dates',

    order_line_fulfillment AS SUPPLY_CHAIN_PLATFORM.SEMANTIC_LAYER.FACT_ORDER_LINE_FULFILLMENT
        PRIMARY KEY (CANONICAL_ORDER_ID, LINE_NUM)
        COMMENT = 'One row per order line with governed fill-rate quantities already computed',

    inventory_doi AS SUPPLY_CHAIN_PLATFORM.SEMANTIC_LAYER.METRIC_DAYS_OF_INVENTORY
        COMMENT = 'Pre-aggregated Days of Inventory per product per plant',

    landed_cost AS SUPPLY_CHAIN_PLATFORM.SEMANTIC_LAYER.METRIC_LANDED_COST_BY_PRODUCT
        COMMENT = 'Pre-aggregated Landed Cost estimate per product per supplier'
  )

  RELATIONSHIPS (
    otd_to_supplier AS shipment_otd(SUPPLIER_ID) REFERENCES supplier(CANONICAL_SUPPLIER_ID),
    otd_to_plant AS shipment_otd(PLANT_ID) REFERENCES plant(CANONICAL_PLANT_ID),
    otd_to_customer AS shipment_otd(CUSTOMER_ID) REFERENCES customer(CANONICAL_CUSTOMER_ID),
    fulfillment_to_supplier AS order_line_fulfillment(SUPPLIER_ID) REFERENCES supplier(CANONICAL_SUPPLIER_ID),
    fulfillment_to_product AS order_line_fulfillment(PRODUCT_ID) REFERENCES product(CANONICAL_PRODUCT_ID),
    doi_to_product AS inventory_doi(PRODUCT_ID) REFERENCES product(CANONICAL_PRODUCT_ID),
    doi_to_plant AS inventory_doi(PLANT_ID) REFERENCES plant(CANONICAL_PLANT_ID),
    landed_cost_to_product AS landed_cost(PRODUCT_ID) REFERENCES product(CANONICAL_PRODUCT_ID),
    landed_cost_to_supplier AS landed_cost(SUPPLIER_ID) REFERENCES supplier(CANONICAL_SUPPLIER_ID)
  )

  FACTS (
    shipment_otd.is_eligible AS IS_ELIGIBLE
        COMMENT = 'TRUE if this shipment counts in the OTD denominator (has a promised date and reached DELIVERED status)',
    shipment_otd.is_on_time AS IS_ON_TIME
        COMMENT = 'TRUE if delivered on or before the promised delivery date (UTC-normalized)',
    order_line_fulfillment.quantity_ordered AS QUANTITY_ORDERED,
    order_line_fulfillment.quantity_delivered AS QUANTITY_DELIVERED
  )

  DIMENSIONS (
    supplier.supplier_name AS SUPPLIER_NAME
        WITH SYNONYMS ('vendor name', 'supplier')
        COMMENT = 'Supplier display name',
    supplier.country AS COUNTRY
        WITH SYNONYMS ('supplier country'),
    product.product_name AS PRODUCT_NAME
        WITH SYNONYMS ('item name', 'material name', 'part name'),
    product.category AS CATEGORY
        WITH SYNONYMS ('product category', 'item category'),
    plant.plant_name AS PLANT_NAME
        WITH SYNONYMS ('factory name', 'site name'),
    customer.customer_name AS CUSTOMER_NAME
        WITH SYNONYMS ('client name', 'account name'),
    shipment_otd.direction AS SHIPMENT_DIRECTION
        WITH SYNONYMS ('inbound or outbound'),
    shipment_otd.carrier_id AS CARRIER_ID
        WITH SYNONYMS ('carrier', 'freight carrier')
  )

  METRICS (
    shipment_otd.on_time_delivery_rate AS
        DIV0(COUNT_IF(shipment_otd.is_on_time), COUNT_IF(shipment_otd.is_eligible)) * 100
        WITH SYNONYMS ('OTD', 'on-time delivery', 'delivery reliability', 'delivery performance',
                        'percent delivered on time', 'how many shipments were delivered on time')
        COMMENT = 'Canonical On-Time Delivery Rate - see CANONICAL_METRICS for the full governed definition. Identical across Planning/Procurement/Logistics phrasing.',

    shipment_otd.eligible_shipment_count AS COUNT_IF(shipment_otd.is_eligible)
        WITH SYNONYMS ('eligible shipments', 'total shipments considered'),

    shipment_otd.on_time_shipment_count AS COUNT_IF(shipment_otd.is_on_time)
        WITH SYNONYMS ('on-time shipments', 'shipments delivered on time'),

    order_line_fulfillment.fill_rate AS
        DIV0(SUM(order_line_fulfillment.quantity_delivered), SUM(order_line_fulfillment.quantity_ordered)) * 100
        WITH SYNONYMS ('fill rate', 'order fill rate', 'percent of order delivered')
        COMMENT = 'Canonical Fill Rate - see CANONICAL_METRICS for the full governed definition.',

    inventory_doi.avg_days_of_inventory AS AVG(inventory_doi.DAYS_OF_INVENTORY)
        WITH SYNONYMS ('days of inventory', 'DOI', 'inventory coverage', 'days of stock'),

    landed_cost.avg_landed_cost AS AVG(landed_cost.LANDED_COST_ESTIMATE)
        WITH SYNONYMS ('landed cost', 'total cost to land', 'delivered cost')
        COMMENT = 'Estimate only - percent-of-cost model, not actual freight invoices (see section 18 guardrail).'
  );

-- Example NL -> governed query translations (what Cortex Analyst produces
-- under the hood when pointed at this semantic view):
--
-- Planning:    "What is Supplier ABC's delivery reliability?"
-- Procurement: "What is Supplier ABC's OTD?"
-- Logistics:   "How many ABC shipments were delivered on time?"
-- ALL THREE resolve to:
--   SELECT on_time_delivery_rate FROM SUPPLY_CHAIN_SEMANTIC_VIEW
--   WHERE supplier_name = 'Supplier ABC';
-- (Logistics' phrasing additionally surfaces on_time_shipment_count,
--  since it asked "how many" rather than "what rate" - same underlying
--  metric family, different but consistent facet.)
