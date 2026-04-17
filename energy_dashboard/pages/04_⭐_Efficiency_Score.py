import sys
from pathlib import Path

import plotly.graph_objects as go
import streamlit as st

# Add parent directory to path to import utils
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

st.set_page_config(page_title="Efficiency Score", layout="wide")

# ── Session State Validation ──────────────────────────────────────────────────
if "df" not in st.session_state or not st.session_state.get("data_loaded", False):
    st.error("⚠️ No data loaded. Please return to the main page and load data first.")
    st.stop()

# Get variables from session state
df = st.session_state.df

# ── Tab 4: Efficiency Score Heatmap ───────────────────────────────────────────
if "Total kW" in df.columns and "Total kVA" in df.columns and "Average PF" in df.columns:
    st.subheader("📊 Daily Efficiency Score Heatmap")

    st.markdown("""
    Track daily power efficiency based on Power Factor and real vs apparent power usage.
    Higher scores indicate better electrical efficiency.
    """)

    # Work with a copy to avoid modifying original df
    df_eff = df.copy()

    # Add date and time columns
    df_eff["date"] = df_eff["timestamp"].dt.date
    df_eff["day_of_month"] = df_eff["timestamp"].dt.day
    df_eff["month"] = df_eff["timestamp"].dt.strftime("%B %Y")

    # Calculate time difference in hours for energy calculation
    df_eff["time_diff_hours"] = df_eff["timestamp"].diff().dt.total_seconds() / 3600
    df_eff.loc[df_eff["time_diff_hours"] < 0, "time_diff_hours"] = 0
    df_eff.loc[df_eff["time_diff_hours"] > 1, "time_diff_hours"] = 0

    # Calculate energy consumption (kWh)
    df_eff["kWh_interval"] = df_eff["Total kW"] * df_eff["time_diff_hours"]

    # Group by day and calculate daily metrics
    daily_stats = (
        df_eff.groupby("date")
        .agg(
            {
                "Average PF": "mean",
                "Total kW": "mean",
                "Total kVA": "mean",
                "kWh_interval": "sum",
                "day_of_month": "first",
                "month": "first",
            }
        )
        .reset_index()
    )

    # Calculate efficiency score (0-100)
    # Based on: Power Factor (60%), kW/kVA ratio (40%)
    daily_stats["kW_kVA_ratio"] = daily_stats["Total kW"] / daily_stats["Total kVA"].replace(0, 1)
    daily_stats["efficiency_score"] = ((daily_stats["Average PF"] * 60) + (daily_stats["kW_kVA_ratio"] * 40)).clip(
        0, 100
    )

    # Round kWh for display
    daily_stats["kWh_display"] = daily_stats["kWh_interval"].round(1)

    if len(daily_stats) > 0:
        st.info(f"📅 Analyzing {len(daily_stats)} days of efficiency data")

        # Create heatmap for each month
        for month in daily_stats["month"].unique():
            month_data = daily_stats[daily_stats["month"] == month].copy().sort_values("day_of_month")

            st.markdown(f"### {month}")

            # Create heatmap with white-to-red color scale
            fig_eff = go.Figure(
                data=go.Heatmap(
                    x=month_data["day_of_month"],
                    y=["Efficiency Score"] * len(month_data),
                    z=month_data["efficiency_score"],
                    text=month_data.apply(
                        lambda row: f"Day {row['day_of_month']}<br>"
                        f"{row['kWh_display']:.1f} kWh<br>"
                        f"Score: {row['efficiency_score']:.1f}%<br>"
                        f"PF: {row['Average PF']:.3f}",
                        axis=1,
                    ),
                    hovertemplate="%{text}<extra></extra>",
                    texttemplate="Day %{x}<br>%{z:.0f}%",
                    textfont={"size": 9, "color": "black"},
                    colorscale=[
                        [0.0, "rgb(178, 34, 34)"],  # Dark red (low/bad)
                        [0.5, "rgb(255, 160, 122)"],  # Light red (medium)
                        [1.0, "rgb(255, 255, 255)"],  # White (high/good)
                    ],
                    reversescale=True,  # Reverse so white = max (good)
                    zmin=60,
                    zmax=100,
                    colorbar={
                        "title": "Efficiency<br>Score (%)",
                        "tickmode": "linear",
                        "tick0": 60,
                        "dtick": 10,
                    },
                )
            )

            fig_eff.update_layout(
                xaxis={"title": "Day of Month", "dtick": 1, "range": [0.5, month_data["day_of_month"].max() + 0.5]},
                yaxis={"title": "", "showticklabels": False},
                height=200,
                margin={"t": 40, "b": 40},
            )

            st.plotly_chart(fig_eff, use_container_width=True)

            # Show statistics
            col1, col2, col3, col4 = st.columns(4)
            avg_score = month_data["efficiency_score"].mean()
            total_kwh = month_data["kWh_interval"].sum()
            avg_pf = month_data["Average PF"].mean()
            best_day_idx = month_data["efficiency_score"].idxmax()
            best_day = month_data.loc[best_day_idx, "day_of_month"]
            best_score = month_data.loc[best_day_idx, "efficiency_score"]

            col1.metric("Avg Efficiency Score", f"{avg_score:.1f}%")
            col2.metric("Total Energy", f"{total_kwh:,.1f} kWh")
            col3.metric("Avg Power Factor", f"{avg_pf:.3f}")
            col4.metric("Best Day", f"Day {int(best_day)}", delta=f"{best_score:.1f}%")

            # Show distribution chart
            st.markdown("#### Score Distribution")

            fig_dist = go.Figure()

            fig_dist.add_trace(
                go.Bar(
                    x=month_data["day_of_month"],
                    y=month_data["efficiency_score"],
                    marker_color=month_data["efficiency_score"],
                    marker_colorscale=[
                        [0.0, "rgb(178, 34, 34)"],
                        [0.5, "rgb(255, 160, 122)"],
                        [1.0, "rgb(255, 255, 255)"],
                    ],
                    marker_cmin=60,
                    marker_cmax=100,
                    marker_reversescale=True,
                    text=month_data["efficiency_score"].round(1),
                    textposition="outside",
                    showlegend=False,
                )
            )

            fig_dist.update_layout(
                xaxis={"title": "Day of Month", "dtick": 1},
                yaxis={"title": "Efficiency Score (%)", "range": [0, 105]},
                height=300,
            )

            st.plotly_chart(fig_dist, use_container_width=True)

            st.markdown("---")

    else:
        st.warning("⚠️ No data available to calculate efficiency scores")

    # Efficiency score explanation
    with st.expander("ℹ️ How is efficiency score calculated?"):
        st.markdown("""
        **Efficiency Score Calculation Formula:**

        ```
        Efficiency Score = (Power Factor × 60) + (kW/kVA Ratio × 40)
        ```

        Where:
        - **Power Factor** = Average PF for the day (0 to 1.0)
        - **kW/kVA Ratio** = Average Real Power ÷ Average Apparent Power for the day

        **Example Calculation:**
        ```
        Day 15:
          • Average Power Factor = 0.97
          • Average kW = 245.3
          • Average kVA = 252.9
          • kW/kVA Ratio = 245.3 ÷ 252.9 = 0.97

        Efficiency Score = (0.97 × 60) + (0.97 × 40)
                        = 58.2 + 38.8
                        = 97.0%
        ```

        **Component Weights:**

        1. **Power Factor (60% weight)**: Measures how effectively electrical power is converted into useful work
           - Target: ≥0.90 (90%)
           - Higher is better
           - Represents the ratio of real power to apparent power

        2. **kW/kVA Ratio (40% weight)**: Real power vs apparent power ratio
           - Indicates how much of the supplied power is actually used
           - Should be close to Power Factor for balanced systems
           - Higher is better

        **Color Coding:**
        - ⚪ White (90-100%): Excellent efficiency
        - 🟠 Light Red (80-90%): Good efficiency
        - 🔴 Red (70-80%): Fair efficiency
        - 🔴 Dark Red (<70%): Poor efficiency - investigate power quality issues

        **Score Ranges:**
        - **90-100%**: Excellent - optimal electrical efficiency, minimal reactive power
        - **80-90%**: Good - minor improvements possible, consider power factor optimization
        - **70-80%**: Fair - power factor correction recommended, potential savings available
        - **Below 70%**: Poor - urgent attention needed, significant reactive power issues

        **What affects your score:**
        - Inductive loads (motors, transformers) without correction lower Power Factor
        - Unbalanced loads reduce efficiency
        - Harmonic distortion from non-linear loads
        - Oversized equipment running at low load
        """)

        # Show calculation for a sample day if data exists
        if len(daily_stats) > 0:
            st.markdown("---")
            st.markdown("**Sample Calculation from Your Data:**")

            # Get a random day from the middle
            sample_idx = len(daily_stats) // 2
            sample_day = daily_stats.iloc[sample_idx]

            pf = sample_day["Average PF"]
            kw = sample_day["Total kW"]
            kva = sample_day["Total kVA"]
            ratio = sample_day["kW_kVA_ratio"]
            score = sample_day["efficiency_score"]

            st.code(
                f"""
Day {int(sample_day['day_of_month'])} ({sample_day['date']}):
  • Average Power Factor = {pf:.4f}
  • Average kW = {kw:.2f}
  • Average kVA = {kva:.2f}
  • kW/kVA Ratio = {kw:.2f} ÷ {kva:.2f} = {ratio:.4f}

Efficiency Score = ({pf:.4f} × 60) + ({ratio:.4f} × 40)
                = {pf*60:.2f} + {ratio*40:.2f}
                = {score:.2f}%
                """,
                language="text",
            )
else:
    st.info("Power Factor or kW/kVA data not available for efficiency calculation")
