-- =====================================================================
-- PHASE 2: AI-POWERED SCHEMA MAPPING + MAPPING REGISTRY (spec sections 7-8)
-- =====================================================================

USE DATABASE SUPPLY_CHAIN_PLATFORM;
CREATE SCHEMA IF NOT EXISTS SUPPLY_CHAIN_PLATFORM.GOVERNANCE;
USE SCHEMA SUPPLY_CHAIN_PLATFORM.GOVERNANCE;

CREATE OR REPLACE FILE FORMAT CSV_STANDARD
    TYPE = CSV FIELD_DELIMITER = ',' SKIP_HEADER = 1 FIELD_OPTIONALLY_ENCLOSED_BY = '"'
    NULL_IF = ('', 'NULL') EMPTY_FIELD_AS_NULL = TRUE;

CREATE OR REPLACE STAGE GOVERNANCE_STAGE FILE_FORMAT = CSV_STANDARD;
-- PUT file:///local/path/csv/governance/*.csv @GOVERNANCE_STAGE AUTO_COMPRESS=TRUE;

-- ---------------------------------------------------------------
-- MAPPING REGISTRY
-- One row per proposed (source column -> canonical attribute) mapping.
-- Approved mappings are reusable: once APPROVAL_STATUS = 'APPROVED' (human)
-- or 'AUTO_APPROVED' (system), the semantic layer and ingestion pipelines
-- read FROM THIS TABLE rather than re-deriving mappings each run.
-- ---------------------------------------------------------------
CREATE OR REPLACE TABLE MAPPING_REGISTRY (
    MAPPING_ID              VARCHAR(20)   NOT NULL,
    SOURCE_SYSTEM             VARCHAR(10)   COMMENT 'ERP_A / ERP_B / future source systems',
    SOURCE_TABLE                 VARCHAR(50),
    SOURCE_COLUMN                   VARCHAR(50),
    CANONICAL_ENTITY                  VARCHAR(30)   COMMENT 'SUPPLIER / PRODUCT / PLANT / CUSTOMER / ORDER / ORDER_LINE / CONTRACT / INVENTORY / ...',
    CANONICAL_ATTRIBUTE                  VARCHAR(50),
    TRANSFORMATION                          VARCHAR(200)  COMMENT 'e.g. direct copy, zero-pad strip, unit conversion, date format normalization',
    CONFIDENCE_SCORE                          NUMBER(5,2)   COMMENT '0-100, AI-proposed confidence',
    RATIONALE                                    VARCHAR(1000) COMMENT 'Why the AI proposed this mapping - shown to the human reviewer',
    APPROVAL_STATUS                                 VARCHAR(20)   COMMENT 'AUTO_APPROVED / PENDING_REVIEW / NEEDS_CLARIFICATION / REJECTED / APPROVED (human) / MODIFIED',
    APPROVED_BY                                        VARCHAR(50)   COMMENT 'SYSTEM_AUTO_APPROVAL, or the reviewer identity for human decisions',
    MAPPING_VERSION                                       NUMBER(5,0)   DEFAULT 1,
    CREATED_AT                                               TIMESTAMP_TZ,
    UPDATED_AT                                                  TIMESTAMP_TZ,
    CONSTRAINT PK_MAPPING_REGISTRY PRIMARY KEY (MAPPING_ID)
);

COPY INTO MAPPING_REGISTRY FROM @GOVERNANCE_STAGE/mapping_registry.csv;

-- ---------------------------------------------------------------
-- Confidence-based governance thresholds (configurable - section 8).
-- Stored as a one-row config table rather than hardcoded, so an admin
-- can retune without a code change.
-- ---------------------------------------------------------------
CREATE OR REPLACE TABLE MAPPING_CONFIDENCE_THRESHOLDS (
    AUTO_APPROVE_AT_OR_ABOVE   NUMBER(5,2) DEFAULT 90.0,
    HUMAN_REVIEW_AT_OR_ABOVE      NUMBER(5,2) DEFAULT 60.0,
    NEEDS_CLARIFICATION_AT_OR_ABOVE  NUMBER(5,2) DEFAULT 45.0
    -- below NEEDS_CLARIFICATION_AT_OR_ABOVE -> REJECTED
);
INSERT INTO MAPPING_CONFIDENCE_THRESHOLDS VALUES (90.0, 60.0, 45.0);

