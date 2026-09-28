-- =====================================================================
-- CANONICAL ONTOLOGY - CORE ENTITIES
-- Business-meaning tables that ERP A and ERP B both resolve into.
-- Populated (for Phase 1) via a deterministic ETL against the known
-- generation-time ID crosswalk. Phase 2 replaces the population method
-- with the governed AI mapping pipeline + mapping registry + human
-- review - the TARGET SCHEMA below does not change.
-- =====================================================================

USE DATABASE SUPPLY_CHAIN_PLATFORM;
CREATE SCHEMA IF NOT EXISTS SUPPLY_CHAIN_PLATFORM.ONTOLOGY_CORE;
USE SCHEMA SUPPLY_CHAIN_PLATFORM.ONTOLOGY_CORE;

CREATE OR REPLACE FILE FORMAT CSV_STANDARD
    TYPE = CSV FIELD_DELIMITER = ',' SKIP_HEADER = 1 FIELD_OPTIONALLY_ENCLOSED_BY = '"'
    NULL_IF = ('', 'NULL') EMPTY_FIELD_AS_NULL = TRUE;

CREATE OR REPLACE STAGE ONTOLOGY_CORE_STAGE FILE_FORMAT = CSV_STANDARD;
-- PUT file:///local/path/csv/ontology_core/*.csv @ONTOLOGY_CORE_STAGE AUTO_COMPRESS=TRUE;

CREATE OR REPLACE TABLE SUPPLIER (
    CANONICAL_SUPPLIER_ID   VARCHAR(20)  NOT NULL,
    SUPPLIER_NAME            VARCHAR(200),
    COUNTRY                  VARCHAR(2),
    TIMEZONE                 VARCHAR(50)  COMMENT 'IANA timezone, resolved from whichever source ERP had it',
    DEFAULT_CURRENCY         VARCHAR(3),
    SOURCE_SYSTEMS           VARCHAR(20)  COMMENT 'ERP_A+ERP_B / ERP_A_only / ERP_B_only',
    ERP_A_SUPPLIER_ID        VARCHAR(10)  COMMENT 'Source LIFNR, blank if not present in ERP A',
    ERP_B_VENDOR_ID          VARCHAR(20)  COMMENT 'Source VENDOR_ID, blank if not present in ERP B',
    MASTER_KEY                VARCHAR(20)  COMMENT 'Synthetic-data generation key (debug only)',
    CONSTRAINT PK_SUPPLIER PRIMARY KEY (CANONICAL_SUPPLIER_ID)
);

CREATE OR REPLACE TABLE PRODUCT (
    CANONICAL_PRODUCT_ID    VARCHAR(20)  NOT NULL,
    PRODUCT_NAME             VARCHAR(200),
    UNIT_OF_MEASURE          VARCHAR(5),
    CATEGORY                 VARCHAR(50),
    SOURCE_SYSTEMS           VARCHAR(20),
    ERP_A_MATERIAL_ID        VARCHAR(8)   COMMENT 'Source MATNR, blank if not present in ERP A',
    ERP_B_SKU                VARCHAR(30)  COMMENT 'Source SKU, blank if not present in ERP B',
    MASTER_KEY                VARCHAR(20),
    CONSTRAINT PK_PRODUCT PRIMARY KEY (CANONICAL_PRODUCT_ID)
);

CREATE OR REPLACE TABLE PLANT (
    CANONICAL_PLANT_ID       VARCHAR(20)  NOT NULL,
    PLANT_NAME                VARCHAR(200),
    COUNTRY                   VARCHAR(2),
    TIMEZONE                  VARCHAR(50),
    ERP_A_WERKS                VARCHAR(4),
    ERP_B_LOCATION_CODE        VARCHAR(20),
    MASTER_KEY                  VARCHAR(20),
    CONSTRAINT PK_PLANT PRIMARY KEY (CANONICAL_PLANT_ID)
);

CREATE OR REPLACE TABLE CUSTOMER (
    CANONICAL_CUSTOMER_ID    VARCHAR(20)  NOT NULL,
    CUSTOMER_NAME             VARCHAR(200),
    COUNTRY                   VARCHAR(2),
    TIMEZONE                  VARCHAR(50),
    SOURCE_SYSTEM              VARCHAR(10)  COMMENT 'ERP_A or ERP_B - customer bases do not overlap between the two',
    ERP_A_KUNNR                 VARCHAR(10),
    ERP_B_CUSTOMER_ID           VARCHAR(20),
    CONSTRAINT PK_CUSTOMER PRIMARY KEY (CANONICAL_CUSTOMER_ID)
);

CREATE OR REPLACE TABLE LOCATION (
    CANONICAL_LOCATION_ID     VARCHAR(30)  NOT NULL,
    LOCATION_NAME              VARCHAR(200),
    LOCATION_TYPE               VARCHAR(20)  COMMENT 'PLANT / SUPPLIER_SITE / CUSTOMER_SITE',
    COUNTRY                      VARCHAR(2),
    TIMEZONE                     VARCHAR(50),
    REFERENCED_ENTITY_ID          VARCHAR(20)  COMMENT 'FK into SUPPLIER/PLANT/CUSTOMER depending on LOCATION_TYPE',
    CONSTRAINT PK_LOCATION PRIMARY KEY (CANONICAL_LOCATION_ID)
);

