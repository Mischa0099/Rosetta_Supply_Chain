-- =====================================================================
-- PHASE 4: SCHEMA DRIFT DETECTION (spec section 21, Test 7)
-- Snapshots source-table metadata on a schedule and diffs consecutive
-- snapshots to catch added/removed/retyped columns before they silently
-- break a mapping or a semantic view.
-- =====================================================================

USE DATABASE SUPPLY_CHAIN_PLATFORM;
USE SCHEMA SUPPLY_CHAIN_PLATFORM.INTELLIGENCE;

CREATE TABLE IF NOT EXISTS SCHEMA_SNAPSHOTS (
    SNAPSHOT_ID       NUMBER AUTOINCREMENT,
    SNAPSHOT_AT         TIMESTAMP_TZ,
    TABLE_SCHEMA           VARCHAR(50),
    TABLE_NAME                VARCHAR(50),
    COLUMN_NAME                  VARCHAR(50),
    DATA_TYPE                       VARCHAR(50),
    ORDINAL_POSITION                   NUMBER,
    CONSTRAINT PK_SCHEMA_SNAPSHOTS PRIMARY KEY (SNAPSHOT_ID)
);

CREATE TABLE IF NOT EXISTS SCHEMA_DRIFT_LOG (
    DRIFT_ID           NUMBER AUTOINCREMENT,
    DETECTED_AT           TIMESTAMP_TZ,
    TABLE_SCHEMA             VARCHAR(50),
    TABLE_NAME                  VARCHAR(50),
    COLUMN_NAME                    VARCHAR(50),
    DRIFT_TYPE                        VARCHAR(30) COMMENT 'COLUMN_ADDED / COLUMN_REMOVED / DATATYPE_CHANGED',
    OLD_VALUE                            VARCHAR(100),
    NEW_VALUE                               VARCHAR(100),
    AFFECTED_MAPPING_IDS                       VARCHAR(500) COMMENT 'MAPPING_REGISTRY.MAPPING_ID rows that referenced this column, comma-separated',
    ACKNOWLEDGED                                  BOOLEAN DEFAULT FALSE,
    CONSTRAINT PK_SCHEMA_DRIFT PRIMARY KEY (DRIFT_ID)
);

-- ---------------------------------------------------------------
-- Take a fresh snapshot of every RAW_* schema's columns (call this on a
-- schedule via a Task, e.g. daily, or on-demand after a known source
-- deployment).
-- ---------------------------------------------------------------
CREATE OR REPLACE PROCEDURE TAKE_SCHEMA_SNAPSHOT()
RETURNS VARCHAR
LANGUAGE SQL
AS
$$
BEGIN
    INSERT INTO SCHEMA_SNAPSHOTS (SNAPSHOT_AT, TABLE_SCHEMA, TABLE_NAME, COLUMN_NAME, DATA_TYPE, ORDINAL_POSITION)
    SELECT CURRENT_TIMESTAMP(), TABLE_SCHEMA, TABLE_NAME, COLUMN_NAME, DATA_TYPE, ORDINAL_POSITION
    FROM SUPPLY_CHAIN_PLATFORM.INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA IN ('RAW_ERP_A', 'RAW_ERP_B', 'RAW_LOGISTICS', 'RAW_IOT');
    RETURN 'Snapshot taken at ' || CURRENT_TIMESTAMP();
END;
$$;

