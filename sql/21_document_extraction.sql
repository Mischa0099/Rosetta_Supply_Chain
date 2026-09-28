-- =====================================================================
-- PHASE 5: DOCUMENT EXTRACTION (spec section 15, Test 8)
-- Extracts structured fields (SLA, lead time, delivery term, dates,
-- applicable products) from the synthetic supplier contracts in
-- @SUPPLIER_CONTRACTS_STAGE using Cortex, then links the result back to
-- ONTOLOGY_CORE.CONTRACT (which today sits at EXTRACTION_STATUS =
-- 'PENDING_AI_EXTRACTION' for all 10 rows - see sql/08 / README).
-- =====================================================================

USE DATABASE SUPPLY_CHAIN_PLATFORM;
USE SCHEMA SUPPLY_CHAIN_PLATFORM.RAW_DOCUMENTS;

-- ---------------------------------------------------------------
-- Read every contract's raw text off the stage. .txt files don't need
-- PARSE_DOCUMENT's layout parsing (that earns its keep on PDFs/scanned
-- docs); a stage SELECT is enough here. For real supplier contracts
-- (PDF/DOCX) swap this for:
--   SELECT RELATIVE_PATH, SNOWFLAKE.CORTEX.PARSE_DOCUMENT(
--       @SUPPLIER_CONTRACTS_STAGE, RELATIVE_PATH, {'mode':'LAYOUT'}
--   ):content::VARCHAR AS CONTRACT_TEXT
--   FROM DIRECTORY(@SUPPLIER_CONTRACTS_STAGE);
-- ---------------------------------------------------------------
CREATE OR REPLACE VIEW CONTRACT_RAW_TEXT AS
SELECT METADATA$FILENAME AS RELATIVE_PATH,
       REGEXP_SUBSTR(METADATA$FILENAME, 'contract_(C[0-9]+)\\.txt', 1, 1, 'e', 1) AS SOURCE_CONTRACT_ID,
       $1 AS CONTRACT_TEXT  -- one row per line; aggregate below
FROM @SUPPLIER_CONTRACTS_STAGE (FILE_FORMAT => (RECORD_DELIMITER => NONE));

CREATE OR REPLACE VIEW CONTRACT_FULL_TEXT AS
SELECT SOURCE_CONTRACT_ID, RELATIVE_PATH, CONTRACT_TEXT AS FULL_TEXT
FROM CONTRACT_RAW_TEXT;

-- ---------------------------------------------------------------
-- Cortex extraction: one COMPLETE call per contract, constrained to a
-- strict JSON schema so the result parses deterministically.
-- ---------------------------------------------------------------
CREATE OR REPLACE FUNCTION EXTRACT_CONTRACT_FIELDS(CONTRACT_TEXT VARCHAR)
RETURNS VARCHAR
LANGUAGE SQL
AS
$$
    SELECT SNOWFLAKE.CORTEX.COMPLETE(
        'llama3.1-70b',
        'Extract the following fields from this supply agreement as a JSON object ' ||
        'with EXACTLY these keys: contract_reference, supplier_name, effective_date ' ||
        '(YYYY-MM-DD), expiration_date (YYYY-MM-DD), sla_days (integer), ' ||
        'lead_time_days (integer), delivery_term (string), min_otd_pct (number), ' ||
        'penalty_pct (number), currency (3-letter code), applicable_products ' ||
        '(array of strings), confidence_0_to_100 (integer - your own confidence ' ||
        'that every field above was extracted correctly from THIS text). ' ||
        'Respond with ONLY the JSON object, no commentary.\n\nCONTRACT TEXT:\n' || CONTRACT_TEXT
    )
$$;

CREATE OR REPLACE TABLE CONTRACT_EXTRACTION_RESULTS (
    SOURCE_CONTRACT_ID   VARCHAR(10),
    RAW_MODEL_OUTPUT        VARCHAR(4000),
    EXTRACTED_AT               TIMESTAMP_TZ,
    CONSTRAINT PK_EXTRACTION_RESULTS PRIMARY KEY (SOURCE_CONTRACT_ID)
);

-- Run extraction over every contract currently on the stage:
INSERT INTO CONTRACT_EXTRACTION_RESULTS (SOURCE_CONTRACT_ID, RAW_MODEL_OUTPUT, EXTRACTED_AT)
SELECT SOURCE_CONTRACT_ID, EXTRACT_CONTRACT_FIELDS(FULL_TEXT), CURRENT_TIMESTAMP()
FROM CONTRACT_FULL_TEXT;

