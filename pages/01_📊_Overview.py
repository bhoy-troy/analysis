"""Overview page - Temperature distribution and daily statistics"""

import plotly.express as px
import streamlit as st

st.title("📊 Cabinet Overview")

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

st.header(f"Overview: {selected_cabinet}")

# Summary metrics
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("Total Readings", f"{len(cabinet_df):,}")
with col2:
    avg_temp = cabinet_df["temperature_celsius"].mean()
    st.metric("Average Temperature", f"{avg_temp:.2f}°C")
with col3:
    min_temp = cabinet_df["temperature_celsius"].min()
    st.metric("Min Temperature", f"{min_temp:.2f}°C")
with col4:
    max_temp = cabinet_df["temperature_celsius"].max()
    st.metric("Max Temperature", f"{max_temp:.2f}°C")

# Temperature distribution
st.subheader("Temperature Distribution")
fig = px.histogram(
    cabinet_df, x="temperature_celsius", nbins=50, title=f"Temperature Distribution - {selected_cabinet}"
)
fig.update_layout(xaxis_title="Temperature (°C)", yaxis_title="Count")
st.plotly_chart(fig, use_container_width=True)

# Daily temperature summary
st.subheader("Daily Statistics")
daily_stats = cabinet_df.groupby("date")["temperature_celsius"].agg(["count", "mean", "min", "max", "std"]).round(2)
daily_stats.columns = ["Readings", "Avg Temp", "Min Temp", "Max Temp", "Std Dev"]
st.dataframe(daily_stats, use_container_width=True)

# Download daily stats
csv = daily_stats.to_csv()
st.download_button(
    label="📥 Download Daily Statistics", data=csv, file_name=f"{selected_cabinet}_daily_stats.csv", mime="text/csv"
)