CREATE OR REPLACE VIEW MAPPING_REGISTRY_RECLASSIFIED AS
SELECT m.*,
    CASE
        WHEN m.CONFIDENCE_SCORE >= t.AUTO_APPROVE_AT_OR_ABOVE THEN 'AUTO_APPROVED'
        WHEN m.CONFIDENCE_SCORE >= t.HUMAN_REVIEW_AT_OR_ABOVE THEN 'PENDING_REVIEW'
        WHEN m.CONFIDENCE_SCORE >= t.NEEDS_CLARIFICATION_AT_OR_ABOVE THEN 'NEEDS_CLARIFICATION'
        ELSE 'REJECTED'
    END AS RECOMMENDED_STATUS
FROM MAPPING_REGISTRY m, MAPPING_CONFIDENCE_THRESHOLDS t;
-- Use this view (not raw CONFIDENCE_SCORE) whenever thresholds might have
-- changed since a mapping was first proposed - it recomputes live.

-- ---------------------------------------------------------------
-- HUMAN REVIEW QUEUE (feeds the "Human Review" Streamlit page, section 22)
-- ---------------------------------------------------------------
CREATE OR REPLACE VIEW HUMAN_REVIEW_QUEUE AS
SELECT MAPPING_ID, SOURCE_SYSTEM, SOURCE_TABLE, SOURCE_COLUMN,
       CANONICAL_ENTITY, CANONICAL_ATTRIBUTE, CONFIDENCE_SCORE, RATIONALE
FROM MAPPING_REGISTRY
WHERE APPROVAL_STATUS IN ('PENDING_REVIEW', 'NEEDS_CLARIFICATION')
ORDER BY CONFIDENCE_SCORE DESC;

-- ---------------------------------------------------------------
-- Human-in-the-loop actions (section 8: Approve / Reject / Modify Mapping)
-- ---------------------------------------------------------------
CREATE OR REPLACE PROCEDURE APPROVE_MAPPING(P_MAPPING_ID VARCHAR, P_REVIEWER VARCHAR)
RETURNS VARCHAR
LANGUAGE SQL
AS
$$
BEGIN
    UPDATE MAPPING_REGISTRY
    SET APPROVAL_STATUS = 'APPROVED', APPROVED_BY = :P_REVIEWER, UPDATED_AT = CURRENT_TIMESTAMP()
    WHERE MAPPING_ID = :P_MAPPING_ID;
    RETURN 'Mapping ' || :P_MAPPING_ID || ' approved by ' || :P_REVIEWER;
END;
$$;

CREATE OR REPLACE PROCEDURE REJECT_MAPPING(P_MAPPING_ID VARCHAR, P_REVIEWER VARCHAR, P_REASON VARCHAR)
RETURNS VARCHAR
LANGUAGE SQL
AS
$$
BEGIN
    UPDATE MAPPING_REGISTRY
    SET APPROVAL_STATUS = 'REJECTED', APPROVED_BY = :P_REVIEWER,
        RATIONALE = RATIONALE || ' | Reviewer rejection reason: ' || :P_REASON,
        UPDATED_AT = CURRENT_TIMESTAMP()
    WHERE MAPPING_ID = :P_MAPPING_ID;
    RETURN 'Mapping ' || :P_MAPPING_ID || ' rejected by ' || :P_REVIEWER;
END;
$$;

CREATE OR REPLACE PROCEDURE MODIFY_MAPPING(P_MAPPING_ID VARCHAR, P_REVIEWER VARCHAR,
    P_NEW_ENTITY VARCHAR, P_NEW_ATTRIBUTE VARCHAR)
