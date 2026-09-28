-- =====================================================================
-- Golden entity crosswalk (ANSWER KEY, not a production table).
-- Human/synthetic-data-authored ground truth linking ERP A and ERP B IDs
-- for the same real-world Supplier/Product/Plant. Use this ONLY to score
-- the accuracy of the AI schema-mapping / entity-resolution component
-- (Test 1). Never feed this table into the mapping model itself.
-- =====================================================================

USE DATABASE SUPPLY_CHAIN_PLATFORM;
USE SCHEMA SUPPLY_CHAIN_PLATFORM.RAW_DOCUMENTS;

CREATE OR REPLACE STAGE GOLDEN_CROSSWALK_STAGE FILE_FORMAT = CSV_STANDARD;
-- PUT file:///local/path/docs/golden_entity_crosswalk.csv @GOLDEN_CROSSWALK_STAGE;

CREATE OR REPLACE TABLE GOLDEN_ENTITY_CROSSWALK_ANSWER_KEY (
    MASTER_KEY     VARCHAR(20),
    ENTITY_TYPE    VARCHAR(20)  COMMENT 'Supplier / Product / Plant',
    REAL_NAME      VARCHAR(200),
    ERP_A_ID       VARCHAR(20)  COMMENT 'LIFNR / MATNR / WERKS as applicable, blank if not present in ERP A',
    ERP_B_ID       VARCHAR(20)  COMMENT 'VENDOR_ID / SKU / LOCATION_CODE as applicable, blank if not present in ERP B',
    PRESENT_IN     VARCHAR(20)  COMMENT 'ERP_A+ERP_B / ERP_A_only / ERP_B_only'
);

COPY INTO GOLDEN_ENTITY_CROSSWALK_ANSWER_KEY FROM @GOLDEN_CROSSWALK_STAGE/golden_entity_crosswalk.csv;
