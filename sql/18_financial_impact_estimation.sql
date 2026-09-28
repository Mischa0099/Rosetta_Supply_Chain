-- =====================================================================
-- PHASE 4: OPERATIONAL-TO-FINANCIAL IMPACT (spec section 18)
-- Every number here is explicitly an ESTIMATE (guardrail #5) built from
-- configurable rates, never presented as an actual accounting figure.
-- =====================================================================

USE DATABASE SUPPLY_CHAIN_PLATFORM;
USE SCHEMA SUPPLY_CHAIN_PLATFORM.INTELLIGENCE;

-- ---------------------------------------------------------------
-- Configurable cost-estimation rates (Finance-owned, not hardcoded logic)
-- ---------------------------------------------------------------
CREATE OR REPLACE TABLE FINANCIAL_IMPACT_CONFIG (
    COST_COMPONENT      VARCHAR(50) NOT NULL,
    RATE_VALUE             NUMBER(10,4),
    RATE_DESCRIPTION          VARCHAR(200),
    CONSTRAINT PK_FIN_CONFIG PRIMARY KEY (COST_COMPONENT)
);
INSERT INTO FINANCIAL_IMPACT_CONFIG VALUES
    ('PRODUCTION_DISRUPTION_PER_PLANT_PER_DAY', 5000, 'Estimated cost of one affected plant running below plan for one day (USD)'),
    ('EXPEDITED_SHIPPING_PCT_OF_ORDER_VALUE',   0.15, 'Extra freight cost to expedite an at-risk order, as a % of that order''s value'),
    ('INVENTORY_CARRYING_ANNUAL_PCT',           0.20, 'Annual inventory carrying cost as a % of held value; prorated by delay_days/365'),
    ('REVENUE_AT_RISK_PCT_OF_ORDER_VALUE',      0.10, 'Conservative share of an affected order''s value treated as genuinely at risk (not 100% - most delays do not cancel the order)');

-- ---------------------------------------------------------------
-- Proxy order value: Sales Order lines in this dataset don't carry a
-- price (real ERPs usually price at invoicing, not order entry), so
-- revenue-at-risk uses each product's average PURCHASE unit price as a
-- cost proxy. This is explicitly an approximation - documented, not hidden.
-- ---------------------------------------------------------------
CREATE OR REPLACE VIEW AFFECTED_ORDER_VALUE_PROXY AS
WITH avg_product_price AS (
    SELECT ol.PRODUCT_ID, AVG(ol.UNIT_PRICE) AS AVG_UNIT_PRICE
    FROM SUPPLY_CHAIN_PLATFORM.ONTOLOGY_CORE.ORDER_LINE ol
    JOIN SUPPLY_CHAIN_PLATFORM.ONTOLOGY_CORE.ORDERS o ON o.CANONICAL_ORDER_ID = ol.CANONICAL_ORDER_ID
    WHERE o.ORDER_TYPE = 'PURCHASE' AND ol.UNIT_PRICE IS NOT NULL
    GROUP BY ol.PRODUCT_ID
)
SELECT ol.CANONICAL_ORDER_ID, SUM(ol.QUANTITY * COALESCE(p.AVG_UNIT_PRICE, 0)) AS ESTIMATED_ORDER_VALUE
FROM SUPPLY_CHAIN_PLATFORM.ONTOLOGY_CORE.ORDER_LINE ol
LEFT JOIN avg_product_price p ON p.PRODUCT_ID = ol.PRODUCT_ID
GROUP BY ol.CANONICAL_ORDER_ID;

-- ---------------------------------------------------------------
-- Full financial impact summary for one delayed shipment
-- ---------------------------------------------------------------
CREATE OR REPLACE FUNCTION FINANCIAL_IMPACT_ESTIMATE(P_SHIPMENT_ID VARCHAR, P_DELAY_DAYS NUMBER)
RETURNS TABLE (IMPACT_TYPE VARCHAR, ESTIMATED_AMOUNT NUMBER(15,2), BASIS VARCHAR)
AS
$$
    WITH counts AS (
        SELECT
            SUM(IFF(IMPACT_CATEGORY = 'AFFECTED_PLANT', 1, 0)) AS n_plants,
            SUM(IFF(IMPACT_CATEGORY = 'AFFECTED_ORDER', 1, 0)) AS n_orders
        FROM TABLE(SUPPLY_CHAIN_PLATFORM.INTELLIGENCE.IMPACT_ANALYSIS_SHIPMENT(P_SHIPMENT_ID))
    ),
    affected_order_ids AS (
        SELECT ENTITY_ID AS order_id
        FROM TABLE(SUPPLY_CHAIN_PLATFORM.INTELLIGENCE.IMPACT_ANALYSIS_SHIPMENT(P_SHIPMENT_ID))
        WHERE IMPACT_CATEGORY = 'AFFECTED_ORDER'
    ),
    order_value AS (
        SELECT SUM(v.ESTIMATED_ORDER_VALUE) AS total_value
        FROM affected_order_ids a
        JOIN AFFECTED_ORDER_VALUE_PROXY v ON v.CANONICAL_ORDER_ID = a.order_id
    ),
    rates AS (
        SELECT
            MAX(IFF(COST_COMPONENT = 'PRODUCTION_DISRUPTION_PER_PLANT_PER_DAY', RATE_VALUE, NULL)) AS r_prod,
            MAX(IFF(COST_COMPONENT = 'EXPEDITED_SHIPPING_PCT_OF_ORDER_VALUE', RATE_VALUE, NULL)) AS r_ship,
            MAX(IFF(COST_COMPONENT = 'INVENTORY_CARRYING_ANNUAL_PCT', RATE_VALUE, NULL)) AS r_carry,
            MAX(IFF(COST_COMPONENT = 'REVENUE_AT_RISK_PCT_OF_ORDER_VALUE', RATE_VALUE, NULL)) AS r_revenue
        FROM FINANCIAL_IMPACT_CONFIG
    )
    SELECT 'OPERATIONAL_IMPACT_PRODUCTION_DISRUPTION',
           ROUND(c.n_plants * r.r_prod * P_DELAY_DAYS, 2),
           c.n_plants || ' affected plant(s) x $' || r.r_prod || '/day x ' || P_DELAY_DAYS || ' day(s) delay'
    FROM counts c, rates r
    UNION ALL
    SELECT 'LOGISTICS_IMPACT_EXPEDITED_SHIPPING',
           ROUND(COALESCE(ov.total_value, 0) * r.r_ship, 2),
           'Estimated order value at risk x ' || (r.r_ship * 100) || '% expedite premium'
    FROM order_value ov, rates r
    UNION ALL
    SELECT 'LOGISTICS_IMPACT_INVENTORY_CARRYING',
           ROUND(COALESCE(ov.total_value, 0) * r.r_carry * (P_DELAY_DAYS / 365.0), 2),
           'Estimated order value x ' || (r.r_carry * 100) || '% annual carrying rate, prorated ' || P_DELAY_DAYS || '/365 days'
    FROM order_value ov, rates r
    UNION ALL
    SELECT 'CUSTOMER_REVENUE_IMPACT',
           ROUND(COALESCE(ov.total_value, 0) * r.r_revenue, 2),
           'Estimated order value x ' || (r.r_revenue * 100) || '% at-risk share (conservative - most delays do not cancel the order)'
    FROM order_value ov, rates r
$$;

-- Example:
-- SELECT * FROM TABLE(FINANCIAL_IMPACT_ESTIMATE('SHP-100001', 4));
-- SELECT IMPACT_TYPE, ESTIMATED_AMOUNT FROM TABLE(FINANCIAL_IMPACT_ESTIMATE('SHP-100001', 4))
-- UNION ALL SELECT 'TOTAL_ESTIMATED_IMPACT', SUM(ESTIMATED_AMOUNT) FROM TABLE(FINANCIAL_IMPACT_ESTIMATE('SHP-100001', 4));
-- Every row here MUST be rendered with an "ESTIMATE" label in any UI - never as an actual accounting figure.
