-- =====================================================================
-- PHASE 4: EVENT & NEAR-REAL-TIME PROCESSING (spec section 19)
-- Batch/incremental for master + historical data (already handled by the
-- COPY INTO loads in scripts 01-11). THIS script is the near-real-time
-- path for operational events: Streams capture new rows as they land,
-- a Task turns DELAYED events into open exceptions, and Dynamic Tables
-- keep "current state" (latest shipment status, latest known location)
-- fresh without a full-table recompute on every query.
-- =====================================================================

USE DATABASE SUPPLY_CHAIN_PLATFORM;
USE SCHEMA SUPPLY_CHAIN_PLATFORM.INTELLIGENCE;

-- ---------------------------------------------------------------
-- Stream: captures every new row landing in SHIPMENT_EVENTS (whether from
-- a batch COPY INTO or, in production, a Snowpipe/Kafka connector feed).
-- ---------------------------------------------------------------
CREATE STREAM IF NOT EXISTS SHIPMENT_EVENTS_STREAM
    ON TABLE SUPPLY_CHAIN_PLATFORM.RAW_LOGISTICS.SHIPMENT_EVENTS;

-- ---------------------------------------------------------------
-- Dynamic Table: current status per shipment, derived from the
-- TIMEZONE-NORMALIZED event stream (not raw local timestamps), refreshed
-- on a short target lag rather than a nightly batch job - this is what
-- "make the latest information available to analytics" (section 19) means.
-- ---------------------------------------------------------------
CREATE OR REPLACE DYNAMIC TABLE CURRENT_SHIPMENT_STATUS
    TARGET_LAG = '5 minutes'
    WAREHOUSE = SUPPLY_CHAIN_WH
AS
SELECT SHIPMENT_ID, EVENT_TYPE AS LATEST_STATUS, EVENT_TIMESTAMP_UTC AS LATEST_EVENT_TIME_UTC
FROM (
    SELECT *, ROW_NUMBER() OVER (PARTITION BY SHIPMENT_ID ORDER BY EVENT_TIMESTAMP_UTC DESC) AS rn
    FROM SUPPLY_CHAIN_PLATFORM.GOVERNANCE.SHIPMENT_EVENTS_UTC
)
WHERE rn = 1;

-- ---------------------------------------------------------------
-- Dynamic Table: latest known GPS location per in-transit shipment, from
-- the IoT feed (naturally higher-frequency than TMS status events).
-- ---------------------------------------------------------------
CREATE OR REPLACE DYNAMIC TABLE CURRENT_SHIPMENT_LOCATION
    TARGET_LAG = '5 minutes'
    WAREHOUSE = SUPPLY_CHAIN_WH
AS
SELECT SHIPMENT_ID, LATITUDE, LONGITUDE, SPEED_KMH, EVENT_TIMESTAMP_UTC AS AS_OF_UTC
FROM (
    SELECT *, ROW_NUMBER() OVER (PARTITION BY SHIPMENT_ID ORDER BY EVENT_TIMESTAMP_UTC DESC) AS rn
    FROM SUPPLY_CHAIN_PLATFORM.RAW_IOT.LOCATION_UPDATES
)
WHERE rn = 1;

-- ---------------------------------------------------------------
-- Open exceptions table (feeds the Executive Control Tower's "active
-- exceptions" tile - section 22).
-- ---------------------------------------------------------------
CREATE TABLE IF NOT EXISTS OPEN_EXCEPTIONS (
    EXCEPTION_ID   VARCHAR(60)  NOT NULL,
    SHIPMENT_ID      VARCHAR(20),
    EXCEPTION_TYPE     VARCHAR(30)  COMMENT 'SHIPMENT_DELAYED, TEMPERATURE_EXCURSION, etc.',
    DETECTED_AT           TIMESTAMP_TZ,
    DETAILS                  VARCHAR(500),
    STATUS                      VARCHAR(20) DEFAULT 'OPEN' COMMENT 'OPEN / ACKNOWLEDGED / RESOLVED',
    CONSTRAINT PK_EXCEPTIONS PRIMARY KEY (EXCEPTION_ID)
);

-- ---------------------------------------------------------------
-- Task: on new DELAYED events, open an exception automatically. Runs
-- only when the stream actually has data (SYSTEM$STREAM_HAS_DATA), so it
-- costs nothing when nothing has changed - this is the "don't make every
-- component real-time unnecessarily" principle in section 19.
-- ---------------------------------------------------------------
CREATE OR REPLACE TASK PROCESS_SHIPMENT_DELAY_EVENTS
    WAREHOUSE = SUPPLY_CHAIN_WH
    SCHEDULE = '5 MINUTE'
WHEN SYSTEM$STREAM_HAS_DATA('SHIPMENT_EVENTS_STREAM')
AS
INSERT INTO OPEN_EXCEPTIONS (EXCEPTION_ID, SHIPMENT_ID, EXCEPTION_TYPE, DETECTED_AT, DETAILS, STATUS)
SELECT 'EXC-' || SHIPMENT_ID || '-' || EVENT_SEQ || '-' || TO_VARCHAR(CURRENT_TIMESTAMP(), 'YYYYMMDDHH24MISS'),
       SHIPMENT_ID, 'SHIPMENT_DELAYED', CURRENT_TIMESTAMP(),
       'DELAYED event detected' || IFF(NOTES IS NOT NULL, ': ' || NOTES, ''), 'OPEN'
FROM SHIPMENT_EVENTS_STREAM
WHERE EVENT_TYPE = 'DELAYED' AND METADATA$ACTION = 'INSERT';

ALTER TASK PROCESS_SHIPMENT_DELAY_EVENTS RESUME;

-- Manual trigger for testing without waiting on the schedule:
-- EXECUTE TASK PROCESS_SHIPMENT_DELAY_EVENTS;

-- Event flow this supports (section 19):
-- ShipmentCreated -> ShipmentPickedUp -> ShipmentDeparted -> CustomsCleared
--   -> ShipmentDelayed (opens an exception + IMPACT_ANALYSIS_SHIPMENT is
--      the natural next call for whoever picks up that exception)
--   -> ShipmentArrived -> ShipmentDelivered (rolls into CURRENT_SHIPMENT_STATUS
--      and the next OTD calculation automatically, no manual refresh needed)
