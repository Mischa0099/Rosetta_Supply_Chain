"""
Shared helpers for every page of the Adaptive Supply Chain Intelligence app.

Designed to run as native "Streamlit in Snowflake" (uses
get_active_session()). If you're instead running this externally
(`streamlit run streamlit_app.py` against a Snowflake account from your
laptop/CI), set SNOWFLAKE_CONNECTION_NAME as an env var pointing at a
connections.toml entry, or fill in st.connection("snowflake") config in
secrets.toml - session() below falls back to that automatically.
"""
import streamlit as st
import pandas as pd

DB = "SUPPLY_CHAIN_PLATFORM"


@st.cache_resource
def get_session():
    try:
        from snowflake.snowpark.context import get_active_session
        return get_active_session()
    except Exception:
        # External Streamlit fallback - requires .streamlit/secrets.toml
        # with a [connections.snowflake] block.
        conn = st.connection("snowflake")
        return conn.session()


def run(sql: str) -> pd.DataFrame:
    """Run SQL and return a pandas DataFrame. Cached per-query-string for 60s
    so navigating between pages doesn't re-hit the warehouse unnecessarily."""
    return _run_cached(sql)


@st.cache_data(ttl=60)
def _run_cached(sql: str) -> pd.DataFrame:
    session = get_session()
    return session.sql(sql).to_pandas()


def call_scalar_proc(call_sql: str) -> str:
    """Call a stored procedure that returns a single VARCHAR, and clear the
    query cache afterward since state may have changed (e.g. an approval)."""
    session = get_session()
    result = session.sql(call_sql).collect()
    _run_cached.clear()
    return result[0][0] if result else None


def confidence_badge(pct: float) -> str:
    if pct is None:
        return "⚪ n/a"
    if pct >= 90:
        return f"🟢 {pct:.1f}%"
    if pct >= 60:
        return f"🟡 {pct:.1f}%"
    if pct >= 45:
        return f"🟠 {pct:.1f}%"
    return f"🔴 {pct:.1f}%"


def page_header(title: str, subtitle: str = ""):
    st.title(title)
    if subtitle:
        st.caption(subtitle)
    st.divider()