-- ---------------------------------------------------------------
-- Parse the JSON and merge into the canonical CONTRACT table, applying
-- the SAME confidence governance tiers as the schema-mapping registry
-- (guardrail: never invent/auto-accept a low-confidence AI output silently).
-- ---------------------------------------------------------------
CREATE OR REPLACE PROCEDURE APPLY_CONTRACT_EXTRACTION()
RETURNS VARCHAR
LANGUAGE SQL
AS
$$
BEGIN
    UPDATE SUPPLY_CHAIN_PLATFORM.ONTOLOGY_CORE.CONTRACT c
    SET EFFECTIVE_DATE = TRY_TO_DATE(PARSE_JSON(r.RAW_MODEL_OUTPUT):effective_date::VARCHAR),
        EXPIRATION_DATE = TRY_TO_DATE(PARSE_JSON(r.RAW_MODEL_OUTPUT):expiration_date::VARCHAR),
        SLA_DAYS = PARSE_JSON(r.RAW_MODEL_OUTPUT):sla_days::NUMBER,
        LEAD_TIME_DAYS = PARSE_JSON(r.RAW_MODEL_OUTPUT):lead_time_days::NUMBER,
        DELIVERY_TERM = PARSE_JSON(r.RAW_MODEL_OUTPUT):delivery_term::VARCHAR,
        MIN_OTD_PCT = PARSE_JSON(r.RAW_MODEL_OUTPUT):min_otd_pct::NUMBER,
        PENALTY_PCT = PARSE_JSON(r.RAW_MODEL_OUTPUT):penalty_pct::NUMBER,
        CURRENCY = PARSE_JSON(r.RAW_MODEL_OUTPUT):currency::VARCHAR,
        APPLICABLE_PRODUCTS = ARRAY_TO_STRING(PARSE_JSON(r.RAW_MODEL_OUTPUT):applicable_products, '; '),
        EXTRACTION_CONFIDENCE = PARSE_JSON(r.RAW_MODEL_OUTPUT):confidence_0_to_100::NUMBER,
        EXTRACTION_STATUS = CASE
            WHEN PARSE_JSON(r.RAW_MODEL_OUTPUT):confidence_0_to_100::NUMBER >= 90 THEN 'AUTO_ACCEPTED'
            WHEN PARSE_JSON(r.RAW_MODEL_OUTPUT):confidence_0_to_100::NUMBER >= 60 THEN 'PENDING_REVIEW'
            ELSE 'NEEDS_CLARIFICATION' END
    FROM SUPPLY_CHAIN_PLATFORM.RAW_DOCUMENTS.CONTRACT_EXTRACTION_RESULTS r
    WHERE c.SOURCE_CONTRACT_ID = r.SOURCE_CONTRACT_ID;
    RETURN 'Contract extraction merged for ' || SQLROWCOUNT || ' contract(s).';
END;
$$;

-- CALL APPLY_CONTRACT_EXTRACTION();
-- SELECT SOURCE_CONTRACT_ID, EXTRACTION_STATUS, EXTRACTION_CONFIDENCE, SLA_DAYS, LEAD_TIME_DAYS
-- FROM SUPPLY_CHAIN_PLATFORM.ONTOLOGY_CORE.CONTRACT ORDER BY SOURCE_CONTRACT_ID;

-- ---------------------------------------------------------------
-- Test 8 validation: compare extracted values against the ground truth
-- manifest generated alongside the synthetic contracts (docs/contracts_ground_truth.csv,
-- loaded as RAW_DOCUMENTS.CONTRACTS_GROUND_TRUTH). See docs/document_extraction_example.md
-- for the actual accuracy achieved on this dataset.
-- ---------------------------------------------------------------
CREATE OR REPLACE VIEW CONTRACT_EXTRACTION_ACCURACY AS
SELECT c.SOURCE_CONTRACT_ID,
       c.SLA_DAYS = g.SLA_DAYS AS SLA_DAYS_CORRECT,
       c.LEAD_TIME_DAYS = g.LEAD_TIME_DAYS AS LEAD_TIME_CORRECT,
       c.DELIVERY_TERM = g.DELIVERY_TERM AS DELIVERY_TERM_CORRECT,
       c.EFFECTIVE_DATE = g.EFFECTIVE_DATE AS EFFECTIVE_DATE_CORRECT,
       c.EXTRACTION_CONFIDENCE, c.EXTRACTION_STATUS
FROM SUPPLY_CHAIN_PLATFORM.ONTOLOGY_CORE.CONTRACT c
JOIN SUPPLY_CHAIN_PLATFORM.RAW_DOCUMENTS.CONTRACTS_GROUND_TRUTH g ON g.CONTRACT_ID = c.SOURCE_CONTRACT_ID;
