import sys
from pathlib import Path

import plotly.graph_objects as go
import streamlit as st

# Add parent directory to path to import utils
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from utils.tariffs import INDUSTRIAL_LEU_TARIFF

st.set_page_config(page_title="Load Analysis", layout="wide")

# ── Session State Validation ──────────────────────────────────────────────────
if "df" not in st.session_state or not st.session_state.get("data_loaded", False):
    st.error("⚠️ No data loaded. Please return to the main page and load data first.")
    st.stop()

# Get variables from session state
df = st.session_state.df

# ── Tab 3: Load Profile Analysis ─────────────────────────────────────────────
if "Total kW" in df.columns:
    st.subheader("⚡ Daily Load Profile Analysis")

    st.markdown("""
    Understand your energy consumption patterns throughout the day.
    This helps identify opportunities for load shifting and cost savings.
    """)

    # Add time-based columns
    df_profile = df.copy()
    df_profile["hour"] = df_profile["timestamp"].dt.hour
    df_profile["day_of_week"] = df_profile["timestamp"].dt.dayofweek
    df_profile["day_name"] = df_profile["timestamp"].dt.day_name()
    df_profile["is_weekend"] = df_profile["day_of_week"].isin([5, 6])

    # 1. Average Hourly Load Profile (24-hour pattern)
    st.markdown("### 📈 24-Hour Load Profile")

    hourly_avg = df_profile.groupby("hour")["Total kW"].agg(["mean", "min", "max"]).reset_index()

    fig_hourly = go.Figure()

    # Add shaded area for min-max range
    fig_hourly.add_trace(
        go.Scatter(
            x=hourly_avg["hour"],
            y=hourly_avg["max"],
            fill=None,
            mode="lines",
            line={"color": "rgba(59, 130, 246, 0.1)"},
            showlegend=False,
            hoverinfo="skip",
        )
    )

    fig_hourly.add_trace(
        go.Scatter(
            x=hourly_avg["hour"],
            y=hourly_avg["min"],
            fill="tonexty",
            mode="lines",
            line={"color": "rgba(59, 130, 246, 0.1)"},
            fillcolor="rgba(59, 130, 246, 0.2)",
            name="Min-Max Range",
        )
    )

    # Average line
    fig_hourly.add_trace(
        go.Scatter(
            x=hourly_avg["hour"],
            y=hourly_avg["mean"],
            mode="lines+markers",
            name="Average Load",
            line={"color": "#3B82F6", "width": 3},
            marker={"size": 6},
        )
    )

    # Add peak/off-peak background shading
    # Day hours: 8-23, Night hours: 23-8
    fig_hourly.add_vrect(
        x0=8,
        x1=23,
        fillcolor="rgba(255, 200, 0, 0.1)",
        layer="below",
        line_width=0,
        annotation_text="Day Rate (08:00-23:00)",
        annotation_position="top left",
    )

    fig_hourly.add_vrect(
        x0=23,
        x1=24,
        fillcolor="rgba(59, 130, 246, 0.1)",
        layer="below",
        line_width=0,
    )

    fig_hourly.add_vrect(
        x0=0,
        x1=8,
        fillcolor="rgba(59, 130, 246, 0.1)",
        layer="below",
        line_width=0,
        annotation_text="Night Rate (23:00-08:00)",
        annotation_position="top right",
    )

    fig_hourly.update_layout(
        xaxis={
            "title": "Hour of Day",
            "dtick": 1,
            "range": [-0.5, 23.5],
        },
        yaxis={"title": "Power (kW)"},
        hovermode="x unified",
        height=400,
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "xanchor": "center", "x": 0.5},
    )

    st.plotly_chart(fig_hourly, use_container_width=True)

    # Show key insights
    peak_hour = hourly_avg.loc[hourly_avg["mean"].idxmax(), "hour"]
    peak_load = hourly_avg["mean"].max()
    min_hour = hourly_avg.loc[hourly_avg["mean"].idxmin(), "hour"]
    min_load = hourly_avg["mean"].min()

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Peak Hour", f"{int(peak_hour):02d}:00")
    col2.metric("Peak Load", f"{peak_load:.1f} kW")
    col3.metric("Minimum Hour", f"{int(min_hour):02d}:00")
    col4.metric("Minimum Load", f"{min_load:.1f} kW")

    # 2. Weekday vs Weekend Comparison
    st.markdown("---")
    st.markdown("### 📊 Weekday vs Weekend Pattern")

    weekday_profile = df_profile[~df_profile["is_weekend"]].groupby("hour")["Total kW"].mean().reset_index()
    weekend_profile = df_profile[df_profile["is_weekend"]].groupby("hour")["Total kW"].mean().reset_index()

    fig_week = go.Figure()

    fig_week.add_trace(
        go.Scatter(
            x=weekday_profile["hour"],
            y=weekday_profile["Total kW"],
            mode="lines+markers",
            name="Weekday Average",
            line={"color": "#3B82F6", "width": 3},
            marker={"size": 6},
        )
    )

    if len(weekend_profile) > 0:
        fig_week.add_trace(
            go.Scatter(
                x=weekend_profile["hour"],
                y=weekend_profile["Total kW"],
                mode="lines+markers",
                name="Weekend Average",
                line={"color": "#10B981", "width": 3, "dash": "dash"},
                marker={"size": 6},
            )
        )

    fig_week.update_layout(
        xaxis={"title": "Hour of Day", "dtick": 1},
        yaxis={"title": "Power (kW)"},
        hovermode="x unified",
        height=400,
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "xanchor": "center", "x": 0.5},
    )

    st.plotly_chart(fig_week, use_container_width=True)

    # Comparison metrics
    weekday_avg = df_profile[~df_profile["is_weekend"]]["Total kW"].mean()
    weekend_avg = df_profile[df_profile["is_weekend"]]["Total kW"].mean()

    col1, col2, col3 = st.columns(3)
    col1.metric("Avg Weekday Load", f"{weekday_avg:.1f} kW")
    col2.metric("Avg Weekend Load", f"{weekend_avg:.1f} kW")
    if weekend_avg > 0:
        diff_pct = ((weekday_avg - weekend_avg) / weekend_avg) * 100
        col3.metric("Weekday vs Weekend", f"{diff_pct:+.1f}%")

    # 3. Day-of-Week Breakdown
    st.markdown("---")
    st.markdown("### 📅 Load by Day of Week")

    day_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    daily_avg = df_profile.groupby("day_name")["Total kW"].agg(["mean", "max"]).reindex(day_order).reset_index()

    fig_daily = go.Figure()

    fig_daily.add_trace(
        go.Bar(
            x=daily_avg["day_name"],
            y=daily_avg["mean"],
            name="Average Load",
            marker_color=[
                "#3B82F6" if day not in ["Saturday", "Sunday"] else "#10B981" for day in daily_avg["day_name"]
            ],
            text=daily_avg["mean"].round(1),
            textposition="outside",
        )
    )

    fig_daily.update_layout(
        xaxis={"title": "Day of Week"},
        yaxis={"title": "Average Power (kW)"},
        height=400,
    )

    st.plotly_chart(fig_daily, use_container_width=True)

    # 4. Load Distribution Throughout the Day
    st.markdown("---")
    st.markdown("### 🕐 Load Distribution by Time Period")

    # Define time periods
    def get_time_period(hour):
        if 0 <= hour < 6:
            return "Night (00:00-06:00)"
        elif 6 <= hour < 9:
            return "Morning (06:00-09:00)"
        elif 9 <= hour < 12:
            return "Mid-Morning (09:00-12:00)"
        elif 12 <= hour < 14:
            return "Lunch (12:00-14:00)"
        elif 14 <= hour < 18:
            return "Afternoon (14:00-18:00)"
        elif 18 <= hour < 22:
            return "Evening (18:00-22:00)"
        else:
            return "Late Night (22:00-24:00)"

    df_profile["time_period"] = df_profile["hour"].apply(get_time_period)

    period_order = [
        "Night (00:00-06:00)",
        "Morning (06:00-09:00)",
        "Mid-Morning (09:00-12:00)",
        "Lunch (12:00-14:00)",
        "Afternoon (14:00-18:00)",
        "Evening (18:00-22:00)",
        "Late Night (22:00-24:00)",
    ]

    period_stats = (
        df_profile.groupby("time_period")["Total kW"].agg(["mean", "max"]).reindex(period_order).reset_index()
    )

    fig_periods = go.Figure()

    fig_periods.add_trace(
        go.Bar(
            x=period_stats["time_period"],
            y=period_stats["mean"],
            name="Average",
            marker_color="#3B82F6",
        )
    )

    fig_periods.add_trace(
        go.Scatter(
            x=period_stats["time_period"],
            y=period_stats["max"],
            name="Peak",
            mode="markers",
            marker={"size": 12, "color": "#EF4444", "symbol": "diamond"},
        )
    )

    fig_periods.update_layout(
        xaxis={"title": "Time Period", "tickangle": -45},
        yaxis={"title": "Power (kW)"},
        height=450,
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "xanchor": "center", "x": 0.5},
    )

    st.plotly_chart(fig_periods, use_container_width=True)

    # Insights
    st.markdown("### 💡 Load Pattern Insights")

    insights = []

    # Check for high off-hours usage
    night_usage = df_profile[df_profile["hour"].isin(range(0, 6))]["Total kW"].mean()
    overall_avg = df_profile["Total kW"].mean()
    if night_usage > overall_avg * 0.5:
        insights.append(
            f"⚠️ Significant night-time usage detected ({night_usage:.1f} kW average from 00:00-06:00). "
            f"This is {(night_usage/overall_avg*100):.1f}% of your average load."
        )

    # Check for consistent load
    load_variability = hourly_avg["mean"].std()
    if load_variability < overall_avg * 0.2:
        insights.append("✅ Your load is relatively consistent throughout the day, indicating steady operations.")
    else:
        insights.append(
            f"📊 Your load varies significantly throughout the day (std dev: {load_variability:.1f} kW). "
            "Consider load shifting opportunities during off-peak hours."
        )

    # Peak vs off-peak comparison
    day_hours_avg = df_profile[df_profile["hour"].isin(range(8, 23))]["Total kW"].mean()
    night_hours_avg = df_profile[~df_profile["hour"].isin(range(8, 23))]["Total kW"].mean()

    day_savings_rate = INDUSTRIAL_LEU_TARIFF["duos_day_rate"]  # type: ignore[assignment]
    night_savings_rate = INDUSTRIAL_LEU_TARIFF["duos_night_rate"]  # type: ignore[assignment]
    potential_savings = (day_savings_rate - night_savings_rate) * 100  # type: ignore[operator]

    if day_hours_avg > night_hours_avg * 1.2:
        insights.append(
            f"💰 Shifting load from day (€{day_savings_rate:.5f}/kWh) to night (€{night_savings_rate:.5f}/kWh) "
            f"could save €{potential_savings:.2f} per 100 kWh shifted on DUoS charges alone."
        )

    for insight in insights:
        st.info(insight)

else:
    st.info("Total kW data not available.")
