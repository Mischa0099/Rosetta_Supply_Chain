-- =====================================================================
-- Logistics domain: carriers, shipments, shipment_events
-- Sits above BOTH ERP A and ERP B (one TMS serves the whole company).
-- Timestamps are stored in LOCAL time + timezone (NOT pre-converted to
-- UTC) on purpose - see 04_timezone_normalization.sql for the fix.
-- =====================================================================

USE DATABASE SUPPLY_CHAIN_PLATFORM;
CREATE SCHEMA IF NOT EXISTS SUPPLY_CHAIN_PLATFORM.RAW_LOGISTICS;
USE SCHEMA SUPPLY_CHAIN_PLATFORM.RAW_LOGISTICS;

CREATE OR REPLACE FILE FORMAT CSV_STANDARD
    TYPE = CSV FIELD_DELIMITER = ',' SKIP_HEADER = 1 FIELD_OPTIONALLY_ENCLOSED_BY = '"'
    NULL_IF = ('', 'NULL') EMPTY_FIELD_AS_NULL = TRUE;

CREATE OR REPLACE STAGE LOGISTICS_STAGE FILE_FORMAT = CSV_STANDARD;
-- PUT file:///local/path/csv/logistics/*.csv @LOGISTICS_STAGE AUTO_COMPRESS=TRUE;

CREATE OR REPLACE TABLE CARRIERS (
    CARRIER_ID      VARCHAR(10)  NOT NULL,
    CARRIER_NAME    VARCHAR(200),
    MODE            VARCHAR(20)  COMMENT 'Ocean / Air / Road / Rail',
    CONSTRAINT PK_CARRIERS PRIMARY KEY (CARRIER_ID)
);

CREATE OR REPLACE TABLE SHIPMENTS (
    SHIPMENT_ID              VARCHAR(20)  NOT NULL,
    SOURCE_ERP               VARCHAR(10)  COMMENT 'ERP_A or ERP_B - which source system this shipment traces back to',
    DIRECTION                VARCHAR(10)  COMMENT 'INBOUND (supplier->plant) or OUTBOUND (plant->customer)',
    REFERENCE_DOC            VARCHAR(20)  COMMENT 'PO number or SO number in the source ERP',
    CARRIER_ID                VARCHAR(10)  COMMENT 'FK -> CARRIERS.CARRIER_ID',
    ORIGIN                    VARCHAR(100),
    DESTINATION               VARCHAR(100),
    ORIGIN_TIMEZONE           VARCHAR(50)  COMMENT 'IANA timezone at origin',
    DEST_TIMEZONE             VARCHAR(50)  COMMENT 'IANA timezone at destination',
    PROMISED_DELIVERY_DATE    DATE,
    ESTIMATED_DELIVERY_DATE   DATE,
    ACTUAL_DELIVERY_DATE      DATE         COMMENT 'NULL until delivered',
    STATUS                     VARCHAR(20)  COMMENT 'CREATED/IN_TRANSIT/DELAYED/ARRIVED/DELIVERED',
    CONSTRAINT PK_SHIPMENTS PRIMARY KEY (SHIPMENT_ID)
);

CREATE OR REPLACE TABLE SHIPMENT_EVENTS (
    SHIPMENT_ID             VARCHAR(20)  NOT NULL COMMENT 'FK -> SHIPMENTS.SHIPMENT_ID',
    EVENT_SEQ               NUMBER(5,0)  NOT NULL,
    EVENT_TYPE              VARCHAR(30)  COMMENT 'CREATED/PICKED_UP/DEPARTED/CUSTOMS_CLEARED/IN_TRANSIT/DELAYED/ARRIVED/DELIVERED',
    EVENT_LOCAL_TIMESTAMP   TIMESTAMP_TZ COMMENT 'Event timestamp in the LOCAL timezone it was recorded in',
    EVENT_TIMEZONE          VARCHAR(50)  COMMENT 'IANA timezone the EVENT_LOCAL_TIMESTAMP is expressed in',
    NOTES                   VARCHAR(500),
    CONSTRAINT PK_SHIPMENT_EVENTS PRIMARY KEY (SHIPMENT_ID, EVENT_SEQ)
);

COPY INTO CARRIERS        FROM @LOGISTICS_STAGE/carriers.csv;
COPY INTO SHIPMENTS       FROM @LOGISTICS_STAGE/shipments.csv;
COPY INTO SHIPMENT_EVENTS FROM @LOGISTICS_STAGE/shipment_events.csv;
