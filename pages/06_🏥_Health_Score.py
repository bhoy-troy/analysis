"""Equipment Health Score page - Predictive Maintenance"""

import streamlit as st
import pandas as pd
import plotly.express as px
import sys
sys.path.append('..')
from utils.calculations import (
    calculate_health_score,
    get_health_status,
    calculate_time_in_range,
    detect_defrost_cycles,
    calculate_recovery_time
)

st.title("🏥 Equipment Health Score")
st.markdown("**Predictive Maintenance Analysis**")

# Get data from session state
if 'selected_cabinet' not in st.session_state:
    st.warning("⚠️ Please select a cabinet from the main page first")
    st.stop()

df = st.session_state.df
selected_cabinet = st.session_state.selected_cabinet
is_freezer = st.session_state.is_freezer
cabinet_df = df[df['cabinet'] == selected_cabinet].copy()

st.header(f"Health Score: {selected_cabinet}")

# Calculate health score
health_data = calculate_health_score(cabinet_df, is_freezer)
status, emoji, color = get_health_status(health_data['overall_score'])
time_range_metrics = calculate_time_in_range(cabinet_df, is_freezer)

# Overall health display
col1, col2, col3 = st.columns([2, 1, 1])

with col1:
    st.markdown(f"### {emoji} Overall Health: {status}")
    st.progress(health_data['overall_score'] / 100)
    st.metric("Health Score", f"{health_data['overall_score']:.1f}/100")

with col2:
    st.metric("Temp Stability (σ)", f"{health_data['temp_std']:.2f}°C")
    st.metric("Temp Drift", f"{health_data['temp_drift']:+.2f}°C")

with col3:
    if health_data['overall_score'] < 60:
        st.error("⚠️ Maintenance Required")
    elif health_data['overall_score'] < 75:
        st.warning("⚡ Monitor Closely")
    else:
        st.success("✅ Healthy")

# Component scores
st.subheader("Component Health Breakdown")

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric(
        "Stability",
        f"{health_data['stability_score']:.0f}/100",
        help="Based on temperature standard deviation"
    )
    st.progress(health_data['stability_score'] / 100)

with col2:
    st.metric(
        "Time-in-Range",
        f"{health_data['range_score']:.0f}/100",
        help="% of time in optimal range"
    )
    st.progress(health_data['range_score'] / 100)

with col3:
    st.metric(
        "Trend Analysis",
        f"{health_data['trend_score']:.0f}/100",
        help="Temperature drift over time"
    )
    st.progress(health_data['trend_score'] / 100)

with col4:
    st.metric(
        "Critical Events",
        f"{health_data['critical_score']:.0f}/100",
        help="Avoidance of critical temperatures"
    )
    st.progress(health_data['critical_score'] / 100)

# Health factors chart
st.subheader("Health Score Factors")

factors_df = pd.DataFrame({
    'Factor': ['Stability (30%)', 'Time-in-Range (35%)', 'Trend (20%)', 'Critical Events (15%)'],
    'Score': [
        health_data['stability_score'],
        health_data['range_score'],
        health_data['trend_score'],
        health_data['critical_score']
    ]
})

fig = px.bar(
    factors_df,
    x='Score',
    y='Factor',
    orientation='h',
    title="Health Score Components",
    color='Score',
    color_continuous_scale=['red', 'orange', 'yellow', 'green'],
    range_color=[0, 100]
)
fig.update_layout(xaxis_range=[0, 100])
st.plotly_chart(fig, use_container_width=True)

# Recovery time analysis
st.subheader("Defrost Recovery Analysis")

defrost_df = detect_defrost_cycles(cabinet_df, is_freezer)
recovery_df = pd.DataFrame()

if len(defrost_df) > 0:
    recovery_df = calculate_recovery_time(cabinet_df, defrost_df, is_freezer)

    if len(recovery_df) > 0:
        avg_recovery = recovery_df['recovery_duration_minutes'].mean()
        max_recovery = recovery_df['recovery_duration_minutes'].max()

        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric("Average Recovery Time", f"{avg_recovery:.1f} min")
        with col2:
            st.metric("Max Recovery Time", f"{max_recovery:.1f} min")
        with col3:
            if avg_recovery > 60:
                st.error("⚠️ Slow Recovery")
            elif avg_recovery > 40:
                st.warning("⚡ Monitor")
            else:
                st.success("✅ Normal")

        with st.expander("View Recovery Trend"):
            recovery_display = recovery_df.copy()
            recovery_display['defrost_start'] = pd.to_datetime(recovery_display['defrost_start'])

            fig = px.scatter(
                recovery_display,
                x='defrost_start',
                y='recovery_duration_minutes',
                title="Defrost Recovery Time Over Time",
                trendline="lowess"
            )
            fig.add_hline(y=40, line_dash="dash", line_color="orange",
                         annotation_text="Warning Threshold")
            fig.add_hline(y=60, line_dash="dash", line_color="red",
                         annotation_text="Critical Threshold")
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No recovery data available.")
else:
    st.info("No defrost cycles detected for this cabinet.")

# Maintenance recommendations
st.subheader("Maintenance Recommendations")

recommendations = []

if health_data['overall_score'] < 60:
    recommendations.append("🔴 **URGENT:** Schedule immediate maintenance inspection")

if health_data['stability_score'] < 70:
    recommendations.append("⚠️ High temperature variance - check door seals and gaskets")

if health_data['temp_drift'] > 1:
    recommendations.append("⚠️ Temperature creeping up - check refrigerant levels")

if health_data['range_score'] < 80:
    recommendations.append("⚠️ Frequently out of optimal range - verify thermostat calibration")

if len(recovery_df) > 0 and recovery_df['recovery_duration_minutes'].mean() > 60:
    recommendations.append("⚠️ Slow defrost recovery - check compressor performance")

if time_range_metrics['critical_pct'] > 5:
    recommendations.append("🔴 Excessive time in critical temperature range - immediate attention required")

if not recommendations:
    st.success("✅ No maintenance issues detected. Equipment is operating normally.")
else:
    for rec in recommendations:
        st.warning(rec)