import sys
from pathlib import Path

import streamlit as st

# Add parent directory to path to import utils
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

st.set_page_config(page_title="Raw Data", layout="wide")

# ── Session State Validation ──────────────────────────────────────────────────
if "df" not in st.session_state or not st.session_state.get("data_loaded", False):
    st.error("⚠️ No data loaded. Please return to the main page and load data first.")
    st.stop()

# Get variables from session state
df = st.session_state.df
raw = st.session_state.raw

# ── Tab 8: Raw Data ───────────────────────────────────────────────────────────
col_a, col_b = st.columns(2)
with col_a:
    st.subheader("Raw uploaded data")
    st.dataframe(raw, use_container_width=True, hide_index=True)
with col_b:
    st.subheader("Pivoted (wide) data")
    st.dataframe(df, use_container_width=True, hide_index=True)

st.download_button(
    "Download pivoted data as CSV",
    data=df.to_csv(index=False).encode("utf-8"),
    file_name="energy_pivoted.csv",
    mime="text/csv",
)
