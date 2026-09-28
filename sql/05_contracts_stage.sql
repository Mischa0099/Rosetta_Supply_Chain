-- =====================================================================
-- Supplier contracts: unstructured documents (synthetic).
-- Loaded to an internal stage for later document-extraction / Cortex
-- parsing (Phase 5). Not modeled as relational tables since these are
-- raw text documents pre-extraction.
-- =====================================================================

USE DATABASE SUPPLY_CHAIN_PLATFORM;
CREATE SCHEMA IF NOT EXISTS SUPPLY_CHAIN_PLATFORM.RAW_DOCUMENTS;
USE SCHEMA SUPPLY_CHAIN_PLATFORM.RAW_DOCUMENTS;

CREATE OR REPLACE STAGE SUPPLIER_CONTRACTS_STAGE
    DIRECTORY = (ENABLE = TRUE)
    ENCRYPTION = (TYPE = 'SNOWFLAKE_SSE');
-- PUT file:///local/path/contracts/*.txt @SUPPLIER_CONTRACTS_STAGE AUTO_COMPRESS=FALSE;

-- Ground-truth manifest for scoring extraction accuracy during testing
-- (NOT an input to the extraction pipeline itself - keep separate).
CREATE OR REPLACE FILE FORMAT CSV_STANDARD
    TYPE = CSV FIELD_DELIMITER = ',' SKIP_HEADER = 1 FIELD_OPTIONALLY_ENCLOSED_BY = '"'
    NULL_IF = ('', 'NULL') EMPTY_FIELD_AS_NULL = TRUE;

CREATE OR REPLACE STAGE CONTRACTS_GROUND_TRUTH_STAGE FILE_FORMAT = CSV_STANDARD;
-- PUT file:///local/path/docs/contracts_ground_truth.csv @CONTRACTS_GROUND_TRUTH_STAGE;

CREATE OR REPLACE TABLE CONTRACTS_GROUND_TRUTH (
    CONTRACT_ID           VARCHAR(10),
    SUPPLIER_REAL_NAME    VARCHAR(200),
    SUPPLIER_MASTER_KEY   VARCHAR(20),
    EFFECTIVE_DATE        DATE,
    EXPIRATION_DATE       DATE,
    TERM_MONTHS           NUMBER(4,0),
    SLA_DAYS              NUMBER(4,0),
    LEAD_TIME_DAYS        NUMBER(4,0),
    DELIVERY_TERM         VARCHAR(20),
    MIN_OTD_PCT           NUMBER(5,2),
    PENALTY_PCT           NUMBER(5,2),
    CURRENCY              VARCHAR(3),
    APPLICABLE_PRODUCTS   VARCHAR(500)
);

COPY INTO CONTRACTS_GROUND_TRUTH FROM @CONTRACTS_GROUND_TRUTH_STAGE/contracts_ground_truth.csv;

-- Example: once files land in SUPPLIER_CONTRACTS_STAGE, list them with:
-- SELECT * FROM DIRECTORY(@SUPPLIER_CONTRACTS_STAGE);
-- Text extraction in Phase 5 can use SNOWFLAKE.CORTEX.PARSE_DOCUMENT() or
-- a Document AI pipeline over this stage.
