-- =====================================================================
-- IoT / near-real-time operational events.
-- Loaded here as CSV batches for the synthetic demo; in production this
-- schema is the landing zone for a Snowpipe / Kafka connector feed, with
-- Streams + Tasks (or Dynamic Tables) promoting new rows into the
-- ontology-aligned layer near-real-time. See 06_streams_tasks.sql.
-- =====================================================================

USE DATABASE SUPPLY_CHAIN_PLATFORM;
CREATE SCHEMA IF NOT EXISTS SUPPLY_CHAIN_PLATFORM.RAW_IOT;
USE SCHEMA SUPPLY_CHAIN_PLATFORM.RAW_IOT;

CREATE OR REPLACE FILE FORMAT CSV_STANDARD
    TYPE = CSV FIELD_DELIMITER = ',' SKIP_HEADER = 1 FIELD_OPTIONALLY_ENCLOSED_BY = '"'
    NULL_IF = ('', 'NULL') EMPTY_FIELD_AS_NULL = TRUE;

CREATE OR REPLACE STAGE IOT_STAGE FILE_FORMAT = CSV_STANDARD;
-- PUT file:///local/path/csv/iot/*.csv @IOT_STAGE AUTO_COMPRESS=TRUE;

CREATE OR REPLACE TABLE LOCATION_UPDATES (
    SHIPMENT_ID          VARCHAR(20)   COMMENT 'FK -> RAW_LOGISTICS.SHIPMENTS.SHIPMENT_ID',
    EVENT_TIMESTAMP_UTC  TIMESTAMP_TZ  COMMENT 'GPS ping timestamp, already UTC at the device level',
    LATITUDE             NUMBER(9,5),
    LONGITUDE            NUMBER(9,5),
    SPEED_KMH            NUMBER(6,1)
);

CREATE OR REPLACE TABLE TEMPERATURE_READINGS (
    SHIPMENT_ID          VARCHAR(20)   COMMENT 'FK -> RAW_LOGISTICS.SHIPMENTS.SHIPMENT_ID',
    EVENT_TIMESTAMP_UTC  TIMESTAMP_TZ,
    TEMPERATURE_C        NUMBER(5,2),
    EXCURSION_FLAG        BOOLEAN       COMMENT 'TRUE if reading breached cold-chain threshold'
);

CREATE OR REPLACE TABLE WAREHOUSE_EVENTS (
    PLANT_MASTER_KEY        VARCHAR(20)   COMMENT 'Synthetic-data master key; maps to WERKS/LOCATION_CODE via mapping registry',
    PLANT_NAME               VARCHAR(200),
    EVENT_LOCAL_TIMESTAMP    TIMESTAMP_TZ,
    EVENT_TIMEZONE           VARCHAR(50),
    EVENT_TYPE                VARCHAR(30)   COMMENT 'INBOUND_RECEIPT/PUTAWAY/PICK/PACK/OUTBOUND_DISPATCH/CYCLE_COUNT/STOCK_ADJUSTMENT',
    QUANTITY                  NUMBER(10,0)
);

CREATE OR REPLACE TABLE SHIPMENT_STATUS_EVENTS (
    SHIPMENT_ID          VARCHAR(20)   COMMENT 'FK -> RAW_LOGISTICS.SHIPMENTS.SHIPMENT_ID',
    EVENT_TIMESTAMP_UTC  TIMESTAMP_TZ,
    DETECTED_STATUS      VARCHAR(20)   COMMENT 'IoT-detected status; may briefly disagree with TMS-reported SHIPMENT_EVENTS - reconcile, do not overwrite silently',
    SOURCE_DEVICE         VARCHAR(30)
);

COPY INTO LOCATION_UPDATES       FROM @IOT_STAGE/location_updates.csv;
COPY INTO TEMPERATURE_READINGS   FROM @IOT_STAGE/temperature_readings.csv;
COPY INTO WAREHOUSE_EVENTS       FROM @IOT_STAGE/warehouse_events.csv;
COPY INTO SHIPMENT_STATUS_EVENTS FROM @IOT_STAGE/shipment_status_events.csv;