RETURNS VARCHAR
LANGUAGE SQL
AS
$$
BEGIN
    UPDATE MAPPING_REGISTRY
    SET CANONICAL_ENTITY = :P_NEW_ENTITY, CANONICAL_ATTRIBUTE = :P_NEW_ATTRIBUTE,
        APPROVAL_STATUS = 'MODIFIED', APPROVED_BY = :P_REVIEWER,
        MAPPING_VERSION = MAPPING_VERSION + 1, UPDATED_AT = CURRENT_TIMESTAMP()
    WHERE MAPPING_ID = :P_MAPPING_ID;
    RETURN 'Mapping ' || :P_MAPPING_ID || ' modified by ' || :P_REVIEWER;
END;
$$;

-- Example usage:
-- CALL APPROVE_MAPPING('MAP-0022', 'jane.procurement@company.com');
-- CALL REJECT_MAPPING('MAP-0006', 'jane.procurement@company.com', 'SPERR should stay unmapped until Supplier Hold Status is added to the ontology');
-- CALL MODIFY_MAPPING('MAP-0018', 'jane.procurement@company.com', 'ORDER_LINE', 'requested_delivery_date');

-- ---------------------------------------------------------------
-- Test 5 validation: an ambiguous field must require human review,
-- never auto-approve.
-- ---------------------------------------------------------------
-- SELECT * FROM MAPPING_REGISTRY WHERE SOURCE_COLUMN = 'EINDT' AND SOURCE_SYSTEM = 'ERP_A';
-- Expect: CONFIDENCE_SCORE = 72.0, APPROVAL_STATUS = 'PENDING_REVIEW' (not AUTO_APPROVED)

-- =====================================================================
-- PRODUCTION MAPPING-PROPOSAL MECHANISM (live AI, not the static CSV load
-- above). For a NEW source system, run this instead of hand-authoring
-- proposals: it inspects INFORMATION_SCHEMA metadata + sample values and
-- calls Cortex to propose a mapping, in the exact output shape the
-- registry expects. This is what Phase 2 formalizes end-to-end; the
-- static CSV above exists only so this demo has data without a live call.
-- =====================================================================
CREATE OR REPLACE FUNCTION PROPOSE_MAPPING(
    SOURCE_TABLE_NAME VARCHAR, SOURCE_COLUMN_NAME VARCHAR, SOURCE_DATATYPE VARCHAR,
    SAMPLE_VALUES VARCHAR, CANONICAL_SCHEMA_DESCRIPTION VARCHAR
)
RETURNS VARCHAR
LANGUAGE SQL
AS
$$
    SELECT SNOWFLAKE.CORTEX.COMPLETE(
        'llama3.1-70b',
        'You are a supply-chain data engineer mapping a source ERP column to a ' ||
        'canonical business ontology. Respond with ONLY a JSON object: ' ||
        '{"canonical_entity": "...", "canonical_attribute": "...", ' ||
        '"confidence_0_to_100": <number>, "transformation": "...", "rationale": "..."}. ' ||
        'If no canonical attribute fits, set canonical_entity/canonical_attribute to null ' ||
        'and confidence below 50.\n\n' ||
        'Canonical ontology:\n' || CANONICAL_SCHEMA_DESCRIPTION || '\n\n' ||
        'Source table: ' || SOURCE_TABLE_NAME || '\n' ||
        'Source column: ' || SOURCE_COLUMN_NAME || '\n' ||
        'Source datatype: ' || SOURCE_DATATYPE || '\n' ||
        'Sample values: ' || SAMPLE_VALUES
    )
$$;

-- Example: generate proposals for every column of a newly-connected source
-- table, then INSERT the parsed JSON results into MAPPING_REGISTRY:
--
-- SELECT column_name, data_type,
--        PROPOSE_MAPPING(table_name, column_name, data_type,
--                         '(sample values collected separately)',
--                         '(canonical ontology description - see docs/ontology_diagram.md)') AS proposal_json
-- FROM INFORMATION_SCHEMA.COLUMNS
-- WHERE TABLE_SCHEMA = 'RAW_ERP_C'   -- a new, not-yet-mapped source
-- ORDER BY table_name, ordinal_position;
