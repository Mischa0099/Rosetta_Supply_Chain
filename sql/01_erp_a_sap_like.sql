-- =====================================================================
-- ERP A — SAP-like schema
-- Field names intentionally mimic real SAP conventions to demonstrate
-- AI-assisted schema mapping against non-obvious source field names.
-- =====================================================================

CREATE DATABASE IF NOT EXISTS SUPPLY_CHAIN_PLATFORM;
CREATE SCHEMA IF NOT EXISTS SUPPLY_CHAIN_PLATFORM.RAW_ERP_A;
USE SCHEMA SUPPLY_CHAIN_PLATFORM.RAW_ERP_A;

CREATE OR REPLACE FILE FORMAT CSV_STANDARD
    TYPE = CSV FIELD_DELIMITER = ',' SKIP_HEADER = 1 FIELD_OPTIONALLY_ENCLOSED_BY = '"'
    NULL_IF = ('', 'NULL') EMPTY_FIELD_AS_NULL = TRUE;

CREATE OR REPLACE STAGE ERP_A_STAGE FILE_FORMAT = CSV_STANDARD;
-- Upload csv/erp_a/*.csv to @ERP_A_STAGE via SnowSQL PUT or Snowsight, e.g.:
-- PUT file:///local/path/csv/erp_a/*.csv @ERP_A_STAGE AUTO_COMPRESS=TRUE;

-- ---------------------------------------------------------------
-- LFA1-style: Vendor/Supplier master
-- ---------------------------------------------------------------
CREATE OR REPLACE TABLE SUPPLIERS (
    LIFNR        VARCHAR(10)  NOT NULL COMMENT 'Vendor number (supplier ID)',
    NAME1        VARCHAR(200) COMMENT 'Vendor name',
    LAND1        VARCHAR(2)   COMMENT 'Country key',
    ORT01        VARCHAR(100) COMMENT 'City',
    WAERS        VARCHAR(3)   COMMENT 'Currency key',
    ZTIMEZONE    VARCHAR(50)  COMMENT 'Custom field: supplier local timezone (IANA)',
    ERDAT        DATE         COMMENT 'Record creation date',
    SPERR        VARCHAR(1)   COMMENT 'Posting block flag (X = blocked)',
    CONSTRAINT PK_SUPPLIERS PRIMARY KEY (LIFNR)
);

-- ---------------------------------------------------------------
-- MARA-style: Material master
-- ---------------------------------------------------------------
CREATE OR REPLACE TABLE MATERIALS (
    MATNR   VARCHAR(8)   NOT NULL COMMENT 'Material number',
    MAKTX   VARCHAR(200) COMMENT 'Material description',
    MEINS   VARCHAR(5)   COMMENT 'Base unit of measure',
    MTART   VARCHAR(10)  COMMENT 'Material type / category code',
    ERDAT   DATE         COMMENT 'Record creation date',
    CONSTRAINT PK_MATERIALS PRIMARY KEY (MATNR)
);

-- ---------------------------------------------------------------
-- T001W-style: Plant master
-- ---------------------------------------------------------------
CREATE OR REPLACE TABLE PLANTS (
    WERKS       VARCHAR(4)   NOT NULL COMMENT 'Plant code',
    NAME1       VARCHAR(200) COMMENT 'Plant name',
    LAND1       VARCHAR(2)   COMMENT 'Country key',
    ZTIMEZONE   VARCHAR(50)  COMMENT 'Custom field: plant local timezone (IANA)',
    CONSTRAINT PK_PLANTS PRIMARY KEY (WERKS)
);

-- ---------------------------------------------------------------
-- KNA1-style: Customer master
-- ---------------------------------------------------------------
CREATE OR REPLACE TABLE CUSTOMERS (
    KUNNR       VARCHAR(10)  NOT NULL COMMENT 'Customer number',
    NAME1       VARCHAR(200) COMMENT 'Customer name',
    LAND1       VARCHAR(2)   COMMENT 'Country key',
    ZTIMEZONE   VARCHAR(50)  COMMENT 'Custom field: customer local timezone (IANA)',
    CONSTRAINT PK_CUSTOMERS PRIMARY KEY (KUNNR)
);

-- ---------------------------------------------------------------
-- EKKO/EKPO-style: Purchase order header + items
-- ---------------------------------------------------------------
CREATE OR REPLACE TABLE PURCHASE_ORDERS (
    EBELN   VARCHAR(10)  NOT NULL COMMENT 'Purchasing document number',
    LIFNR   VARCHAR(10)  COMMENT 'Vendor number (FK -> SUPPLIERS.LIFNR)',
    WERKS   VARCHAR(4)   COMMENT 'Plant (FK -> PLANTS.WERKS)',
    BEDAT   DATE         COMMENT 'Purchasing document date',
    WAERS   VARCHAR(3)   COMMENT 'Currency key',
    BSART   VARCHAR(4)   COMMENT 'Purchasing document type',
    CONSTRAINT PK_PO PRIMARY KEY (EBELN)
);

CREATE OR REPLACE TABLE PURCHASE_ORDER_ITEMS (
    EBELN   VARCHAR(10)  NOT NULL COMMENT 'Purchasing document number (FK -> PURCHASE_ORDERS.EBELN)',
    EBELP   VARCHAR(5)   NOT NULL COMMENT 'Item number of purchasing document',
    MATNR   VARCHAR(8)   COMMENT 'Material number (FK -> MATERIALS.MATNR)',
    WERKS   VARCHAR(4)   COMMENT 'Plant (FK -> PLANTS.WERKS)',
    MENGE   NUMBER(15,3) COMMENT 'Purchase order quantity',
    MEINS   VARCHAR(5)   COMMENT 'Order unit',
    NETPR   NUMBER(15,2) COMMENT 'Net price',
    EINDT   DATE         COMMENT 'Item delivery date (promised delivery date) - may be NULL (data quality case)',
    CONSTRAINT PK_POI PRIMARY KEY (EBELN, EBELP)
);

-- ---------------------------------------------------------------
-- VBAK/VBAP-style: Sales order header + items
-- ---------------------------------------------------------------
CREATE OR REPLACE TABLE SALES_ORDERS (
    VBELN   VARCHAR(10)  NOT NULL COMMENT 'Sales document number',
    KUNNR   VARCHAR(10)  COMMENT 'Sold-to customer (FK -> CUSTOMERS.KUNNR)',
    ERDAT   DATE         COMMENT 'Record creation date',
    AUART   VARCHAR(4)   COMMENT 'Sales document type',
    CONSTRAINT PK_SO PRIMARY KEY (VBELN)
);

CREATE OR REPLACE TABLE SALES_ORDER_ITEMS (
    VBELN   VARCHAR(10)  NOT NULL COMMENT 'Sales document number (FK -> SALES_ORDERS.VBELN)',
    POSNR   VARCHAR(6)   NOT NULL COMMENT 'Sales document item number',
    MATNR   VARCHAR(8)   COMMENT 'Material number (FK -> MATERIALS.MATNR)',
    WERKS   VARCHAR(4)   COMMENT 'Delivering plant (FK -> PLANTS.WERKS)',
    KWMENG  NUMBER(15,3) COMMENT 'Cumulative order quantity',
    CONSTRAINT PK_SOI PRIMARY KEY (VBELN, POSNR)
);

-- ---------------------------------------------------------------
-- Inventory (MARD/MCHB-style, simplified)
-- ---------------------------------------------------------------
CREATE OR REPLACE TABLE INVENTORY (
    MATNR   VARCHAR(8)   NOT NULL COMMENT 'Material number (FK -> MATERIALS.MATNR)',
    WERKS   VARCHAR(4)   NOT NULL COMMENT 'Plant (FK -> PLANTS.WERKS)',
    LGORT   VARCHAR(4)   COMMENT 'Storage location',
    LABST   NUMBER(15,3) COMMENT 'Unrestricted-use stock quantity',
    CONSTRAINT PK_INV PRIMARY KEY (MATNR, WERKS, LGORT)
);

-- ---------------------------------------------------------------
-- COPY INTO statements (run after PUT / after staging via Snowsight upload)
-- ---------------------------------------------------------------
COPY INTO SUPPLIERS            FROM @ERP_A_STAGE/suppliers.csv;
COPY INTO MATERIALS            FROM @ERP_A_STAGE/materials.csv;
COPY INTO PLANTS               FROM @ERP_A_STAGE/plants.csv;
COPY INTO CUSTOMERS            FROM @ERP_A_STAGE/customers.csv;
COPY INTO PURCHASE_ORDERS      FROM @ERP_A_STAGE/purchase_orders.csv;
COPY INTO PURCHASE_ORDER_ITEMS FROM @ERP_A_STAGE/purchase_order_items.csv;
COPY INTO SALES_ORDERS         FROM @ERP_A_STAGE/sales_orders.csv;
COPY INTO SALES_ORDER_ITEMS    FROM @ERP_A_STAGE/sales_order_items.csv;
COPY INTO INVENTORY            FROM @ERP_A_STAGE/inventory.csv;
