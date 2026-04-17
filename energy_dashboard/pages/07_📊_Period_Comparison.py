import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# Add parent directory to path to import utils
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from utils.tariffs import INDUSTRIAL_LEU_TARIFF

st.set_page_config(page_title="Period Comparison", layout="wide")

# ── Session State Validation ──────────────────────────────────────────────────
if "df" not in st.session_state or not st.session_state.get("data_loaded", False):
    st.error("⚠️ No data loaded. Please return to the main page and load data first.")
    st.stop()

# Get variables from session state
df = st.session_state.df

# ── Tab 7: Period Comparison ──────────────────────────────────────────────────
if "Total kW" in df.columns and len(df) >= 7:
    st.subheader("📊 Period Comparison Analysis")

    st.markdown("""
    Compare energy consumption, demand, and costs across different time periods.
    This helps identify trends and seasonal patterns in energy usage.
    """)

    # Prepare data with time calculations
    df_periods = df.copy()
    df_periods["date"] = df_periods["timestamp"].dt.date
    df_periods["hour"] = df_periods["timestamp"].dt.hour

    # Calculate energy (kWh)
    df_periods["time_diff_hours"] = df_periods["timestamp"].diff().dt.total_seconds() / 3600
    df_periods.loc[df_periods["time_diff_hours"] < 0, "time_diff_hours"] = 0
    df_periods.loc[df_periods["time_diff_hours"] > 1, "time_diff_hours"] = 0
    df_periods["kWh"] = df_periods["Total kW"] * df_periods["time_diff_hours"]

    # Time-of-day categorization
    df_periods["is_day"] = df_periods["hour"].isin(INDUSTRIAL_LEU_TARIFF["day_hours"])

    # Define periods
    today = df_periods["date"].max()

    # Last 7 days
    last_7_days_start = today - timedelta(days=6)
    last_7_days_data = df_periods[df_periods["date"] >= last_7_days_start]

    # Previous week (7 days before the last 7 days)
    prev_week_end = last_7_days_start - timedelta(days=1)
    prev_week_start = prev_week_end - timedelta(days=6)
    prev_week_data = df_periods[(df_periods["date"] >= prev_week_start) & (df_periods["date"] <= prev_week_end)]

    # Previous month (30 days before today)
    prev_month_start = today - timedelta(days=36)  # 30 days + 7 days
    prev_month_end = today - timedelta(days=7)
    prev_month_data = df_periods[(df_periods["date"] >= prev_month_start) & (df_periods["date"] <= prev_month_end)]

    def calculate_period_metrics(period_data, period_name, period_days):
        """Calculate comprehensive metrics for a time period."""
        if len(period_data) == 0:
            return None

        metrics = {
            "Period": period_name,
            "Days": period_days,
            "Total kWh": period_data["kWh"].sum(),
            "Avg Daily kWh": period_data["kWh"].sum() / period_days if period_days > 0 else 0,
            "Peak Demand (kW)": period_data["Total kW"].max(),
            "Avg Load (kW)": period_data["Total kW"].mean(),
            "Avg Power Factor": period_data["Average PF"].mean() if "Average PF" in period_data.columns else None,
            "Day kWh": period_data[period_data["is_day"]]["kWh"].sum(),
            "Night kWh": period_data[~period_data["is_day"]]["kWh"].sum(),
        }

        # Calculate cost
        total_kwh = metrics["Total kWh"]
        day_kwh = metrics["Day kWh"]
        night_kwh = metrics["Night kWh"]

        if total_kwh > 0:
            # Energy charge
            energy_cost = total_kwh * INDUSTRIAL_LEU_TARIFF["energy_rate"]

            # DUoS charges (prorated)
            duos_standing = INDUSTRIAL_LEU_TARIFF["duos_standing_charge_monthly"] / 30 * period_days
            duos_capacity = (
                INDUSTRIAL_LEU_TARIFF["max_import_capacity_kva"]
                * INDUSTRIAL_LEU_TARIFF["duos_capacity_charge_per_kva"]
                / 30
                * period_days
            )
            duos_energy = (
                day_kwh * INDUSTRIAL_LEU_TARIFF["duos_day_rate"] + night_kwh * INDUSTRIAL_LEU_TARIFF["duos_night_rate"]
            )

            # TUoS charges
            day_mwh = day_kwh / 1000
            night_mwh = night_kwh / 1000
            total_mwh = total_kwh / 1000

            demand_network = total_mwh * INDUSTRIAL_LEU_TARIFF["demand_network_capacity_per_mwh"]
            tuos_day = day_mwh * INDUSTRIAL_LEU_TARIFF["tuos_day_rate_per_mwh"]
            tuos_night = night_mwh * INDUSTRIAL_LEU_TARIFF["tuos_night_rate_per_mwh"]

            # Supplier capacity (prorated)
            supplier_capacity = INDUSTRIAL_LEU_TARIFF["supplier_capacity_charge_monthly"] / 30 * period_days

            # Market charges
            capacity_social = total_kwh * INDUSTRIAL_LEU_TARIFF["capacity_socialisation_charge"]
            imperfections = total_kwh * INDUSTRIAL_LEU_TARIFF["imperfections_charge"]
            market_op = total_kwh * INDUSTRIAL_LEU_TARIFF["market_operator_charge"]
            currency_adj = total_kwh * INDUSTRIAL_LEU_TARIFF["currency_adjustment_charge"]

            # Levies (prorated)
            pso_levy = INDUSTRIAL_LEU_TARIFF["pso_levy_monthly"] / 30 * period_days
            eeos = total_kwh * (INDUSTRIAL_LEU_TARIFF["eeos_charge"] + INDUSTRIAL_LEU_TARIFF["eeos_credit"])

            # Electricity tax
            elec_tax = total_kwh * INDUSTRIAL_LEU_TARIFF["electricity_tax"]

            # Subtotal before VAT
            subtotal = (
                energy_cost
                + duos_standing
                + duos_capacity
                + duos_energy
                + demand_network
                + tuos_day
                + tuos_night
                + supplier_capacity
                + capacity_social
                + imperfections
                + market_op
                + currency_adj
                + pso_levy
                + eeos
                + elec_tax
            )

            # VAT
            vat = subtotal * INDUSTRIAL_LEU_TARIFF["vat_rate"]
            total_cost = subtotal + vat

            metrics["Estimated Cost (€)"] = round(total_cost, 2)
            metrics["Cost per kWh (€)"] = round(total_cost / total_kwh, 4) if total_kwh > 0 else 0
            metrics["Avg Daily Cost (€)"] = round(total_cost / period_days, 2) if period_days > 0 else 0
        else:
            metrics["Estimated Cost (€)"] = 0
            metrics["Cost per kWh (€)"] = 0
            metrics["Avg Daily Cost (€)"] = 0

        return metrics

    # Calculate metrics for each period
    last_7_metrics = calculate_period_metrics(last_7_days_data, "Last 7 Days", 7)
    prev_week_metrics = calculate_period_metrics(prev_week_data, "Previous Week", 7)
    prev_month_metrics = calculate_period_metrics(
        prev_month_data, "Previous Month", (prev_month_end - prev_month_start).days + 1
    )

    # Create comparison table
    period_comparison_data: list[dict] = []
    for metrics in [last_7_metrics, prev_week_metrics, prev_month_metrics]:
        if metrics:
            period_comparison_data.append(metrics)

    if period_comparison_data:
        comparison_df = pd.DataFrame(period_comparison_data)

        # Display key metrics comparison
        st.markdown("### 📈 Key Metrics Comparison")

        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric(
                "Last 7 Days - Total kWh",
                f"{last_7_metrics['Total kWh']:,.1f}" if last_7_metrics else "N/A",
            )
            st.metric(
                "Estimated Cost",
                f"€{last_7_metrics['Estimated Cost (€)']:,.2f}" if last_7_metrics else "N/A",
            )

        with col2:
            if prev_week_metrics and last_7_metrics:
                kwh_change = (
                    (last_7_metrics["Total kWh"] - prev_week_metrics["Total kWh"])
                    / prev_week_metrics["Total kWh"]
                    * 100
                    if prev_week_metrics["Total kWh"] > 0
                    else 0
                )
                cost_change = (
                    (last_7_metrics["Estimated Cost (€)"] - prev_week_metrics["Estimated Cost (€)"])
                    / prev_week_metrics["Estimated Cost (€)"]
                    * 100
                    if prev_week_metrics["Estimated Cost (€)"] > 0
                    else 0
                )

                st.metric(
                    "vs Previous Week - kWh",
                    f"{prev_week_metrics['Total kWh']:,.1f}",
                    delta=f"{kwh_change:+.1f}%",
                    delta_color="inverse",
                )
                st.metric(
                    "vs Previous Week - Cost",
                    f"€{prev_week_metrics['Estimated Cost (€)']:,.2f}",
                    delta=f"{cost_change:+.1f}%",
                    delta_color="inverse",
                )
            else:
                st.info("Previous week data not available")

        with col3:
            if prev_month_metrics and last_7_metrics:
                # Normalize to daily average for fair comparison
                last_7_daily = last_7_metrics["Avg Daily kWh"]
                prev_month_daily = prev_month_metrics["Avg Daily kWh"]

                daily_kwh_change = (
                    (last_7_daily - prev_month_daily) / prev_month_daily * 100 if prev_month_daily > 0 else 0
                )

                st.metric(
                    "Previous Month - Avg Daily kWh",
                    f"{prev_month_daily:,.1f}",
                    delta=f"{daily_kwh_change:+.1f}%",
                    delta_color="inverse",
                )
                st.metric(
                    "Total Cost (Full Period)",
                    f"€{prev_month_metrics['Estimated Cost (€)']:,.2f}",
                )
            else:
                st.info("Previous month data not available")

        # Detailed comparison table
        st.markdown("### 📋 Detailed Comparison Table")

        display_columns = [
            "Period",
            "Days",
            "Total kWh",
            "Avg Daily kWh",
            "Peak Demand (kW)",
            "Avg Load (kW)",
            "Avg Power Factor",
            "Estimated Cost (€)",
            "Avg Daily Cost (€)",
            "Cost per kWh (€)",
        ]

        st.dataframe(
            comparison_df[display_columns]
            .style.background_gradient(subset=["Total kWh"], cmap="YlGn")
            .background_gradient(subset=["Estimated Cost (€)"], cmap="YlOrRd")
            .format(
                {
                    "Total kWh": "{:,.1f}",
                    "Avg Daily kWh": "{:,.1f}",
                    "Peak Demand (kW)": "{:.1f}",
                    "Avg Load (kW)": "{:.1f}",
                    "Avg Power Factor": "{:.3f}",
                    "Estimated Cost (€)": "€{:,.2f}",
                    "Avg Daily Cost (€)": "€{:.2f}",
                    "Cost per kWh (€)": "€{:.4f}",
                }
            ),
            use_container_width=True,
            hide_index=True,
        )

        # Visualization - Energy consumption comparison
        st.markdown("### 📊 Energy Consumption Comparison")

        fig_comparison = go.Figure()

        periods = [m["Period"] for m in period_comparison_data]
        total_kwh = [m["Total kWh"] for m in period_comparison_data]
        day_kwh = [m["Day kWh"] for m in period_comparison_data]
        night_kwh = [m["Night kWh"] for m in period_comparison_data]

        fig_comparison.add_trace(go.Bar(name="Day (08:00-23:00)", x=periods, y=day_kwh, marker_color="#3B82F6"))

        fig_comparison.add_trace(go.Bar(name="Night (23:00-08:00)", x=periods, y=night_kwh, marker_color="#1E40AF"))

        fig_comparison.update_layout(
            barmode="stack",
            xaxis_title="Period",
            yaxis_title="Energy Consumption (kWh)",
            legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "xanchor": "center", "x": 0.5},
            height=400,
        )

        st.plotly_chart(fig_comparison, use_container_width=True)

        # Cost comparison visualization
        st.markdown("### 💰 Cost Comparison")

        fig_cost = go.Figure()

        costs = [m["Estimated Cost (€)"] for m in period_comparison_data]
        avg_daily_costs = [m["Avg Daily Cost (€)"] for m in period_comparison_data]

        fig_cost.add_trace(
            go.Bar(
                name="Total Cost",
                x=periods,
                y=costs,
                marker_color="#10B981",
                text=[f"€{c:,.2f}" for c in costs],
                textposition="outside",
            )
        )

        fig_cost.update_layout(
            xaxis_title="Period",
            yaxis_title="Estimated Cost (€)",
            height=400,
        )

        st.plotly_chart(fig_cost, use_container_width=True)

        # Insights
        st.markdown("### 💡 Period Insights")

        insights = []

        if last_7_metrics and prev_week_metrics:
            kwh_change = (
                (last_7_metrics["Total kWh"] - prev_week_metrics["Total kWh"]) / prev_week_metrics["Total kWh"] * 100
                if prev_week_metrics["Total kWh"] > 0
                else 0
            )

            if abs(kwh_change) > 10:
                direction = "increased" if kwh_change > 0 else "decreased"
                color = "🔴" if kwh_change > 0 else "🟢"
                insights.append(
                    f"{color} Energy consumption {direction} by **{abs(kwh_change):.1f}%** compared to previous week"
                )

            peak_change = (
                (last_7_metrics["Peak Demand (kW)"] - prev_week_metrics["Peak Demand (kW)"])
                / prev_week_metrics["Peak Demand (kW)"]
                * 100
                if prev_week_metrics["Peak Demand (kW)"] > 0
                else 0
            )

            if abs(peak_change) > 5:
                insights.append(f"Peak demand changed by **{peak_change:+.1f}%** week-over-week")

        # Day vs Night usage pattern
        if last_7_metrics:
            day_pct = (
                last_7_metrics["Day kWh"] / last_7_metrics["Total kWh"] * 100 if last_7_metrics["Total kWh"] > 0 else 0
            )
            night_pct = (
                last_7_metrics["Night kWh"] / last_7_metrics["Total kWh"] * 100
                if last_7_metrics["Total kWh"] > 0
                else 0
            )

            insights.append(f"📊 Last 7 days usage split: **{day_pct:.1f}%** during day, **{night_pct:.1f}%** at night")

            # Cost efficiency
            cost_per_kwh = last_7_metrics["Cost per kWh (€)"]
            insights.append(f"💰 All-in cost per kWh (last 7 days): **€{cost_per_kwh:.4f}**")

        if insights:
            for insight in insights:
                st.info(insight)

        # Download comparison data
        csv = comparison_df.to_csv(index=False).encode("utf-8")
        st.download_button(
            "📥 Download Period Comparison CSV",
            data=csv,
            file_name=f"period_comparison_{datetime.now(UTC).strftime('%Y%m%d')}.csv",
            mime="text/csv",
        )

    else:
        st.warning("Not enough data for period comparison analysis")

else:
    st.info("Need at least 7 days of data for period comparison analysis")
