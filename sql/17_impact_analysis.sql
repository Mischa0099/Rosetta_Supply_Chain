-- =====================================================================
-- PHASE 4: IMPACT ANALYSIS (spec section 17)
-- Given a delayed/disrupted shipment, trace the full downstream chain:
--   Shipment -> Product(s) transported
--            -> (if a raw material) Finished Goods that require it (BOM)
--            -> Plants that manufacture those finished goods
--            -> Production Orders producing them
--            -> Sales Orders containing the affected product(s)
--            -> Customers on those orders
-- =====================================================================

USE DATABASE SUPPLY_CHAIN_PLATFORM;
USE SCHEMA SUPPLY_CHAIN_PLATFORM.INTELLIGENCE;

-- SCOPING RULE (important): a delayed INBOUND shipment only disrupts
-- production AT THE PLANT IT WAS ACTUALLY HEADED TO - not every plant
-- company-wide that happens to also use the same generic raw material.
-- Without this scope, walking Product->requires->Product and
-- Order->contains->Product unscoped sweeps in every unrelated order in
-- the whole company that ever touches this product category, wildly
-- overstating blast radius (an earlier version of this function did
-- exactly that and produced a company-wide "impact" for one shipment -
-- not a useful answer). So: first resolve the shipment's destination
-- plant via Shipment->fulfills->Order->fulfilled_at->Plant, then scope
-- every downstream step to that plant.
CREATE OR REPLACE FUNCTION IMPACT_ANALYSIS_SHIPMENT(P_SHIPMENT_ID VARCHAR)
RETURNS TABLE (IMPACT_CATEGORY VARCHAR, ENTITY_TYPE VARCHAR, ENTITY_ID VARCHAR, ENTITY_NAME VARCHAR)
AS
$$
    WITH direct_products AS (
        SELECT TO_ID AS product_id
        FROM SUPPLY_CHAIN_PLATFORM.ONTOLOGY_GRAPH.RELATIONSHIP_EDGES
        WHERE FROM_TYPE = 'SHIPMENT' AND FROM_ID = P_SHIPMENT_ID AND RELATIONSHIP = 'transports'
    ),
    destination_plants AS (
        SELECT DISTINCT oe.TO_ID AS plant_id
        FROM SUPPLY_CHAIN_PLATFORM.ONTOLOGY_GRAPH.RELATIONSHIP_EDGES se
        JOIN SUPPLY_CHAIN_PLATFORM.ONTOLOGY_GRAPH.RELATIONSHIP_EDGES oe
            ON oe.FROM_TYPE = 'ORDER' AND oe.FROM_ID = se.TO_ID AND oe.RELATIONSHIP = 'fulfilled_at'
        WHERE se.FROM_TYPE = 'SHIPMENT' AND se.FROM_ID = P_SHIPMENT_ID AND se.RELATIONSHIP = 'fulfills'
    ),
    candidate_finished_goods AS (
        -- Products that REQUIRE (via Bill of Materials) one of the directly-shipped products as a raw material
        SELECT DISTINCT e.FROM_ID AS product_id
        FROM SUPPLY_CHAIN_PLATFORM.ONTOLOGY_GRAPH.RELATIONSHIP_EDGES e
        JOIN direct_products dp ON e.TO_ID = dp.product_id
        WHERE e.RELATIONSHIP = 'requires' AND e.FROM_TYPE = 'PRODUCT'
    ),
    finished_goods AS (
        -- ...restricted to those actually manufactured at the destination plant(s)
        SELECT DISTINCT cfg.product_id
        FROM candidate_finished_goods cfg
        JOIN SUPPLY_CHAIN_PLATFORM.ONTOLOGY_GRAPH.RELATIONSHIP_EDGES e
            ON e.FROM_TYPE = 'PLANT' AND e.TO_ID = cfg.product_id AND e.RELATIONSHIP = 'produces'
        JOIN destination_plants dp ON dp.plant_id = e.FROM_ID
    ),
    all_affected_products AS (
        SELECT product_id FROM direct_products
        UNION
        SELECT product_id FROM finished_goods
    ),
    affected_plants AS (
        SELECT plant_id FROM destination_plants
    ),
    affected_production_orders AS (
        SELECT DISTINCT e.FROM_ID AS production_order_id
        FROM SUPPLY_CHAIN_PLATFORM.ONTOLOGY_GRAPH.RELATIONSHIP_EDGES e
        JOIN finished_goods fg ON e.TO_ID = fg.product_id
        WHERE e.RELATIONSHIP = 'produces' AND e.FROM_TYPE = 'PRODUCTION_ORDER'
    ),
    affected_orders AS (
        -- Line-level, plant-scoped (not the unscoped Order->contains->Product
        -- graph edge, which has no plant context of its own)
        SELECT DISTINCT ol.CANONICAL_ORDER_ID AS order_id
        FROM SUPPLY_CHAIN_PLATFORM.ONTOLOGY_CORE.ORDER_LINE ol
        JOIN all_affected_products p ON p.product_id = ol.PRODUCT_ID
        JOIN destination_plants dp ON dp.plant_id = ol.PLANT_ID
    ),
    affected_customers AS (
        SELECT DISTINCT e.TO_ID AS customer_id
        FROM SUPPLY_CHAIN_PLATFORM.ONTOLOGY_GRAPH.RELATIONSHIP_EDGES e
        JOIN affected_orders o ON e.FROM_ID = o.order_id
        WHERE e.RELATIONSHIP = 'belongs_to' AND e.FROM_TYPE = 'ORDER'
    )
    SELECT 'DIRECT_PRODUCT', 'PRODUCT', dp.product_id, p.PRODUCT_NAME
        FROM direct_products dp JOIN SUPPLY_CHAIN_PLATFORM.ONTOLOGY_CORE.PRODUCT p ON p.CANONICAL_PRODUCT_ID = dp.product_id
    UNION ALL
    SELECT 'DOWNSTREAM_FINISHED_GOOD', 'PRODUCT', fg.product_id, p.PRODUCT_NAME
        FROM finished_goods fg JOIN SUPPLY_CHAIN_PLATFORM.ONTOLOGY_CORE.PRODUCT p ON p.CANONICAL_PRODUCT_ID = fg.product_id
    UNION ALL
    SELECT 'AFFECTED_PLANT', 'PLANT', ap.plant_id, pl.PLANT_NAME
        FROM affected_plants ap JOIN SUPPLY_CHAIN_PLATFORM.ONTOLOGY_CORE.PLANT pl ON pl.CANONICAL_PLANT_ID = ap.plant_id
    UNION ALL
    SELECT 'AFFECTED_PRODUCTION_ORDER', 'PRODUCTION_ORDER', production_order_id, production_order_id
        FROM affected_production_orders
    UNION ALL
    SELECT 'AFFECTED_ORDER', 'ORDER', order_id, order_id
        FROM affected_orders
    UNION ALL
    SELECT 'AFFECTED_CUSTOMER', 'CUSTOMER', ac.customer_id, c.CUSTOMER_NAME
        FROM affected_customers ac JOIN SUPPLY_CHAIN_PLATFORM.ONTOLOGY_CORE.CUSTOMER c ON c.CANONICAL_CUSTOMER_ID = ac.customer_id
$$;

-- Summary rollup: affected-entity counts by category, for the impact
-- analysis card ("Affected plants: 2, Affected orders: 14, ...")
CREATE OR REPLACE FUNCTION IMPACT_ANALYSIS_SUMMARY(P_SHIPMENT_ID VARCHAR)
RETURNS TABLE (IMPACT_CATEGORY VARCHAR, AFFECTED_COUNT NUMBER)
AS
$$
    SELECT IMPACT_CATEGORY, COUNT(DISTINCT ENTITY_ID) AS AFFECTED_COUNT
    FROM TABLE(IMPACT_ANALYSIS_SHIPMENT(P_SHIPMENT_ID))
    GROUP BY IMPACT_CATEGORY
$$;

-- Example (see docs/impact_analysis_example.md for the full worked example
-- on the featured demo shipment):
-- SELECT * FROM TABLE(IMPACT_ANALYSIS_SHIPMENT('SHP-100001'));
-- SELECT * FROM TABLE(IMPACT_ANALYSIS_SUMMARY('SHP-100001'));
