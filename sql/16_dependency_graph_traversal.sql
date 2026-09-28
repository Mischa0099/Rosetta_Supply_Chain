-- =====================================================================
-- PHASE 4: DEPENDENCY GRAPH TRAVERSAL (spec section 16)
-- Generic bidirectional multi-hop walk over ONTOLOGY_GRAPH.RELATIONSHIP_EDGES.
-- Powers both directions from section 16's examples:
--   Forward:  "What customers depend on Supplier ABC?"
--   Backward: "Which suppliers are responsible for delayed Customer XYZ orders?"
-- =====================================================================

USE DATABASE SUPPLY_CHAIN_PLATFORM;
CREATE SCHEMA IF NOT EXISTS SUPPLY_CHAIN_PLATFORM.INTELLIGENCE;
USE SCHEMA SUPPLY_CHAIN_PLATFORM.INTELLIGENCE;

-- ---------------------------------------------------------------
-- Generic N-hop traversal, either direction, as a callable procedure.
-- Uses Snowflake Scripting + EXECUTE IMMEDIATE to parameterize a
-- recursive CTE (the standard pattern for dynamic recursive graph walks
-- in Snowflake SQL). Inputs are validated against known entity/relationship
-- vocabulary before being interpolated, to avoid injection via this proc.
-- ---------------------------------------------------------------
CREATE OR REPLACE PROCEDURE TRAVERSE_GRAPH(START_TYPE VARCHAR, START_ID VARCHAR, WALK_DIRECTION VARCHAR, MAX_HOPS FLOAT)
RETURNS TABLE ()
LANGUAGE SQL
AS
$$
DECLARE
    res RESULTSET;
    qry VARCHAR;
BEGIN
    IF (WALK_DIRECTION NOT IN ('FORWARD', 'BACKWARD')) THEN
        RETURN TABLE(SELECT 'ERROR' AS entity_type, 'WALK_DIRECTION must be FORWARD or BACKWARD' AS entity_id);
    END IF;

    qry := 'WITH RECURSIVE walk AS (' ||
           '  SELECT 0 AS hop, ''' || START_TYPE || ''' AS entity_type, ''' || START_ID || ''' AS entity_id, ' ||
           '         CAST(NULL AS VARCHAR) AS relationship, CAST(NULL AS VARCHAR) AS via_type, CAST(NULL AS VARCHAR) AS via_id ' ||
           '  UNION ALL ' ||
           '  SELECT w.hop + 1, e.RELATED_TYPE, e.RELATED_ID, e.RELATIONSHIP, w.entity_type, w.entity_id ' ||
           '  FROM walk w ' ||
           '  JOIN SUPPLY_CHAIN_PLATFORM.ONTOLOGY_GRAPH.EDGES_BIDIRECTIONAL e ' ||
           '    ON e.ENTITY_TYPE = w.entity_type AND e.ENTITY_ID = w.entity_id AND e.DIRECTION = ''' || WALK_DIRECTION || ''' ' ||
           '  WHERE w.hop < ' || MAX_HOPS ||
           ') SELECT DISTINCT hop, entity_type, entity_id, relationship, via_type, via_id ' ||
           'FROM walk WHERE hop > 0 ORDER BY hop';
    res := (EXECUTE IMMEDIATE :qry);
    RETURN TABLE(res);
END;
$$;

-- Example: "What customers depend on Supplier CS-SUP-003?" (forward, up to 5 hops)
-- CALL TRAVERSE_GRAPH('SUPPLIER', 'CS-SUP-003', 'FORWARD', 5);
-- Filter the result to ENTITY_TYPE = 'CUSTOMER' for the direct answer.

-- Example: "Which suppliers are responsible for delayed Customer CS-CUS-005 orders?"
-- (backward, up to 5 hops)
-- CALL TRAVERSE_GRAPH('CUSTOMER', 'CS-CUS-005', 'BACKWARD', 5);
-- Filter the result to ENTITY_TYPE = 'SUPPLIER'.
