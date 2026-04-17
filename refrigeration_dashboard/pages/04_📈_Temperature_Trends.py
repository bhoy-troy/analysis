"""Temperature Trends page"""

import plotly.graph_objects as go
import streamlit as st

st.title("📈 Temperature Trends")

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

st.header(f"Temperature Trends: {selected_cabinet}")

# Date range selector
date_range = st.date_input(
    "Select Date Range",
    value=(cabinet_df["date"].min(), cabinet_df["date"].max()),
    min_value=cabinet_df["date"].min(),
    max_value=cabinet_df["date"].max(),
)

if len(date_range) == 2:
    filtered_df = cabinet_df[(cabinet_df["date"] >= date_range[0]) & (cabinet_df["date"] <= date_range[1])]

    st.subheader("Temperature Over Time")
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=filtered_df["timestamp"],
            y=filtered_df["temperature_celsius"],
            mode="lines",
            name="Temperature",
            line={"color": "blue", "width": 1},
        )
    )

    fig.update_layout(
        title=f"Temperature Timeline - {selected_cabinet}",
        xaxis_title="Time",
        yaxis_title="Temperature (°C)",
        hovermode="x unified",
    )
    st.plotly_chart(fig, use_container_width=True)

    # Hourly averages
    st.subheader("Hourly Average Temperature Pattern")
    filtered_df["hour"] = filtered_df["timestamp"].dt.hour
    hourly_avg = filtered_df.groupby("hour")["temperature_celsius"].agg(["mean", "std"]).reset_index()

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=hourly_avg["hour"],
            y=hourly_avg["mean"],
            mode="lines+markers",
            name="Average",
            line={"color": "green", "width": 2},
        )
    )
    fig.add_trace(
        go.Scatter(
            x=hourly_avg["hour"],
            y=hourly_avg["mean"] + hourly_avg["std"],
            mode="lines",
            line={"width": 0},
            showlegend=False,
        )
    )
    fig.add_trace(
        go.Scatter(
            x=hourly_avg["hour"],
            y=hourly_avg["mean"] - hourly_avg["std"],
            mode="lines",
            line={"width": 0},
            fillcolor="rgba(0,100,80,0.2)",
            fill="tonexty",
            name="±1 Std Dev",
        )
    )

    fig.update_layout(
        title="Average Temperature by Hour of Day", xaxis_title="Hour of Day", yaxis_title="Temperature (°C)"
    )
    st.plotly_chart(fig, use_container_width=True)

    # Statistics for selected period
    st.subheader("Period Statistics")
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Average", f"{filtered_df['temperature_celsius'].mean():.2f}°C")
    with col2:
        st.metric("Min", f"{filtered_df['temperature_celsius'].min():.2f}°C")
    with col3:
        st.metric("Max", f"{filtered_df['temperature_celsius'].max():.2f}°C")
    with col4:
        st.metric("Std Dev", f"{filtered_df['temperature_celsius'].std():.2f}°C")
