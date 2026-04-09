"""Equipment Health Score page - Predictive Maintenance"""

import sys

import pandas as pd
import plotly.express as px
import streamlit as st

sys.path.append("..")
from utils.calculations import (
    calculate_health_score,
    calculate_recovery_time,
    calculate_time_in_range,
    detect_defrost_cycles,
    get_health_status,
)

st.title("🏥 Equipment Health Score")
st.markdown("**Predictive Maintenance Analysis**")

st.info("""
📊 **What is the Health Score?**

The Health Score is a comprehensive 0-100 rating that evaluates equipment performance and predicts maintenance needs.
It combines four factors: temperature stability, time in optimal range, temperature drift trends, and critical event avoidance.

**Score Guide:** 🟢 90+ Excellent | 🟡 75-89 Good | 🟠 60-74 Fair | 🔴 <60 Poor (Maintenance Required)
""")

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

st.header(f"Health Score: {selected_cabinet}")

# Calculate health score
health_data = calculate_health_score(cabinet_df, is_freezer)
status, emoji, color = get_health_status(health_data["overall_score"])
time_range_metrics = calculate_time_in_range(cabinet_df, is_freezer)

# Overall health display
col1, col2, col3 = st.columns([2, 1, 1])

with col1:
    st.markdown(f"### {emoji} Overall Health: {status}")
    st.progress(health_data["overall_score"] / 100)
    st.metric("Health Score", f"{health_data['overall_score']:.1f}/100")

with col2:
    st.metric("Temp Stability (σ)", f"{health_data['temp_std']:.2f}°C")
    st.metric("Temp Drift", f"{health_data['temp_drift']:+.2f}°C")

with col3:
    if health_data["overall_score"] < 60:
        st.error("⚠️ Maintenance Required")
    elif health_data["overall_score"] < 75:
        st.warning("⚡ Monitor Closely")
    else:
        st.success("✅ Healthy")

# Component scores
st.subheader("Component Health Breakdown")

# Explanation section
with st.expander("ℹ️ What do these metrics mean?"):
    st.markdown("""
    The Health Score is calculated from four key components, each measuring different aspects of equipment performance:

    **🎯 Stability (30% of score)**
    - Measures temperature consistency using standard deviation (σ)
    - Lower variation = better stability = higher score
    - **Why it matters:** Consistent temperatures indicate reliable compressor performance and good insulation
    - **Warning signs:** High variation suggests door seal issues, refrigerant problems, or failing thermostats
    - **Good:** σ < 1°C | **Fair:** σ < 2°C | **Poor:** σ > 3°C

    **📊 Time-in-Range (35% of score)**
    - Percentage of time spent in the optimal temperature range
    - Directly reflects food safety compliance
    - **Why it matters:** Food safety regulations require specific temperature ranges to prevent bacterial growth
    - **Warning signs:** Low percentage indicates the unit struggles to maintain safe temperatures
    - **Target:** >95% for optimal food safety compliance

    **📈 Trend Analysis (20% of score)**
    - Detects gradual temperature drift over time
    - Compares first half vs. second half of data period
    - **Why it matters:** Gradual warming indicates refrigerant loss or compressor degradation
    - **Warning signs:** Temperature creeping up >1°C suggests equipment aging or refrigerant leak
    - **Action:** Warming trend requires immediate inspection to prevent failure

    **⚠️ Critical Events (15% of score)**
    - Penalizes time spent in food-unsafe temperature zones
    - Critical zone: Above -10°C for freezers, above 8°C for chillers
    - **Why it matters:** Critical temperatures risk food spoilage and health violations
    - **Warning signs:** Frequent critical events indicate serious equipment problems
    - **Compliance:** Should be <1% for proper operation, <5% acceptable with monitoring

    ---
    **Weighted Calculation:** Each component is scored 0-100, then combined using the weights above to produce the final Health Score.
    """)

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("Stability", f"{health_data['stability_score']:.0f}/100", help="Temperature consistency (σ)")
    st.progress(health_data["stability_score"] / 100)
    st.caption(f"σ = {health_data['temp_std']:.2f}°C")

with col2:
    st.metric("Time-in-Range", f"{health_data['range_score']:.0f}/100", help="% in optimal range")
    st.progress(health_data["range_score"] / 100)
    st.caption(f"{health_data['range_score']:.1f}% optimal")