CREATE OR REPLACE TABLE ORDERS (
    CANONICAL_ORDER_ID        VARCHAR(30)  NOT NULL,
    ORDER_TYPE                 VARCHAR(10)  COMMENT 'PURCHASE or SALES',
    SOURCE_SYSTEM               VARCHAR(10),
    SOURCE_DOC_ID                 VARCHAR(20)  COMMENT 'EBELN/VBELN (ERP A) or PO_NUMBER/ORDER_ID (ERP B)',
    SUPPLIER_ID                    VARCHAR(20)  COMMENT 'FK -> SUPPLIER, populated for PURCHASE orders',
    CUSTOMER_ID                     VARCHAR(20)  COMMENT 'FK -> CUSTOMER, populated for SALES orders',
    PLANT_ID                         VARCHAR(20)  COMMENT 'FK -> PLANT',
    ORDER_DATE                        DATE,
    CURRENCY                           VARCHAR(3),
    CONSTRAINT PK_ORDERS PRIMARY KEY (CANONICAL_ORDER_ID)
);

CREATE OR REPLACE TABLE ORDER_LINE (
    CANONICAL_ORDER_ID        VARCHAR(30)  NOT NULL COMMENT 'FK -> ORDERS',
    LINE_NUM                    VARCHAR(10)  NOT NULL,
    PRODUCT_ID                    VARCHAR(20)  COMMENT 'FK -> PRODUCT',
    PLANT_ID                        VARCHAR(20)  COMMENT 'FK -> PLANT',
    QUANTITY                          NUMBER(15,3),
    UNIT_PRICE                          NUMBER(15,2),
    PROMISED_DATE                        DATE         COMMENT 'May be NULL - reflects source data quality gaps (EINDT/PROMISE_DT)',
    CONSTRAINT PK_ORDER_LINE PRIMARY KEY (CANONICAL_ORDER_ID, LINE_NUM)
);

CREATE OR REPLACE TABLE CONTRACT (
    CANONICAL_CONTRACT_ID     VARCHAR(20)  NOT NULL,
    SOURCE_CONTRACT_ID          VARCHAR(10),
    SUPPLIER_ID                   VARCHAR(20)  COMMENT 'FK -> SUPPLIER',
    EFFECTIVE_DATE                  DATE,
    EXPIRATION_DATE                   DATE,
    SLA_DAYS                            NUMBER(4,0),
    LEAD_TIME_DAYS                        NUMBER(4,0),
    DELIVERY_TERM                           VARCHAR(20),
    MIN_OTD_PCT                               NUMBER(5,2),
    PENALTY_PCT                                 NUMBER(5,2),
    CURRENCY                                     VARCHAR(3),
    APPLICABLE_PRODUCTS                            VARCHAR(500),
    EXTRACTION_CONFIDENCE                            NUMBER(5,2) COMMENT 'Placeholder - populated by Phase 5 document extraction',
    EXTRACTION_STATUS                                  VARCHAR(30) COMMENT 'PENDING_AI_EXTRACTION until Phase 5 runs',
    CONSTRAINT PK_CONTRACT PRIMARY KEY (CANONICAL_CONTRACT_ID)
);

CREATE OR REPLACE TABLE TRANSACTION (
    TRANSACTION_ID              VARCHAR(40)  NOT NULL,
    TRANSACTION_TYPE              VARCHAR(30),
    RELATED_ENTITY_TYPE             VARCHAR(20),
    RELATED_ENTITY_ID                 VARCHAR(30),
    TRANSACTION_DATE                    DATE,
    SOURCE_SYSTEM                         VARCHAR(10),
    CONSTRAINT PK_TRANSACTION PRIMARY KEY (TRANSACTION_ID)
);

COPY INTO SUPPLIER    FROM @ONTOLOGY_CORE_STAGE/supplier.csv;
COPY INTO PRODUCT     FROM @ONTOLOGY_CORE_STAGE/product.csv;
COPY INTO PLANT       FROM @ONTOLOGY_CORE_STAGE/plant.csv;
COPY INTO CUSTOMER    FROM @ONTOLOGY_CORE_STAGE/customer.csv;
COPY INTO LOCATION    FROM @ONTOLOGY_CORE_STAGE/location.csv;
COPY INTO ORDERS      FROM @ONTOLOGY_CORE_STAGE/order.csv;
COPY INTO ORDER_LINE  FROM @ONTOLOGY_CORE_STAGE/order_line.csv;
COPY INTO CONTRACT    FROM @ONTOLOGY_CORE_STAGE/contract.csv;
COPY INTO TRANSACTION FROM @ONTOLOGY_CORE_STAGE/transaction.csv;
