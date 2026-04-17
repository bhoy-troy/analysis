"""Multi-Cabinet Comparison page - Fleet Analysis"""

import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

# Add parent directory to path to import utils
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from utils.calculations import (
    calculate_health_score,
    calculate_time_in_range,
    detect_cooling_cycles,
    detect_defrost_cycles,
)

st.title("🔍 Multi-Cabinet Comparison")
st.markdown("**Identify Problem Units**")

# Get data from session state
if "df" not in st.session_state or st.session_state.df.empty:
    st.warning("⚠️ No data loaded. Please return to the main page and load data first.")
    st.info("1. Select a premises\n2. Choose date range\n3. Click 'Load Data'")
    st.stop()

df = st.session_state.df

# Cabinet selection for comparison
st.subheader("Select Cabinets to Compare")

# Filter by cabinet type
compare_type = st.radio(
    "Cabinet Type for Comparison", ["Freezers Only", "Chillers Only", "All Cabinets"], horizontal=True
)

if compare_type == "Freezers Only":
    compare_cabinets = sorted(df[df["cabinet"].str.contains("Freezer", case=False, na=False)]["cabinet"].unique())
elif compare_type == "Chillers Only":
    compare_cabinets = sorted(df[df["cabinet"].str.contains("Chiller", case=False, na=False)]["cabinet"].unique())
else:
    compare_cabinets = sorted(df["cabinet"].unique())

selected_for_comparison = st.multiselect(
    "Select 2-10 cabinets to compare", compare_cabinets, default=compare_cabinets[: min(5, len(compare_cabinets))]
)

if len(selected_for_comparison) >= 2:
    # Calculate metrics for all selected cabinets
    comparison_data = []

    with st.spinner(f"Calculating metrics for {len(selected_for_comparison)} cabinets..."):
        for cabinet in selected_for_comparison:
            cab_data = df[df["cabinet"] == cabinet].copy()
            cab_is_freezer = "freezer" in cabinet.lower()

            # Calculate all metrics
            health = calculate_health_score(cab_data, cab_is_freezer)
            time_range = calculate_time_in_range(cab_data, cab_is_freezer)
            defrost = detect_defrost_cycles(cab_data, cab_is_freezer)
            cycles = detect_cooling_cycles(cab_data)

            comparison_data.append(
                {
                    "Cabinet": cabinet,
                    "Health Score": health["overall_score"],
                    "Avg Temp (°C)": cab_data["temperature_celsius"].mean(),
                    "Temp Std Dev": cab_data["temperature_celsius"].std(),
                    "Optimal %": time_range["optimal_pct"],
                    "Critical %": time_range["critical_pct"],
                    "Defrost Cycles": len(defrost),
                    "Cooling Cycles": len(cycles),
                    "Temp Drift": health["temp_drift"],
                }
            )

    comparison_df = pd.DataFrame(comparison_data)

    # Overall comparison table
    st.subheader("Comparison Summary")
    st.dataframe(
        comparison_df.style.background_gradient(subset=["Health Score"], cmap="RdYlGn", vmin=0, vmax=100)
        .background_gradient(subset=["Optimal %"], cmap="RdYlGn", vmin=0, vmax=100)
        .background_gradient(subset=["Critical %"], cmap="RdYlGn_r", vmin=0, vmax=10)
        .format(
            {
                "Health Score": "{:.1f}",
                "Avg Temp (°C)": "{:.2f}",
                "Temp Std Dev": "{:.2f}",
                "Optimal %": "{:.1f}",
                "Critical %": "{:.1f}",
                "Temp Drift": "{:.2f}",
            }
        ),
        use_container_width=True,
    )

    # Health score comparison
    st.subheader("Health Score Comparison")
    fig = px.bar(
        comparison_df.sort_values("Health Score", ascending=False),
        x="Cabinet",
        y="Health Score",
        title="Equipment Health Scores",
        color="Health Score",
        color_continuous_scale=["red", "orange", "yellow", "green"],
        range_color=[0, 100],
    )
    fig.add_hline(y=75, line_dash="dash", line_color="orange", annotation_text="Good")
    fig.add_hline(y=90, line_dash="dash", line_color="green", annotation_text="Excellent")
    st.plotly_chart(fig, use_container_width=True)

    # Temperature stability comparison
    st.subheader("Temperature Stability")
    fig = px.bar(
        comparison_df.sort_values("Temp Std Dev"),
        x="Cabinet",
        y="Temp Std Dev",
        title="Temperature Standard Deviation (lower is better)",
        color="Temp Std Dev",
        color_continuous_scale="Reds",
    )
    st.plotly_chart(fig, use_container_width=True)

    # Compliance comparison
    st.subheader("Time-in-Range Compliance")
    fig = px.bar(
        comparison_df.sort_values("Optimal %", ascending=False),
        x="Cabinet",
        y="Optimal %",
        title="% Time in Optimal Temperature Range",
        color="Optimal %",
        color_continuous_scale="Greens",
        range_color=[0, 100],
    )
    fig.add_hline(y=95, line_dash="dash", line_color="green", annotation_text="Target")
    st.plotly_chart(fig, use_container_width=True)

    # Identify best and worst performers
    st.subheader("Performance Rankings")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### 🏆 Best Performers")
        best = comparison_df.nlargest(3, "Health Score")[["Cabinet", "Health Score"]]
        for _idx, row in best.iterrows():
            st.success(f"**{row['Cabinet']}**: {row['Health Score']:.1f}/100")

    with col2:
        st.markdown("### ⚠️ Needs Attention")
        worst = comparison_df.nsmallest(3, "Health Score")[["Cabinet", "Health Score"]]
        for _idx, row in worst.iterrows():
            st.error(f"**{row['Cabinet']}**: {row['Health Score']:.1f}/100")

    # Temperature drift analysis
    st.subheader("Temperature Drift Analysis")
    drifting = comparison_df[comparison_df["Temp Drift"] > 1]

    if len(drifting) > 0:
        st.warning(f"⚠️ {len(drifting)} cabinet(s) showing significant temperature drift:")
        st.dataframe(drifting[["Cabinet", "Temp Drift"]], use_container_width=True)
    else:
        st.success("✅ No cabinets showing significant temperature drift")

    # Export
    csv = comparison_df.to_csv(index=False)
    st.download_button(
        label="📥 Download Comparison Data",
        data=csv,
        file_name=f"multi_cabinet_comparison_{compare_type.replace(' ', '_').lower()}.csv",
        mime="text/csv",
    )

elif len(selected_for_comparison) == 1:
    st.info("Please select at least 2 cabinets to compare")
else:
    st.info("Select cabinets above to begin comparison")
