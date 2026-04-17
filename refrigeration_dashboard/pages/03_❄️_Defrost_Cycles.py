"""Defrost Cycles Analysis page"""

import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

# Add parent directory to path to import utils
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from utils.calculations import calculate_recovery_time, detect_defrost_cycles

st.title("❄️ Defrost Cycles Analysis")

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

st.header(f"Defrost Cycles: {selected_cabinet}")

with st.spinner("Detecting defrost cycles..."):
    defrost_df = detect_defrost_cycles(cabinet_df, is_freezer=is_freezer)

if len(defrost_df) > 0:
    # Add date column
    defrost_df["date"] = pd.to_datetime(defrost_df["start_time"]).dt.date
    defrost_df["week"] = pd.to_datetime(defrost_df["start_time"]).dt.isocalendar().week

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Total Defrost Cycles", len(defrost_df))
    with col2:
        avg_defrost_duration = defrost_df["duration_minutes"].mean()
        st.metric("Average Defrost Duration", f"{avg_defrost_duration:.1f} min")
    with col3:
        avg_temp_rise = defrost_df["temp_rise"].mean()
        st.metric("Average Temp Rise", f"{avg_temp_rise:.2f}°C")

    # Defrost cycles per day
    st.subheader("Defrost Cycles per Day")
    defrost_per_day = defrost_df.groupby("date").size().reset_index(name="defrost_count")
    fig = px.bar(defrost_per_day, x="date", y="defrost_count", title="Number of Defrost Cycles per Day")
    fig.update_layout(xaxis_title="Date", yaxis_title="Number of Defrost Cycles")
    st.plotly_chart(fig, use_container_width=True)

    # Defrost cycles per week
    st.subheader("Defrost Cycles per Week")
    defrost_per_week = defrost_df.groupby("week").size().reset_index(name="defrost_count")
    st.dataframe(defrost_per_week, use_container_width=True)

    # Defrost duration over time
    st.subheader("Defrost Duration Over Time")
    defrost_display = defrost_df.copy()
    defrost_display["start_time"] = pd.to_datetime(defrost_display["start_time"])
    fig = px.scatter(
        defrost_display,
        x="start_time",
        y="duration_minutes",
        color="max_temp",
        title="Defrost Duration and Peak Temperature Over Time",
    )
    fig.update_layout(xaxis_title="Time", yaxis_title="Duration (minutes)")
    st.plotly_chart(fig, use_container_width=True)

    # Recovery Time Analysis
    st.subheader("Defrost Recovery Analysis")
    recovery_df = calculate_recovery_time(cabinet_df, defrost_df, is_freezer)

    if len(recovery_df) > 0:
        col1, col2 = st.columns(2)

        with col1:
            avg_recovery = recovery_df["recovery_duration_minutes"].mean()
            st.metric("Average Recovery Time", f"{avg_recovery:.1f} min")

        with col2:
            max_recovery = recovery_df["recovery_duration_minutes"].max()
            st.metric("Max Recovery Time", f"{max_recovery:.1f} min")

        # Recovery time trend
        recovery_display = recovery_df.copy()
        recovery_display["defrost_start"] = pd.to_datetime(recovery_display["defrost_start"])

        fig = px.scatter(
            recovery_display,
            x="defrost_start",
            y="recovery_duration_minutes",
            title="Defrost Recovery Time Over Time",
            trendline="lowess",
        )
        fig.add_hline(y=40, line_dash="dash", line_color="orange", annotation_text="Warning")
        fig.add_hline(y=60, line_dash="dash", line_color="red", annotation_text="Critical")
        st.plotly_chart(fig, use_container_width=True)

        with st.expander("View Detailed Recovery Data"):
            st.dataframe(recovery_display, use_container_width=True)
    else:
        st.info("No recovery data available - defrost cycles may not have completed.")

    # Detailed defrost data
    st.subheader("Detailed Defrost Cycle Data")
    display_defrost = defrost_df.copy()
    display_defrost["start_time"] = pd.to_datetime(display_defrost["start_time"])
    display_defrost["end_time"] = pd.to_datetime(display_defrost["end_time"])
    st.dataframe(display_defrost, use_container_width=True)

    # Export
    csv = defrost_df.to_csv(index=False)
    st.download_button(
        label="📥 Download Defrost Data", data=csv, file_name=f"{selected_cabinet}_defrost_cycles.csv", mime="text/csv"
    )
else:
    st.info(f"No defrost cycles detected for {selected_cabinet}. This may be normal for some cabinet types.")