-- ---------------------------------------------------------------
-- Compare the two most recent snapshots and log drift. Cross-references
-- MAPPING_REGISTRY so a datatype change on a MAPPED column immediately
-- tells you which mappings/metrics are now at risk (section 21: "affected
-- mappings, affected metrics, affected semantic views").
-- ---------------------------------------------------------------
CREATE OR REPLACE PROCEDURE DETECT_SCHEMA_DRIFT()
RETURNS VARCHAR
LANGUAGE SQL
AS
$$
DECLARE
    drift_count INTEGER DEFAULT 0;
BEGIN
    LET latest_two CURSOR FOR
        SELECT DISTINCT SNAPSHOT_ID FROM SCHEMA_SNAPSHOTS ORDER BY SNAPSHOT_ID DESC LIMIT 2;

    -- (Snowflake Scripting: compare snapshot N vs N-1 using a windowed join)
    INSERT INTO SCHEMA_DRIFT_LOG (DETECTED_AT, TABLE_SCHEMA, TABLE_NAME, COLUMN_NAME, DRIFT_TYPE, OLD_VALUE, NEW_VALUE, AFFECTED_MAPPING_IDS)
    WITH ranked AS (
        SELECT *, DENSE_RANK() OVER (ORDER BY SNAPSHOT_ID DESC) AS snap_rank
        FROM SCHEMA_SNAPSHOTS
    ),
    curr AS (SELECT * FROM ranked WHERE snap_rank = 1),
    prev AS (SELECT * FROM ranked WHERE snap_rank = 2),
    datatype_changes AS (
        SELECT c.TABLE_SCHEMA, c.TABLE_NAME, c.COLUMN_NAME, p.DATA_TYPE AS OLD_TYPE, c.DATA_TYPE AS NEW_TYPE
        FROM curr c
        JOIN prev p ON c.TABLE_SCHEMA = p.TABLE_SCHEMA AND c.TABLE_NAME = p.TABLE_NAME AND c.COLUMN_NAME = p.COLUMN_NAME
        WHERE c.DATA_TYPE != p.DATA_TYPE
    ),
    added_columns AS (
        SELECT c.TABLE_SCHEMA, c.TABLE_NAME, c.COLUMN_NAME, c.DATA_TYPE
        FROM curr c
        WHERE NOT EXISTS (SELECT 1 FROM prev p WHERE p.TABLE_SCHEMA=c.TABLE_SCHEMA AND p.TABLE_NAME=c.TABLE_NAME AND p.COLUMN_NAME=c.COLUMN_NAME)
    ),
    removed_columns AS (
        SELECT p.TABLE_SCHEMA, p.TABLE_NAME, p.COLUMN_NAME, p.DATA_TYPE
        FROM prev p
        WHERE NOT EXISTS (SELECT 1 FROM curr c WHERE c.TABLE_SCHEMA=p.TABLE_SCHEMA AND c.TABLE_NAME=p.TABLE_NAME AND c.COLUMN_NAME=p.COLUMN_NAME)
    )
    SELECT CURRENT_TIMESTAMP(), TABLE_SCHEMA, TABLE_NAME, COLUMN_NAME, 'DATATYPE_CHANGED', OLD_TYPE, NEW_TYPE,
           (SELECT LISTAGG(MAPPING_ID, ',') FROM SUPPLY_CHAIN_PLATFORM.GOVERNANCE.MAPPING_REGISTRY m
            WHERE m.SOURCE_TABLE = dc.TABLE_NAME AND m.SOURCE_COLUMN = dc.COLUMN_NAME)
    FROM datatype_changes dc
    UNION ALL
    SELECT CURRENT_TIMESTAMP(), TABLE_SCHEMA, TABLE_NAME, COLUMN_NAME, 'COLUMN_ADDED', NULL, DATA_TYPE, NULL
    FROM added_columns
    UNION ALL
    SELECT CURRENT_TIMESTAMP(), TABLE_SCHEMA, TABLE_NAME, COLUMN_NAME, 'COLUMN_REMOVED', DATA_TYPE, NULL,
           (SELECT LISTAGG(MAPPING_ID, ',') FROM SUPPLY_CHAIN_PLATFORM.GOVERNANCE.MAPPING_REGISTRY m
            WHERE m.SOURCE_TABLE = rc.TABLE_NAME AND m.SOURCE_COLUMN = rc.COLUMN_NAME)
    FROM removed_columns rc;

    drift_count := SQLROWCOUNT;
    RETURN drift_count || ' drift event(s) logged.';
END;
$$;

-- ---------------------------------------------------------------
-- Admin-facing warning view (section 21: "Provide a warning for
-- administrators")
-- ---------------------------------------------------------------
CREATE OR REPLACE VIEW UNACKNOWLEDGED_SCHEMA_DRIFT AS
SELECT * FROM SCHEMA_DRIFT_LOG WHERE ACKNOWLEDGED = FALSE ORDER BY DETECTED_AT DESC;

-- ---------------------------------------------------------------
-- Test 7 walkthrough: change a source datatype and confirm it's caught.
-- ---------------------------------------------------------------
-- CALL TAKE_SCHEMA_SNAPSHOT();                                     -- baseline
-- ALTER TABLE RAW_ERP_A.PURCHASE_ORDER_ITEMS ALTER COLUMN EINDT SET DATA TYPE VARCHAR(20);  -- simulate drift (DATE -> VARCHAR, as in the spec's example)
-- CALL TAKE_SCHEMA_SNAPSHOT();                                     -- post-change
-- CALL DETECT_SCHEMA_DRIFT();
-- SELECT * FROM UNACKNOWLEDGED_SCHEMA_DRIFT WHERE COLUMN_NAME = 'EINDT';
-- Expect: DRIFT_TYPE='DATATYPE_CHANGED', OLD_VALUE='DATE', NEW_VALUE='VARCHAR(20)',
--         AFFECTED_MAPPING_IDS containing the MAP-#### row that maps EINDT.
