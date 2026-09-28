# Deploying the Streamlit app

## Option A — Streamlit in Snowflake (recommended)
1. Run all SQL scripts `00`–`21` first (see `../sql/00_setup_and_run_order.sql`).
2. Snowsight → Projects → Streamlit → **+ Streamlit App**. Pick database
   `SUPPLY_CHAIN_PLATFORM`, any schema (e.g. `INTELLIGENCE`) and warehouse `SUPPLY_CHAIN_WH`.
3. Upload this folder's contents keeping structure:
   `streamlit_app.py`, `common.py`, `environment.yml`, and `pages/*.py`.
4. Grant the app's role SELECT on all `SUPPLY_CHAIN_PLATFORM` schemas and
   USAGE/EXECUTE on the procedures in `GOVERNANCE` and `INTELLIGENCE`.

## Option B — run locally against Snowflake
```
pip install streamlit pandas snowflake-snowpark-python
# .streamlit/secrets.toml  ->  [connections.snowflake]  account/user/password/warehouse/database
streamlit run streamlit_app.py
```

## Notes
- The Conversational Analytics page tries Cortex Analyst first (only works
  inside Streamlit in Snowflake with Cortex Analyst enabled) and otherwise
  falls back to a simple router over the same governed metric views.
- This app has not been executed against a live Snowflake account in this
  build — expect to fix small things (role grants, object names) on first run.
