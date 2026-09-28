-- =====================================================================
-- ERP B — Custom / Oracle-like schema
-- Represents the SAME business concepts as ERP A under different field
-- names/conventions (vendor_id vs LIFNR, sku vs MATNR, location_code vs
-- WERKS, promise_dt vs EINDT, ...). This is the second source system the
-- AI schema-mapping component must reconcile against the canonical ontology.
-- =====================================================================

USE DATABASE SUPPLY_CHAIN_PLATFORM;
CREATE SCHEMA IF NOT EXISTS SUPPLY_CHAIN_PLATFORM.RAW_ERP_B;
USE SCHEMA SUPPLY_CHAIN_PLATFORM.RAW_ERP_B;

CREATE OR REPLACE FILE FORMAT CSV_STANDARD
    TYPE = CSV FIELD_DELIMITER = ',' SKIP_HEADER = 1 FIELD_OPTIONALLY_ENCLOSED_BY = '"'
    NULL_IF = ('', 'NULL') EMPTY_FIELD_AS_NULL = TRUE;

CREATE OR REPLACE STAGE ERP_B_STAGE FILE_FORMAT = CSV_STANDARD;
-- PUT file:///local/path/csv/erp_b/*.csv @ERP_B_STAGE AUTO_COMPRESS=TRUE;

CREATE OR REPLACE TABLE VENDORS (
    VENDOR_ID       VARCHAR(20)  NOT NULL COMMENT 'Vendor identifier (supplier ID)',
    VENDOR_NAME     VARCHAR(200) COMMENT 'Vendor legal name',
    COUNTRY_CODE    VARCHAR(2)   COMMENT 'ISO country code',
    CURRENCY_CODE   VARCHAR(3)   COMMENT 'Default transaction currency',
    TIME_ZONE       VARCHAR(50)  COMMENT 'Vendor local timezone (IANA)',
    CREATED_DATE    DATE         COMMENT 'Record creation date',
    STATUS          VARCHAR(10)  COMMENT 'ACTIVE / HOLD',
    CONSTRAINT PK_VENDORS PRIMARY KEY (VENDOR_ID)
);

CREATE OR REPLACE TABLE ITEMS (
    SKU             VARCHAR(30)  NOT NULL COMMENT 'Stock keeping unit (material identifier)',
    ITEM_DESC       VARCHAR(200) COMMENT 'Item description',
    UOM             VARCHAR(5)   COMMENT 'Unit of measure',
    ITEM_CATEGORY   VARCHAR(50)  COMMENT 'Item category',
    CREATED_DATE    DATE         COMMENT 'Record creation date',
    CONSTRAINT PK_ITEMS PRIMARY KEY (SKU)
);

CREATE OR REPLACE TABLE LOCATIONS (
    LOCATION_CODE   VARCHAR(20)  NOT NULL COMMENT 'Location identifier (plant identifier)',
    LOCATION_NAME   VARCHAR(200) COMMENT 'Location name',
    COUNTRY_CODE    VARCHAR(2)   COMMENT 'ISO country code',
    TIME_ZONE       VARCHAR(50)  COMMENT 'Location local timezone (IANA)',
    CONSTRAINT PK_LOCATIONS PRIMARY KEY (LOCATION_CODE)
);

CREATE OR REPLACE TABLE CUSTOMERS (
    CUSTOMER_ID     VARCHAR(20)  NOT NULL COMMENT 'Customer identifier',
    CUSTOMER_NAME   VARCHAR(200) COMMENT 'Customer name',
    COUNTRY_CODE    VARCHAR(2)   COMMENT 'ISO country code',
    TIME_ZONE       VARCHAR(50)  COMMENT 'Customer local timezone (IANA)',
    CONSTRAINT PK_CUSTOMERS_B PRIMARY KEY (CUSTOMER_ID)
);

CREATE OR REPLACE TABLE PURCHASE_ORDERS (
    PO_NUMBER       VARCHAR(20)  NOT NULL COMMENT 'Purchase order number',
    VENDOR_ID       VARCHAR(20)  COMMENT 'Vendor identifier (FK -> VENDORS.VENDOR_ID)',
    LOCATION_CODE   VARCHAR(20)  COMMENT 'Receiving location (FK -> LOCATIONS.LOCATION_CODE)',
    ORDER_DATE      DATE         COMMENT 'PO creation date',
    CURRENCY_CODE   VARCHAR(3)   COMMENT 'Transaction currency',
    PO_TYPE         VARCHAR(20)  COMMENT 'Purchase order type',
    CONSTRAINT PK_PO_B PRIMARY KEY (PO_NUMBER)
);

