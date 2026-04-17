import sys
from pathlib import Path

import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# Add parent directory to path to import utils
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

st.set_page_config(page_title="Peak Demand", layout="wide")

# ── Session State Validation ──────────────────────────────────────────────────
if "df" not in st.session_state or not st.session_state.get("data_loaded", False):
    st.error("⚠️ No data loaded. Please return to the main page and load data first.")
    st.stop()

# Get variables from session state
df = st.session_state.df
MIC = st.session_state.MIC
demand_warning_pct = st.session_state.demand_warning_pct

# ── Tab 2: Peak Demand ────────────────────────────────────────────────────────
if "Total kW" in df.columns:
    st.subheader("Hourly peak demand vs MIC")
    df["hour"] = df["timestamp"].dt.hour
    hourly_peak = df.groupby("hour")["Total kW"].max().reset_index()
    hourly_peak.columns = ["Hour", "Peak kW"]
    hourly_peak["Status"] = hourly_peak["Peak kW"].apply(
        lambda v: "Over Warning" if v >= MIC * demand_warning_pct / 100 else "Normal"
    )
    fig3 = px.bar(
        hourly_peak,
        x="Hour",
        y="Peak kW",
        color="Status",
        color_discrete_map={"Over Warning": "#EF4444", "Normal": "#3B82F6"},
    )
    fig3.add_hline(y=MIC, line_dash="dot", line_color="red", annotation_text=f"MIC {MIC} kW")
    fig3.add_hline(
        y=MIC * demand_warning_pct / 100,
        line_dash="dot",
        line_color="orange",
        annotation_text=f"Warning {demand_warning_pct}%",
    )
    fig3.update_layout(
        xaxis={"title": "Hour of Day", "dtick": 1},
        yaxis={"title": "Peak kW", "range": [0, MIC * 1.15], "dtick": 50},
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "xanchor": "center", "x": 0.5},
    )
    st.plotly_chart(fig3, use_container_width=True)

    st.subheader("Demand as % of MIC over time")
    df["MIC %"] = (df["Total kW"] / MIC) * 100
    fig4 = go.Figure()
    fig4.add_trace(
        go.Scatter(
            x=df["timestamp"], y=df["MIC %"], mode="lines", fill="tozeroy", name="Demand % MIC", line={"width": 2}
        )
    )
    fig4.add_hline(y=100, line_dash="dot", line_color="red", annotation_text="MIC 100%")
    fig4.add_hline(
        y=demand_warning_pct, line_dash="dot", line_color="orange", annotation_text=f"Warning {demand_warning_pct}%"
    )
    fig4.update_layout(
        xaxis={"title": "Timestamp"},
        yaxis={"title": "% of MIC", "range": [0, 115], "dtick": 10},
        hovermode="x unified",
    )
    st.plotly_chart(fig4, use_container_width=True)
else:
    st.info("Total kW data not available.")
