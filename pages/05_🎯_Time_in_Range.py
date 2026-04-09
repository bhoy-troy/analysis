"""Time-in-Range Analysis page - Food Safety Compliance"""

import sys

import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

sys.path.append("..")
from utils.calculations import calculate_time_in_range

st.title("🎯 Time-in-Range Analysis")
st.markdown("**Food Safety Compliance Monitoring**")

# Get data from session state
if "df" not in st.session_state or st.session_state.df.empty:
    st.warning("⚠️ No data loaded. Please return to the main page and load data first.")
    st.info("1. Select a premises\n2. Choose date range\n3. Click 'Load Data'")
    st.stop()

if "selected_cabinet" not in st.session_state:
    st.warning("⚠️ Please select a cabinet from the main page first")
    st.stop()

df = st.session_state.df
selected_cabinet = st.session_state.selected_cabinet
is_freezer = st.session_state.is_freezer
cabinet_df = df[df["cabinet"] == selected_cabinet].copy()

st.header(f"Time-in-Range: {selected_cabinet}")

# Calculate time-in-range metrics
time_range_metrics = calculate_time_in_range(cabinet_df, is_freezer)

st.subheader("Temperature Range Distribution")

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("Optimal Range", f"{time_range_metrics['optimal_pct']:.1f}%", help=time_range_metrics["optimal_range"])
    st.caption(time_range_metrics["optimal_range"])

with col2:
    st.metric("Warning Range", f"{time_range_metrics['warning_pct']:.1f}%", help=time_range_metrics["warning_range"])
    st.caption(time_range_metrics["warning_range"])

with col3:
    st.metric(
        "Critical",
        f"{time_range_metrics['critical_pct']:.1f}%",
        delta=f"{-time_range_metrics['critical_pct']:.1f}%" if time_range_metrics["critical_pct"] > 0 else None,
        delta_color="inverse",
        help=time_range_metrics["critical_threshold"],
    )
    st.caption(time_range_metrics["critical_threshold"])

with col4:
    st.metric("Below Optimal", f"{time_range_metrics['below_optimal_pct']:.1f}%")
    st.caption("Too cold")

# Pie chart
fig = go.Figure(
    data=[
        go.Pie(
            labels=["Optimal", "Warning", "Critical", "Below Optimal"],
            values=[
                time_range_metrics["optimal_pct"],
                time_range_metrics["warning_pct"],
                time_range_metrics["critical_pct"],
                time_range_metrics["below_optimal_pct"],
            ],
            marker={"colors": ["green", "orange", "red", "lightblue"]},
            hole=0.4,
        )
    ]
)
fig.update_layout(title="Time-in-Range Distribution")
st.plotly_chart(fig, use_container_width=True)

# Daily compliance
st.subheader("Daily Compliance Analysis")

cabinet_df_daily = cabinet_df.copy()
cabinet_df_daily["in_optimal"] = (cabinet_df_daily["temperature_celsius"] >= (-25 if is_freezer else 0)) & (
    cabinet_df_daily["temperature_celsius"] <= (-18 if is_freezer else 5)
)

daily_compliance = (
    cabinet_df_daily.groupby("date").agg({"in_optimal": lambda x: (x.sum() / len(x)) * 100}).reset_index()
)
daily_compliance.columns = ["date", "compliance_pct"]

fig = px.bar(
    daily_compliance,
    x="date",
    y="compliance_pct",
    title="Daily Compliance Rate (% Time in Optimal Range)",
    color="compliance_pct",
    color_continuous_scale=["red", "orange", "green"],
    range_color=[0, 100],
)
fig.update_layout(xaxis_title="Date", yaxis_title="Compliance %", yaxis_range=[0, 105])
fig.add_hline(y=95, line_dash="dash", line_color="green", annotation_text="95% Target")
st.plotly_chart(fig, use_container_width=True)

# Compliance summary
avg_compliance = daily_compliance["compliance_pct"].mean()
days_compliant = len(daily_compliance[daily_compliance["compliance_pct"] >= 95])
total_days = len(daily_compliance)

st.info(f"""
**Summary:** {days_compliant}/{total_days} days met 95% compliance target
(Average: {avg_compliance:.1f}%)
""")

# Export
csv = daily_compliance.to_csv(index=False)
st.download_button(
    label="📥 Download Compliance Data", data=csv, file_name=f"{selected_cabinet}_compliance.csv", mime="text/csv"
)
