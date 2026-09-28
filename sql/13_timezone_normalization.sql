-- =====================================================================
-- PHASE 2: TIME-ZONE NORMALIZATION (spec section 9, Test 3)
--
-- RAW_LOGISTICS.SHIPMENT_EVENTS and RAW_IOT.WAREHOUSE_EVENTS store
-- EVENT_LOCAL_TIMESTAMP + EVENT_TIMEZONE exactly as each source system
-- recorded them (local time, not UTC). Two shipments departing at the
-- "same moment" from a Pune plant (Asia/Kolkata) and a Stuttgart plant
-- (Europe/Berlin) have different local clock values, and naive string/
-- datetime comparison across them would misorder events or misclassify
-- on-time vs late. These views fix that by converting to a single
-- canonical UTC timestamp while preserving the original local values.
-- =====================================================================

USE DATABASE SUPPLY_CHAIN_PLATFORM;
CREATE SCHEMA IF NOT EXISTS SUPPLY_CHAIN_PLATFORM.GOVERNANCE;
USE SCHEMA SUPPLY_CHAIN_PLATFORM.GOVERNANCE;

-- ---------------------------------------------------------------
-- Shipment events, UTC-normalized
-- ---------------------------------------------------------------
CREATE OR REPLACE VIEW SHIPMENT_EVENTS_UTC AS
SELECT
    SHIPMENT_ID, EVENT_SEQ, EVENT_TYPE,
    EVENT_LOCAL_TIMESTAMP,                                   -- original, preserved
    EVENT_TIMEZONE,                                           -- original, preserved
    CONVERT_TIMEZONE(EVENT_TIMEZONE, 'UTC', EVENT_LOCAL_TIMESTAMP) AS EVENT_TIMESTAMP_UTC,  -- canonical
    NOTES
FROM SUPPLY_CHAIN_PLATFORM.RAW_LOGISTICS.SHIPMENT_EVENTS;

-- ---------------------------------------------------------------
-- Warehouse events, UTC-normalized
-- ---------------------------------------------------------------
CREATE OR REPLACE VIEW WAREHOUSE_EVENTS_UTC AS
SELECT
    PLANT_MASTER_KEY, PLANT_NAME,
    EVENT_LOCAL_TIMESTAMP, EVENT_TIMEZONE,
    CONVERT_TIMEZONE(EVENT_TIMEZONE, 'UTC', EVENT_LOCAL_TIMESTAMP) AS EVENT_TIMESTAMP_UTC,
    EVENT_TYPE, QUANTITY
FROM SUPPLY_CHAIN_PLATFORM.RAW_IOT.WAREHOUSE_EVENTS;

-- ---------------------------------------------------------------
-- Correct cross-timezone event ordering for a single shipment
-- (Test 3: equivalent timestamps from different countries must produce
-- the same event chronology - i.e. sorting by EVENT_TIMESTAMP_UTC, not
-- by the naive local EVENT_LOCAL_TIMESTAMP string/value, is required).
-- ---------------------------------------------------------------
CREATE OR REPLACE VIEW SHIPMENT_EVENT_TIMELINE AS
SELECT SHIPMENT_ID, EVENT_TYPE, EVENT_TIMESTAMP_UTC, EVENT_TIMEZONE,
       ROW_NUMBER() OVER (PARTITION BY SHIPMENT_ID ORDER BY EVENT_TIMESTAMP_UTC) AS CORRECT_SEQUENCE,
       EVENT_SEQ AS SOURCE_RECORDED_SEQUENCE
FROM SHIPMENT_EVENTS_UTC;
-- If CORRECT_SEQUENCE ever disagrees with SOURCE_RECORDED_SEQUENCE for a
-- shipment, that shipment's origin/destination timezones produced a
-- naive-ordering error - exactly what this normalization step prevents.

-- ---------------------------------------------------------------
-- Corrected on-time delivery check, timezone-safe (feeds the canonical
-- OTD metric in the semantic layer - section 9 explicitly calls out that
-- OTD must not be computed on unnormalized local timestamps)
-- ---------------------------------------------------------------
CREATE OR REPLACE VIEW SHIPMENT_DELIVERY_TIMEZONE_SAFE AS
SELECT
    s.SHIPMENT_ID,
    s.PROMISED_DELIVERY_DATE,
    s.ACTUAL_DELIVERY_DATE,
    DATE(d.EVENT_TIMESTAMP_UTC) AS ACTUAL_DELIVERY_DATE_UTC,
    CASE WHEN d.EVENT_TIMESTAMP_UTC IS NOT NULL
         THEN DATE(d.EVENT_TIMESTAMP_UTC) <= s.PROMISED_DELIVERY_DATE
         ELSE NULL END AS ON_TIME_UTC_BASIS
FROM SUPPLY_CHAIN_PLATFORM.RAW_LOGISTICS.SHIPMENTS s
LEFT JOIN SHIPMENT_EVENTS_UTC d
    ON d.SHIPMENT_ID = s.SHIPMENT_ID AND d.EVENT_TYPE = 'DELIVERED';

-- Example validation query (Test 3): pick a shipment whose origin and
-- destination timezones differ and confirm the UTC-based delivered date
-- can differ from a naive same-day-string comparison of the local
-- DELIVERED event timestamp against PROMISED_DELIVERY_DATE:
-- SELECT * FROM SHIPMENT_DELIVERY_TIMEZONE_SAFE
-- JOIN SUPPLY_CHAIN_PLATFORM.RAW_LOGISTICS.SHIPMENTS USING (SHIPMENT_ID)
-- WHERE ORIGIN_TIMEZONE != DEST_TIMEZONE
-- LIMIT 20;
