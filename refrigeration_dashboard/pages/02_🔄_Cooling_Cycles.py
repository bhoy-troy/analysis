"""Cooling Cycles Analysis page"""

import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

# Add parent directory to path to import utils
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from utils.calculations import detect_cooling_cycles

st.title("🔄 Cooling Cycles Analysis")

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
cabinet_df = df[df["cabinet"] == selected_cabinet].copy()

st.header(f"Cooling Cycles: {selected_cabinet}")

with st.spinner("Detecting cooling cycles..."):
    cycles_df = detect_cooling_cycles(cabinet_df)

if len(cycles_df) > 0:
    # Add date and week columns
    cycles_df["date"] = pd.to_datetime(cycles_df["start_time"]).dt.date
    cycles_df["week"] = pd.to_datetime(cycles_df["start_time"]).dt.isocalendar().week

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Total Cycles Detected", len(cycles_df))
    with col2:
        avg_duration = cycles_df["duration_minutes"].mean()
        st.metric("Average Cycle Duration", f"{avg_duration:.1f} min")
    with col3:
        avg_temp_range = cycles_df["temp_range"].mean()
        st.metric("Average Temp Range", f"{avg_temp_range:.2f}°C")

    # Cycles per day
    st.subheader("Cycles per Day")
    cycles_per_day = cycles_df.groupby("date").size().reset_index(name="cycle_count")
    fig = px.bar(cycles_per_day, x="date", y="cycle_count", title="Number of Cooling Cycles per Day")
    fig.update_layout(xaxis_title="Date", yaxis_title="Number of Cycles")
    st.plotly_chart(fig, use_container_width=True)

    # Cycles per week
    st.subheader("Cycles per Week")
    cycles_per_week = cycles_df.groupby("week").size().reset_index(name="cycle_count")
    st.dataframe(cycles_per_week, use_container_width=True)

    # Cycle duration distribution
    st.subheader("Cycle Duration Distribution")
    fig = px.histogram(cycles_df, x="duration_minutes", nbins=30, title="Distribution of Cycle Durations")
    fig.update_layout(xaxis_title="Duration (minutes)", yaxis_title="Count")
    st.plotly_chart(fig, use_container_width=True)

    # Detailed cycle data
    st.subheader("Detailed Cycle Data")
    display_cycles = cycles_df.copy()
    display_cycles["start_time"] = pd.to_datetime(display_cycles["start_time"])
    display_cycles["end_time"] = pd.to_datetime(display_cycles["end_time"])
    st.dataframe(display_cycles, use_container_width=True)

    # Export
    csv = cycles_df.to_csv(index=False)
    st.download_button(
        label="📥 Download Cycles Data", data=csv, file_name=f"{selected_cabinet}_cooling_cycles.csv", mime="text/csv"
    )
else:
    st.warning("No cooling cycles detected. Try adjusting the detection parameters.")
