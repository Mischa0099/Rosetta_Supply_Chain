-- =====================================================================
-- PHASE 3: CANONICAL METRICS (spec section 10)
-- Defined ONCE here, reused everywhere (semantic layer, conversational
-- analytics, all three personas). No agent, page, or query is allowed to
-- redefine these - governance rule #1/#2 in section 25.
-- =====================================================================

USE DATABASE SUPPLY_CHAIN_PLATFORM;
CREATE SCHEMA IF NOT EXISTS SUPPLY_CHAIN_PLATFORM.SEMANTIC_LAYER;
USE SCHEMA SUPPLY_CHAIN_PLATFORM.SEMANTIC_LAYER;

-- ---------------------------------------------------------------
-- Human-readable metric catalog (what the Trust Layer / Metric Lineage
-- Streamlit page shows for "Definition" - section 14, 22).
-- ---------------------------------------------------------------
CREATE OR REPLACE TABLE CANONICAL_METRICS (
    METRIC_NAME       VARCHAR(50) NOT NULL,
    DEFINITION          VARCHAR(1000),
    FORMULA               VARCHAR(500),
    ELIGIBILITY_RULE        VARCHAR(1000),
    OWNER                     VARCHAR(50),
    VERSION                     NUMBER(5,0) DEFAULT 1,
    CONSTRAINT PK_METRICS PRIMARY KEY (METRIC_NAME)
);

INSERT INTO CANONICAL_METRICS VALUES
('On-Time Delivery Rate',
 'The share of eligible shipments that arrived on or before their promised delivery date.',
 'SUM(is_on_time) / COUNT(eligible_shipments)',
 'A shipment is eligible once it has a non-null PROMISED_DELIVERY_DATE and STATUS = DELIVERED. In-transit/undelivered shipments are excluded from the denominator (not yet resolved) and surfaced separately as open exceptions, not counted as late or on-time.',
 'Logistics/Procurement Governance', 1),
('Fill Rate',
 'The share of ordered quantity that was actually delivered.',
 'SUM(quantity_delivered) / SUM(quantity_ordered)',
 'quantity_delivered = full order-line quantity if the fulfilling shipment reached STATUS = DELIVERED, else 0 (this dataset does not model partial-shipment splits). Order lines with a NULL PROMISED_DATE are still included in Fill Rate (a promise-date gap does not by itself mean nothing was delivered) but are flagged separately.',
 'Procurement Governance', 1),
('Days of Inventory',
 'How many days current on-hand stock would last at the recent average daily demand.',
 'quantity_on_hand / average_daily_demand',
 'average_daily_demand = SUM(sales order-line quantity in the trailing 90 days) / 90, per product per plant. Where average_daily_demand = 0 (no recent demand), Days of Inventory is returned as NULL, not infinity or zero - a data limitation to be stated, not silently defaulted.',
 'Planning Governance', 1),
('Landed Cost',
 'Total cost to get one unit of product to a plant: product cost plus freight, duties, handling, and any other configured cost components.',
 'unit_price + (unit_price * freight_pct) + (unit_price * duty_pct) + (unit_price * handling_pct) + other_configured_costs',
 'unit_price = average NETPR/UNIT_PRICE across that product''s purchase-order lines in the period. freight/duty/handling percentages come from LANDED_COST_CONFIG (configurable per supplier country); a MISSING config falls back to the DEFAULT row - which the answer trust layer must disclose as an estimate, not a precise figure (section 18 guardrail).',
 'Procurement Governance', 1);

