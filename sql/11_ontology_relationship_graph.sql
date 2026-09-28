-- =====================================================================
-- DEPENDENCY / RELATIONSHIP GRAPH
-- A single generic edge list spanning CORE + GOODS + MANUFACTURING +
-- SERVICES. This is what Phase 4 (dependency graph, impact analysis) and
-- the Ontology Explorer traverse. Stored as one directed edge per
-- relationship instance; traverse it in either direction with the two
-- helper views below (forward: FROM -> TO, backward: TO -> FROM).
-- =====================================================================

USE DATABASE SUPPLY_CHAIN_PLATFORM;
CREATE SCHEMA IF NOT EXISTS SUPPLY_CHAIN_PLATFORM.ONTOLOGY_GRAPH;
USE SCHEMA SUPPLY_CHAIN_PLATFORM.ONTOLOGY_GRAPH;

CREATE OR REPLACE FILE FORMAT CSV_STANDARD
    TYPE = CSV FIELD_DELIMITER = ',' SKIP_HEADER = 1 FIELD_OPTIONALLY_ENCLOSED_BY = '"'
    NULL_IF = ('', 'NULL') EMPTY_FIELD_AS_NULL = TRUE;

CREATE OR REPLACE STAGE ONTOLOGY_GRAPH_STAGE FILE_FORMAT = CSV_STANDARD;
-- PUT file:///local/path/csv/ontology_graph/*.csv @ONTOLOGY_GRAPH_STAGE AUTO_COMPRESS=TRUE;

CREATE OR REPLACE TABLE RELATIONSHIP_EDGES (
    FROM_TYPE       VARCHAR(20)  NOT NULL COMMENT 'SUPPLIER/PRODUCT/PLANT/CUSTOMER/ORDER/SHIPMENT/CONTRACT/WAREHOUSE/PRODUCTION_LINE/PRODUCTION_ORDER',
    FROM_ID          VARCHAR(30)  NOT NULL,
    RELATIONSHIP       VARCHAR(30)  NOT NULL COMMENT 'e.g. supplies, fulfills, contains, belongs_to, transports, stored_at, produces, requires',
    TO_TYPE               VARCHAR(20)  NOT NULL,
    TO_ID                  VARCHAR(30)  NOT NULL
);

COPY INTO RELATIONSHIP_EDGES FROM @ONTOLOGY_GRAPH_STAGE/relationship_edges.csv;

-- Convenience views for bidirectional traversal in the Ontology Explorer / Impact Analysis pages:

CREATE OR REPLACE VIEW EDGES_FORWARD AS
SELECT FROM_TYPE AS ENTITY_TYPE, FROM_ID AS ENTITY_ID, RELATIONSHIP,
       TO_TYPE AS RELATED_TYPE, TO_ID AS RELATED_ID, 'FORWARD' AS DIRECTION
FROM RELATIONSHIP_EDGES;

CREATE OR REPLACE VIEW EDGES_BACKWARD AS
SELECT TO_TYPE AS ENTITY_TYPE, TO_ID AS ENTITY_ID, RELATIONSHIP,
       FROM_TYPE AS RELATED_TYPE, FROM_ID AS RELATED_ID, 'BACKWARD' AS DIRECTION
FROM RELATIONSHIP_EDGES;

CREATE OR REPLACE VIEW EDGES_BIDIRECTIONAL AS
SELECT * FROM EDGES_FORWARD
UNION ALL
SELECT * FROM EDGES_BACKWARD;

-- Example traversal: "what depends on Supplier CS-SUP-001?" (one hop)
-- SELECT * FROM EDGES_FORWARD WHERE ENTITY_TYPE = 'SUPPLIER' AND ENTITY_ID = 'CS-SUP-001';
--
-- Example: "what suppliers feed Customer CS-CUS-005?" (walk backward from customer)
-- SELECT * FROM EDGES_BACKWARD WHERE ENTITY_TYPE = 'CUSTOMER' AND ENTITY_ID = 'CS-CUS-005';