with col3:
    st.metric("Trend Analysis", f"{health_data['trend_score']:.0f}/100", help="Temperature drift")
    st.progress(health_data["trend_score"] / 100)
    st.caption(f"{health_data['temp_drift']:+.2f}°C drift")

with col4:
    st.metric("Critical Events", f"{health_data['critical_score']:.0f}/100", help="Avoid critical temps")
    st.progress(health_data["critical_score"] / 100)
    st.caption(f"{time_range_metrics['critical_pct']:.1f}% critical")

# Health factors chart
st.subheader("Health Score Factors")

factors_df = pd.DataFrame(
    {
        "Factor": ["Stability (30%)", "Time-in-Range (35%)", "Trend (20%)", "Critical Events (15%)"],
        "Score": [
            health_data["stability_score"],
            health_data["range_score"],
            health_data["trend_score"],
            health_data["critical_score"],
        ],
    }
)

fig = px.bar(
    factors_df,
    x="Score",
    y="Factor",
    orientation="h",
    title="Health Score Components",
    color="Score",
    color_continuous_scale=["red", "orange", "yellow", "green"],
    range_color=[0, 100],
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
        avg_recovery = recovery_df["recovery_duration_minutes"].mean()
        max_recovery = recovery_df["recovery_duration_minutes"].max()

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
            recovery_display["defrost_start"] = pd.to_datetime(recovery_display["defrost_start"])

            fig = px.scatter(
                recovery_display,
                x="defrost_start",
                y="recovery_duration_minutes",
                title="Defrost Recovery Time Over Time",
                trendline="lowess",
            )
            fig.add_hline(y=40, line_dash="dash", line_color="orange", annotation_text="Warning Threshold")
            fig.add_hline(y=60, line_dash="dash", line_color="red", annotation_text="Critical Threshold")
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No recovery data available.")
else:
    st.info("No defrost cycles detected for this cabinet.")

# Maintenance recommendations
st.subheader("Maintenance Recommendations")

recommendations = []

if health_data["overall_score"] < 60:
    recommendations.append("🔴 **URGENT:** Schedule immediate maintenance inspection")

if health_data["stability_score"] < 70:
    recommendations.append("⚠️ High temperature variance - check door seals and gaskets")

if health_data["temp_drift"] > 1:
    recommendations.append("⚠️ Temperature creeping up - check refrigerant levels")

if health_data["range_score"] < 80:
    recommendations.append("⚠️ Frequently out of optimal range - verify thermostat calibration")

if len(recovery_df) > 0 and recovery_df["recovery_duration_minutes"].mean() > 60:
    recommendations.append("⚠️ Slow defrost recovery - check compressor performance")

if time_range_metrics["critical_pct"] > 5:
    recommendations.append("🔴 Excessive time in critical temperature range - immediate attention required")

if not recommendations:
    st.success("✅ No maintenance issues detected. Equipment is operating normally.")
else:
    for rec in recommendations:
        st.warning(rec)

# Quick Reference Guide
st.markdown("---")
with st.expander("📖 Quick Reference Guide"):
    st.markdown("""
    ### Interpreting Your Health Score

    | Score Range | Status | Action Required |
    |-------------|--------|----------------|
    | 90-100 | 🟢 **Excellent** | Continue routine monitoring |
    | 75-89  | 🟡 **Good** | Schedule preventive maintenance |
    | 60-74  | 🟠 **Fair** | Increase monitoring frequency, plan repairs |
    | 0-59   | 🔴 **Poor** | **Immediate inspection required** |

    ### Common Issues and Causes

    **Low Stability Score (<70)**
    - Door seals degraded or damaged
    - Frequent door openings
    - Thermostat malfunction
    - Refrigerant charge issues

    **Low Time-in-Range Score (<80)**
    - Undersized or overloaded unit
    - Compressor wear
    - Dirty condenser coils
    - Incorrect thermostat settings

    **Low Trend Score (<70)**
    - Refrigerant leak (gradual loss)
    - Compressor efficiency declining
    - Insulation degradation
    - Failing expansion valve

    **Low Critical Events Score (<70)**
    - Compressor failure imminent
    - Severe refrigerant loss
    - Power supply issues
    - Defrost system malfunction

    ### Preventive Maintenance Schedule

    **Monthly:**
    - Clean condenser coils
    - Check door seals
    - Verify temperature accuracy

    **Quarterly:**
    - Inspect refrigerant lines
    - Test defrost system
    - Check electrical connections

    **Annually:**
    - Professional refrigerant charge check
    - Compressor performance test
    - Full system inspection
    """)