CREATE OR REPLACE TABLE PURCHASE_ORDER_LINES (
    PO_NUMBER       VARCHAR(20)  NOT NULL COMMENT 'Purchase order number (FK -> PURCHASE_ORDERS.PO_NUMBER)',
    LINE_NUM        NUMBER(5,0)  NOT NULL COMMENT 'PO line number',
    SKU             VARCHAR(30)  COMMENT 'Item identifier (FK -> ITEMS.SKU)',
    LOCATION_CODE   VARCHAR(20)  COMMENT 'Receiving location (FK -> LOCATIONS.LOCATION_CODE)',
    QUANTITY        NUMBER(15,3) COMMENT 'Ordered quantity',
    UNIT_PRICE      NUMBER(15,2) COMMENT 'Unit price',
    PROMISE_DT      DATE         COMMENT 'Promised delivery date - may be NULL (data quality case)',
    CONSTRAINT PK_POL PRIMARY KEY (PO_NUMBER, LINE_NUM)
);

CREATE OR REPLACE TABLE SALES_ORDERS (
    ORDER_ID        VARCHAR(20)  NOT NULL COMMENT 'Sales order identifier',
    CUSTOMER_ID     VARCHAR(20)  COMMENT 'Customer identifier (FK -> CUSTOMERS.CUSTOMER_ID)',
    ORDER_DATE      DATE         COMMENT 'Order creation date',
    ORDER_TYPE      VARCHAR(20)  COMMENT 'Sales order type',
    CONSTRAINT PK_SO_B PRIMARY KEY (ORDER_ID)
);

CREATE OR REPLACE TABLE SALES_ORDER_LINES (
    ORDER_ID        VARCHAR(20)  NOT NULL COMMENT 'Sales order identifier (FK -> SALES_ORDERS.ORDER_ID)',
    LINE_NUM        NUMBER(5,0)  NOT NULL COMMENT 'Sales order line number',
    SKU             VARCHAR(30)  COMMENT 'Item identifier (FK -> ITEMS.SKU)',
    LOCATION_CODE   VARCHAR(20)  COMMENT 'Shipping location (FK -> LOCATIONS.LOCATION_CODE)',
    QTY_ORDERED     NUMBER(15,3) COMMENT 'Ordered quantity',
    CONSTRAINT PK_SOL PRIMARY KEY (ORDER_ID, LINE_NUM)
);

CREATE OR REPLACE TABLE INVENTORY_BALANCES (
    SKU             VARCHAR(30)  NOT NULL COMMENT 'Item identifier (FK -> ITEMS.SKU)',
    LOCATION_CODE   VARCHAR(20)  NOT NULL COMMENT 'Location identifier (FK -> LOCATIONS.LOCATION_CODE)',
    WAREHOUSE_ZONE  VARCHAR(5)   COMMENT 'Warehouse zone',
    QTY_ON_HAND     NUMBER(15,3) COMMENT 'On-hand quantity',
    CONSTRAINT PK_INV_B PRIMARY KEY (SKU, LOCATION_CODE, WAREHOUSE_ZONE)
);

COPY INTO VENDORS               FROM @ERP_B_STAGE/vendors.csv;
COPY INTO ITEMS                 FROM @ERP_B_STAGE/items.csv;
COPY INTO LOCATIONS             FROM @ERP_B_STAGE/locations.csv;
COPY INTO CUSTOMERS             FROM @ERP_B_STAGE/customers.csv;
COPY INTO PURCHASE_ORDERS       FROM @ERP_B_STAGE/purchase_orders.csv;
COPY INTO PURCHASE_ORDER_LINES  FROM @ERP_B_STAGE/purchase_order_lines.csv;
COPY INTO SALES_ORDERS          FROM @ERP_B_STAGE/sales_orders.csv;
COPY INTO SALES_ORDER_LINES     FROM @ERP_B_STAGE/sales_order_lines.csv;
COPY INTO INVENTORY_BALANCES    FROM @ERP_B_STAGE/inventory_balances.csv;