-- ---------------------------------------------------------------
-- Configurable landed-cost cost components (section 10: "other configured
-- costs" - kept as data, not hardcoded logic, so Finance can retune).
-- ---------------------------------------------------------------
CREATE OR REPLACE TABLE LANDED_COST_CONFIG (
    SUPPLIER_COUNTRY   VARCHAR(2)  COMMENT 'NULL row = DEFAULT fallback',
    FREIGHT_PCT           NUMBER(5,4),
    DUTY_PCT                 NUMBER(5,4),
    HANDLING_PCT               NUMBER(5,4)
);
INSERT INTO LANDED_COST_CONFIG VALUES
    (NULL,  0.08, 0.05, 0.02),   -- DEFAULT fallback
    ('CN',  0.12, 0.09, 0.02),   -- longer ocean freight + tariffs
    ('IN',  0.10, 0.06, 0.02),
    ('DE',  0.06, 0.02, 0.02),
    ('US',  0.04, 0.00, 0.02),
    ('MX',  0.05, 0.01, 0.02),
    ('BR',  0.09, 0.07, 0.02),
    ('KR',  0.09, 0.04, 0.02),
    ('UK',  0.06, 0.02, 0.02);

-- =====================================================================
-- FACT VIEW: one row per shipment, with eligibility/on-time already
-- computed on the TIMEZONE-SAFE UTC delivery date from Phase 2. Every
-- persona-facing OTD query (section 12-13) filters/aggregates THIS view -
-- never recomputes on-time logic itself.
-- =====================================================================
CREATE OR REPLACE VIEW FACT_SHIPMENT_OTD AS
SELECT
    s.SHIPMENT_ID, s.SOURCE_ERP, s.DIRECTION, s.CARRIER_ID, s.STATUS,
    s.PROMISED_DELIVERY_DATE,
    tz.ACTUAL_DELIVERY_DATE_UTC,
    o.CANONICAL_ORDER_ID, o.SUPPLIER_ID, o.CUSTOMER_ID, o.PLANT_ID,
    (s.PROMISED_DELIVERY_DATE IS NOT NULL AND s.STATUS = 'DELIVERED') AS IS_ELIGIBLE,
    CASE WHEN s.PROMISED_DELIVERY_DATE IS NOT NULL AND s.STATUS = 'DELIVERED'
         THEN (tz.ACTUAL_DELIVERY_DATE_UTC <= s.PROMISED_DELIVERY_DATE) ELSE NULL END AS IS_ON_TIME
FROM SUPPLY_CHAIN_PLATFORM.RAW_LOGISTICS.SHIPMENTS s
JOIN SUPPLY_CHAIN_PLATFORM.GOVERNANCE.SHIPMENT_DELIVERY_TIMEZONE_SAFE tz ON tz.SHIPMENT_ID = s.SHIPMENT_ID
LEFT JOIN SUPPLY_CHAIN_PLATFORM.ONTOLOGY_CORE.ORDERS o
    ON o.SOURCE_SYSTEM = s.SOURCE_ERP AND o.SOURCE_DOC_ID = s.REFERENCE_DOC;

-- One governed rollup - ANY persona/filter combination is a WHERE/GROUP BY
-- on top of this SAME view, guaranteeing metric consistency (Test 2).
CREATE OR REPLACE VIEW METRIC_OTD_BY_SUPPLIER AS
SELECT SUPPLIER_ID,
       COUNT_IF(IS_ELIGIBLE) AS ELIGIBLE_SHIPMENTS,
       COUNT_IF(IS_ON_TIME) AS ON_TIME_SHIPMENTS,
       DIV0(COUNT_IF(IS_ON_TIME), COUNT_IF(IS_ELIGIBLE)) * 100 AS OTD_PCT
FROM FACT_SHIPMENT_OTD
WHERE DIRECTION = 'INBOUND'   -- supplier->plant shipments
GROUP BY SUPPLIER_ID;

CREATE OR REPLACE VIEW METRIC_OTD_BY_PLANT AS
SELECT PLANT_ID,
       COUNT_IF(IS_ELIGIBLE) AS ELIGIBLE_SHIPMENTS,
       COUNT_IF(IS_ON_TIME) AS ON_TIME_SHIPMENTS,
       DIV0(COUNT_IF(IS_ON_TIME), COUNT_IF(IS_ELIGIBLE)) * 100 AS OTD_PCT
FROM FACT_SHIPMENT_OTD
GROUP BY PLANT_ID;

-- =====================================================================
-- FILL RATE (order-line grain; Test 6: NULL promised dates are flagged,
-- never silently treated as on-time or as zero quantity)
-- =====================================================================
CREATE OR REPLACE VIEW FACT_ORDER_LINE_FULFILLMENT AS
SELECT
    ol.CANONICAL_ORDER_ID, ol.LINE_NUM, ol.PRODUCT_ID, ol.PLANT_ID,
    ol.QUANTITY AS QUANTITY_ORDERED, ol.PROMISED_DATE,
    (ol.PROMISED_DATE IS NULL) AS PROMISE_DATE_MISSING,
    o.SUPPLIER_ID, o.CUSTOMER_ID, o.ORDER_TYPE, o.SOURCE_SYSTEM, o.SOURCE_DOC_ID,
    sh.STATUS AS FULFILLING_SHIPMENT_STATUS,
    CASE WHEN sh.STATUS = 'DELIVERED' THEN ol.QUANTITY ELSE 0 END AS QUANTITY_DELIVERED
FROM SUPPLY_CHAIN_PLATFORM.ONTOLOGY_CORE.ORDER_LINE ol
JOIN SUPPLY_CHAIN_PLATFORM.ONTOLOGY_CORE.ORDERS o ON o.CANONICAL_ORDER_ID = ol.CANONICAL_ORDER_ID
LEFT JOIN SUPPLY_CHAIN_PLATFORM.RAW_LOGISTICS.SHIPMENTS sh
    ON sh.SOURCE_ERP = o.SOURCE_SYSTEM AND sh.REFERENCE_DOC = o.SOURCE_DOC_ID;

CREATE OR REPLACE VIEW METRIC_FILL_RATE_BY_SUPPLIER AS
SELECT SUPPLIER_ID,
       SUM(QUANTITY_ORDERED) AS TOTAL_QUANTITY_ORDERED,
       SUM(QUANTITY_DELIVERED) AS TOTAL_QUANTITY_DELIVERED,
       DIV0(SUM(QUANTITY_DELIVERED), SUM(QUANTITY_ORDERED)) * 100 AS FILL_RATE_PCT,
       COUNT_IF(PROMISE_DATE_MISSING) AS LINES_WITH_MISSING_PROMISE_DATE
FROM FACT_ORDER_LINE_FULFILLMENT
WHERE ORDER_TYPE = 'PURCHASE'
GROUP BY SUPPLIER_ID;

-- =====================================================================
-- DAYS OF INVENTORY
-- =====================================================================
CREATE OR REPLACE VIEW FACT_AVG_DAILY_DEMAND_90D AS
SELECT ol.PRODUCT_ID, ol.PLANT_ID,
       SUM(ol.QUANTITY) / 90.0 AS AVG_DAILY_DEMAND
FROM SUPPLY_CHAIN_PLATFORM.ONTOLOGY_CORE.ORDER_LINE ol
JOIN SUPPLY_CHAIN_PLATFORM.ONTOLOGY_CORE.ORDERS o ON o.CANONICAL_ORDER_ID = ol.CANONICAL_ORDER_ID
WHERE o.ORDER_TYPE = 'SALES' AND o.ORDER_DATE >= DATEADD('day', -90, CURRENT_DATE())
GROUP BY ol.PRODUCT_ID, ol.PLANT_ID;

CREATE OR REPLACE VIEW METRIC_DAYS_OF_INVENTORY AS
SELECT inv.CANONICAL_PRODUCT_ID AS PRODUCT_ID, wh.PLANT_ID,
       SUM(inv.QUANTITY_ON_HAND) AS QUANTITY_ON_HAND,
       d.AVG_DAILY_DEMAND,
       CASE WHEN d.AVG_DAILY_DEMAND IS NULL OR d.AVG_DAILY_DEMAND = 0 THEN NULL
            ELSE SUM(inv.QUANTITY_ON_HAND) / d.AVG_DAILY_DEMAND END AS DAYS_OF_INVENTORY
FROM SUPPLY_CHAIN_PLATFORM.ONTOLOGY_GOODS.INVENTORY inv
JOIN SUPPLY_CHAIN_PLATFORM.ONTOLOGY_GOODS.WAREHOUSE_MASTER wh ON wh.CANONICAL_WAREHOUSE_ID = inv.CANONICAL_WAREHOUSE_ID
LEFT JOIN FACT_AVG_DAILY_DEMAND_90D d ON d.PRODUCT_ID = inv.CANONICAL_PRODUCT_ID AND d.PLANT_ID = wh.PLANT_ID
GROUP BY inv.CANONICAL_PRODUCT_ID, wh.PLANT_ID, d.AVG_DAILY_DEMAND;

-- =====================================================================
-- LANDED COST
-- =====================================================================
CREATE OR REPLACE VIEW METRIC_LANDED_COST_BY_PRODUCT AS
WITH avg_cost AS (
    SELECT ol.PRODUCT_ID, o.SUPPLIER_ID, AVG(ol.UNIT_PRICE) AS AVG_UNIT_PRICE
    FROM SUPPLY_CHAIN_PLATFORM.ONTOLOGY_CORE.ORDER_LINE ol
    JOIN SUPPLY_CHAIN_PLATFORM.ONTOLOGY_CORE.ORDERS o ON o.CANONICAL_ORDER_ID = ol.CANONICAL_ORDER_ID
    WHERE o.ORDER_TYPE = 'PURCHASE' AND ol.UNIT_PRICE IS NOT NULL
    GROUP BY ol.PRODUCT_ID, o.SUPPLIER_ID
)
SELECT ac.PRODUCT_ID, ac.SUPPLIER_ID, ac.AVG_UNIT_PRICE,
       COALESCE(cfg.FREIGHT_PCT, dflt.FREIGHT_PCT) AS FREIGHT_PCT,
       COALESCE(cfg.DUTY_PCT, dflt.DUTY_PCT) AS DUTY_PCT,
       COALESCE(cfg.HANDLING_PCT, dflt.HANDLING_PCT) AS HANDLING_PCT,
       (cfg.SUPPLIER_COUNTRY IS NULL) AS USED_DEFAULT_CONFIG,
       ac.AVG_UNIT_PRICE * (1 + COALESCE(cfg.FREIGHT_PCT, dflt.FREIGHT_PCT)
                              + COALESCE(cfg.DUTY_PCT, dflt.DUTY_PCT)
                              + COALESCE(cfg.HANDLING_PCT, dflt.HANDLING_PCT)) AS LANDED_COST_ESTIMATE
FROM avg_cost ac
JOIN SUPPLY_CHAIN_PLATFORM.ONTOLOGY_CORE.SUPPLIER s ON s.CANONICAL_SUPPLIER_ID = ac.SUPPLIER_ID
LEFT JOIN LANDED_COST_CONFIG cfg ON cfg.SUPPLIER_COUNTRY = s.COUNTRY
CROSS JOIN (SELECT FREIGHT_PCT, DUTY_PCT, HANDLING_PCT FROM LANDED_COST_CONFIG WHERE SUPPLIER_COUNTRY IS NULL) dflt;

-- Landed cost is always an ESTIMATE (percent-of-cost model, not actual
-- freight invoices) - label it as such wherever surfaced (section 18).
