import sys
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# Add parent directory to path to import utils
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from utils.tariffs import INDUSTRIAL_LEU_TARIFF

st.set_page_config(page_title="Energy Overview", layout="wide")

# ── Session State Validation ──────────────────────────────────────────────────
if "df" not in st.session_state or not st.session_state.get("data_loaded", False):
    st.error("⚠️ No data loaded. Please return to the main page and load data first.")
    st.stop()

# Get variables from session state
df = st.session_state.df
MIC = st.session_state.MIC
demand_warning_pct = st.session_state.demand_warning_pct
pf_target = st.session_state.pf_target
start_date = st.session_state.start_date
end_date = st.session_state.end_date

# ── Tab 1: Energy Overview ────────────────────────────────────────────────────
st.subheader("Energy profile — kW, kVA, kVAr & Max Demand")
fig = go.Figure()

# kW split into normal (blue) and high-demand (red)
if "Total kW" in df.columns:
    threshold = MIC * demand_warning_pct / 100
    df["kW_normal"] = df["Total kW"].where(df["Total kW"] < threshold)
    df["kW_high"] = df["Total kW"].where(df["Total kW"] >= threshold)

    fig.add_trace(
        go.Scatter(
            x=df["timestamp"],
            y=df["kW_normal"],
            name="kW (normal)",
            mode="lines",
            line={"color": "#3B82F6", "width": 2},
        )
    )
    fig.add_trace(
        go.Scatter(
            x=df["timestamp"],
            y=df["kW_high"],
            name="kW (high demand)",
            mode="lines",
            line={"color": "#EF4444", "width": 3},
        )
    )

# Remaining traces
for col, dash in [("Total kVA", "solid"), ("Total kVAr", "solid"), ("Max Demand kW", "dash")]:
    if col in df.columns:
        fig.add_trace(go.Scatter(x=df["timestamp"], y=df[col], name=col, mode="lines", line={"width": 2, "dash": dash}))

# MIC and warning lines
fig.add_hline(
    y=MIC,
    line_dash="dot",
    line_color="red",
    line_width=2,
    annotation_text=f"MIC {MIC} kW",
    annotation_position="top left",
)
fig.add_hline(
    y=MIC * demand_warning_pct / 100,
    line_dash="dot",
    line_color="orange",
    annotation_text=f"Warning {demand_warning_pct}%",
    annotation_position="bottom right",
)

# Shaded background regions where kW > threshold
if "Total kW" in df.columns:
    in_region = False
    region_start = None

    for ts, flag in zip(df["timestamp"], df["Total kW"] >= threshold, strict=False):
        if flag and not in_region:
            region_start = ts
            in_region = True
        elif not flag and in_region:
            fig.add_vrect(
                x0=region_start,
                x1=ts,
                fillcolor="red",
                opacity=0.10,
                layer="below",
                line_width=0,
                annotation_text="⚠️",
                annotation_position="top left",
                annotation_font_size=10,
                annotation_font_color="red",
            )
            in_region = False

    # Close any open region at end of data
    if in_region:
        fig.add_vrect(
            x0=region_start,
            x1=df["timestamp"].iloc[-1],
            fillcolor="red",
            opacity=0.10,
            layer="below",
            line_width=0,
            annotation_text="High demand",
            annotation_position="top left",
            annotation_font_size=10,
            annotation_font_color="red",
        )

fig.update_layout(
    xaxis={"title": "Timestamp"},
    yaxis={"title": "Power (kW / kVA / kVAr)"},
    legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "xanchor": "center", "x": 0.5},
    hovermode="x unified",
)
st.plotly_chart(fig, use_container_width=True)

# Daily Summary Table
st.markdown("---")
st.subheader("📅 Daily Energy Summary")

if "Total kW" in df.columns:
    # Add date column
    df_summary = df.copy()
    df_summary["date"] = df_summary["timestamp"].dt.date

    # Calculate time differences for energy calculation
    df_summary["time_diff_hours"] = df_summary["timestamp"].diff().dt.total_seconds() / 3600
    df_summary.loc[df_summary["time_diff_hours"] < 0, "time_diff_hours"] = 0
    df_summary.loc[df_summary["time_diff_hours"] > 1, "time_diff_hours"] = 0

    # Calculate energy (kWh) using trapezoidal integration
    df_summary["kWh_interval"] = df_summary["Total kW"] * df_summary["time_diff_hours"]

    # Group by date and calculate daily statistics
    daily_stats = (
        df_summary.groupby("date")
        .agg(
            {
                "kWh_interval": "sum",  # Cumulative energy
                "Total kW": "max",  # Peak demand
                "Average PF": "mean",  # Average power factor
                "Total kVA": "max",  # Peak apparent power
            }
        )
        .reset_index()
    )

    # Rename columns for display
    daily_stats.columns = [
        "Date",
        "Cumulative Energy (kWh)",
        "Peak Demand (kW)",
        "Avg Power Factor",
        "Peak Apparent (kVA)",
    ]

    # Round values
    daily_stats["Cumulative Energy (kWh)"] = daily_stats["Cumulative Energy (kWh)"].round(1)
    daily_stats["Peak Demand (kW)"] = daily_stats["Peak Demand (kW)"].round(1)
    daily_stats["Avg Power Factor"] = daily_stats["Avg Power Factor"].round(3)
    daily_stats["Peak Apparent (kVA)"] = daily_stats["Peak Apparent (kVA)"].round(1)

    # Add % of MIC column
    daily_stats["Peak % of MIC"] = ((daily_stats["Peak Demand (kW)"] / MIC) * 100).round(1)

    # Calculate  cost using Energia tariff
    # Split energy by time of day for accurate costing
    df_summary["hour"] = df_summary["timestamp"].dt.hour
    df_summary["is_day"] = df_summary["hour"].isin(INDUSTRIAL_LEU_TARIFF["day_hours"])

    # Calculate day and night energy per date
    daily_breakdown = df_summary.groupby(["date", "is_day"])["kWh_interval"].sum().unstack(fill_value=0)
    daily_breakdown.columns = ["Night kWh", "Day kWh"]
    daily_breakdown = daily_breakdown.reset_index()

    # Merge with daily_stats
    daily_stats = daily_stats.merge(daily_breakdown, left_on="Date", right_on="date", how="left").drop("date", axis=1)

    # Calculate daily costs based on Energia Industrial (LEU) tariff
    def calculate_daily_cost(row):
        day_kwh = row["Day kWh"]
        night_kwh = row["Night kWh"]
        total_kwh = day_kwh + night_kwh

        if total_kwh == 0:
            return 0.0

        # Energy charges
        energy_cost = total_kwh * INDUSTRIAL_LEU_TARIFF["energy_rate"]

        # DUoS charges (prorated daily from monthly)
        duos_standing = INDUSTRIAL_LEU_TARIFF["duos_standing_charge_monthly"] / 30
        duos_capacity = (
            INDUSTRIAL_LEU_TARIFF["max_import_capacity_kva"] * INDUSTRIAL_LEU_TARIFF["duos_capacity_charge_per_kva"]
        ) / 30
        duos_energy = (
            day_kwh * INDUSTRIAL_LEU_TARIFF["duos_day_rate"] + night_kwh * INDUSTRIAL_LEU_TARIFF["duos_night_rate"]
        )

        # TUoS charges (convert kWh to MWh)
        day_mwh = day_kwh / 1000
        night_mwh = night_kwh / 1000
        total_mwh = total_kwh / 1000

        demand_network = total_mwh * INDUSTRIAL_LEU_TARIFF["demand_network_capacity_per_mwh"]
        tuos_day = day_mwh * INDUSTRIAL_LEU_TARIFF["tuos_day_rate_per_mwh"]
        tuos_night = night_mwh * INDUSTRIAL_LEU_TARIFF["tuos_night_rate_per_mwh"]

        # Supplier capacity charge (prorated daily)
        supplier_capacity = INDUSTRIAL_LEU_TARIFF["supplier_capacity_charge_monthly"] / 30

        # Market charges
        capacity_social = total_kwh * INDUSTRIAL_LEU_TARIFF["capacity_socialisation_charge"]
        imperfections = total_kwh * INDUSTRIAL_LEU_TARIFF["imperfections_charge"]
        market_op = total_kwh * INDUSTRIAL_LEU_TARIFF["market_operator_charge"]
        currency_adj = total_kwh * INDUSTRIAL_LEU_TARIFF["currency_adjustment_charge"]

        # Levies (prorated daily)
        pso_levy = INDUSTRIAL_LEU_TARIFF["pso_levy_monthly"] / 30
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

        # Total
        total = subtotal + vat

        return round(total, 2)

    daily_stats["Est Cost (€)"] = daily_stats.apply(calculate_daily_cost, axis=1)

    # Display summary metrics
    col1, col2, col3, col4 = st.columns(4)
    total_energy = daily_stats["Cumulative Energy (kWh)"].sum()
    avg_daily_energy = daily_stats["Cumulative Energy (kWh)"].mean()
    max_peak = daily_stats["Peak Demand (kW)"].max()
    avg_pf = daily_stats["Avg Power Factor"].mean()
    total_cost = daily_stats["Est Cost (€)"].sum()

    col1.metric("Total Energy (Period)", f"{total_energy:.1f} kWh")
    col2.metric("Estimated Total Cost", f"€{total_cost:,.2f}")
    col3.metric("Highest Peak", f"{max_peak:.1f} kW", delta=f"{(max_peak/MIC)*100:.1f}% of MIC")
    col4.metric("Avg Power Factor", f"{avg_pf:.3f}")

    # Display the table with styling (excluding Day/Night kWh breakdown columns)
    display_cols = [
        "Date",
        "Cumulative Energy (kWh)",
        "Peak Demand (kW)",
        "Avg Power Factor",
        "Peak Apparent (kVA)",
        "Peak % of MIC",
        "Est Cost (€)",
    ]

    st.dataframe(
        daily_stats[display_cols]
        .style.background_gradient(subset=["Peak % of MIC"], cmap="RdYlGn_r", vmin=50, vmax=100)
        .background_gradient(subset=["Avg Power Factor"], cmap="RdYlGn", vmin=0.85, vmax=1.0)
        .format(
            {
                "Cumulative Energy (kWh)": "{:.1f}",
                "Peak Demand (kW)": "{:.1f}",
                "Avg Power Factor": "{:.3f}",
                "Peak Apparent (kVA)": "{:.1f}",
                "Peak % of MIC": "{:.1f}%",
                "Est Cost (€)": "€{:.2f}",
            }
        ),
        use_container_width=True,
        hide_index=True,
    )

    # Download button for the summary
    csv = daily_stats.to_csv(index=False).encode("utf-8")
    st.download_button(
        "📥 Download Daily Summary CSV",
        data=csv,
        file_name=f"daily_energy_summary_{datetime.now(UTC).strftime('%Y%m%d')}.csv",
        mime="text/csv",
    )

    # Cost calculation explanation
    with st.expander("ℹ️ How are costs calculated?"):
        vat_percent = float(INDUSTRIAL_LEU_TARIFF["vat_rate"]) * 100  # type: ignore[arg-type]
        st.markdown(f"""
        **Cost calculation based on Energia Industrial (LEU) Tariff:**

        Costs include all actual charges from your energy bill:
        - **Energy Charges**: €{INDUSTRIAL_LEU_TARIFF['energy_rate']}/kWh base rate
        - **Network Charges (DUoS)**:
          - Standing charge: €{INDUSTRIAL_LEU_TARIFF['duos_standing_charge_monthly']:.2f}/month (prorated daily)
          - Capacity charge: €{INDUSTRIAL_LEU_TARIFF['duos_capacity_charge_per_kva']}/kVA × {INDUSTRIAL_LEU_TARIFF['max_import_capacity_kva']} kVA
          - Day rate: €{INDUSTRIAL_LEU_TARIFF['duos_day_rate']}/kWh (08:00-23:00)
          - Night rate: €{INDUSTRIAL_LEU_TARIFF['duos_night_rate']}/kWh (23:00-08:00)
        - **Transmission Charges (TUoS)**: €{INDUSTRIAL_LEU_TARIFF['tuos_day_rate_per_mwh']}/MWh
        - **Supplier Capacity**: €{INDUSTRIAL_LEU_TARIFF['supplier_capacity_charge_monthly']:.2f}/month (prorated daily)
        - **Market Charges**: Imperfections, Market Operator, Currency Adjustment
        - **Levies**: PSO Levy (€{INDUSTRIAL_LEU_TARIFF['pso_levy_monthly']:.2f}/month), EEOS
        - **Electricity Tax**: €{INDUSTRIAL_LEU_TARIFF['electricity_tax']}/kWh
        - **VAT**: {vat_percent:.0f}%

        **Total estimated cost**: €{total_cost:,.2f} for {len(daily_stats)} days
        **Average cost per kWh**: €{(total_cost/total_energy) if total_energy > 0 else 0:.4f}/kWh (all-in rate)
        """)

        # Show day/night breakdown
        total_day_kwh = daily_stats["Day kWh"].sum()
        total_night_kwh = daily_stats["Night kWh"].sum()
        day_pct = (total_day_kwh / total_energy * 100) if total_energy > 0 else 0
        night_pct = (total_night_kwh / total_energy * 100) if total_energy > 0 else 0

        col1, col2 = st.columns(2)
        col1.metric("Day Usage (08:00-23:00)", f"{total_day_kwh:,.1f} kWh", delta=f"{day_pct:.1f}%")
        col2.metric("Night Usage (23:00-08:00)", f"{total_night_kwh:,.1f} kWh", delta=f"{night_pct:.1f}%")

    # Highlight any days exceeding threshold
    risk_days = daily_stats[daily_stats["Peak % of MIC"] >= demand_warning_pct]
    if len(risk_days) > 0:
        st.warning(
            f"⚠️ **{len(risk_days)} day(s)** exceeded {demand_warning_pct}% demand threshold:\n"
            + "\n".join(
                [
                    f"- {row['Date']}: Peak {row['Peak Demand (kW)']:.1f} kW ({row['Peak % of MIC']:.1f}% of MIC)"
                    for _, row in risk_days.iterrows()
                ]
            )
        )
else:
    st.info("No power data available for daily summary")

# Week-over-Week Comparison
st.markdown("---")
st.subheader("📊 Week-over-Week Comparison")

if "Total kW" in df.columns and len(df) >= 7:
    # Add week information
    df_weekly = df.copy()
    df_weekly["date"] = df_weekly["timestamp"].dt.date
    df_weekly["week_start"] = df_weekly["timestamp"].dt.to_period("W").apply(lambda r: r.start_time.date())

    # Calculate weekly statistics
    weekly_stats = df_weekly.groupby("week_start").agg(
        {
            "Total kW": ["mean", "max"],
            "Average PF": "mean" if "Average PF" in df_weekly.columns else lambda x: None,
        }
    )

    # Flatten column names
    weekly_stats.columns = ["_".join(col).strip() if col[1] else col[0] for col in weekly_stats.columns.values]

    # Calculate energy consumption per week
    df_weekly["time_diff_hours"] = df_weekly["timestamp"].diff().dt.total_seconds() / 3600
    df_weekly.loc[df_weekly["time_diff_hours"] < 0, "time_diff_hours"] = 0
    df_weekly.loc[df_weekly["time_diff_hours"] > 1, "time_diff_hours"] = 0
    df_weekly["kWh_interval"] = df_weekly["Total kW"] * df_weekly["time_diff_hours"]

    weekly_energy = df_weekly.groupby("week_start")["kWh_interval"].sum().reset_index()
    weekly_energy.columns = ["week_start", "Total_kWh"]

    # Merge energy data
    weekly_stats = weekly_stats.reset_index()
    weekly_stats = weekly_stats.merge(weekly_energy, on="week_start", how="left")

    # Get last two complete weeks if available
    if len(weekly_stats) >= 2:
        current_week = weekly_stats.iloc[-1]
        previous_week = weekly_stats.iloc[-2]

        # Calculate changes
        energy_change = (
            ((current_week["Total_kWh"] - previous_week["Total_kWh"]) / previous_week["Total_kWh"] * 100)
            if previous_week["Total_kWh"] > 0
            else 0
        )
        avg_kw_change = (
            ((current_week["Total kW_mean"] - previous_week["Total kW_mean"]) / previous_week["Total kW_mean"] * 100)
            if previous_week["Total kW_mean"] > 0
            else 0
        )
        peak_kw_change = (
            ((current_week["Total kW_max"] - previous_week["Total kW_max"]) / previous_week["Total kW_max"] * 100)
            if previous_week["Total kW_max"] > 0
            else 0
        )

        # Display comparison metrics
        col1, col2, col3, col4 = st.columns(4)

        col1.metric(
            "Total Energy",
            f"{current_week['Total_kWh']:.1f} kWh",
            delta=f"{energy_change:+.1f}%",
            delta_color="inverse",  # Red for increase (more energy used)
        )

        col2.metric(
            "Average Load",
            f"{current_week['Total kW_mean']:.1f} kW",
            delta=f"{avg_kw_change:+.1f}%",
            delta_color="inverse",
        )

        col3.metric(
            "Peak Demand",
            f"{current_week['Total kW_max']:.1f} kW",
            delta=f"{peak_kw_change:+.1f}%",
            delta_color="inverse",
        )

        if (
            "Average PF_mean" in current_week.index
            and pd.notna(current_week["Average PF_mean"])
            and pd.notna(previous_week["Average PF_mean"])
        ):
            pf_change = (
                (
                    (current_week["Average PF_mean"] - previous_week["Average PF_mean"])
                    / previous_week["Average PF_mean"]
                    * 100
                )
                if previous_week["Average PF_mean"] > 0
                else 0
            )
            col4.metric(
                "Avg Power Factor",
                f"{current_week['Average PF_mean']:.3f}",
                delta=f"{pf_change:+.1f}%",
                delta_color="normal",  # Green for increase (better PF)
            )
        else:
            col4.metric("Avg Power Factor", "N/A")

        # Week labels
        st.markdown(f"""
        **Current Week:** {current_week['week_start']} to {current_week['week_start'] + pd.Timedelta(days=6)}
        **Previous Week:** {previous_week['week_start']} to {previous_week['week_start'] + pd.Timedelta(days=6)}
        """)

        # Side-by-side bar chart comparison
        st.markdown("### Weekly Comparison Chart")

        comparison_data = pd.DataFrame(
            {
                "Metric": ["Total Energy (kWh)", "Avg Load (kW)", "Peak Demand (kW)"],
                "Previous Week": [
                    previous_week["Total_kWh"],
                    previous_week["Total kW_mean"],
                    previous_week["Total kW_max"],
                ],
                "Current Week": [
                    current_week["Total_kWh"],
                    current_week["Total kW_mean"],
                    current_week["Total kW_max"],
                ],
            }
        )

        fig_comparison = go.Figure()

        fig_comparison.add_trace(
            go.Bar(
                name="Previous Week",
                x=comparison_data["Metric"],
                y=comparison_data["Previous Week"],
                marker_color="#94A3B8",
                text=comparison_data["Previous Week"].round(1),
                textposition="outside",
            )
        )

        fig_comparison.add_trace(
            go.Bar(
                name="Current Week",
                x=comparison_data["Metric"],
                y=comparison_data["Current Week"],
                marker_color="#3B82F6",
                text=comparison_data["Current Week"].round(1),
                textposition="outside",
            )
        )

        fig_comparison.update_layout(
            barmode="group",
            xaxis_title="",
            yaxis_title="Value",
            legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "xanchor": "center", "x": 0.5},
            height=400,
        )

        st.plotly_chart(fig_comparison, use_container_width=True)

        # Insights
        st.markdown("### 💡 Key Insights")

        insights = []

        if abs(energy_change) > 10:
            direction = "increased" if energy_change > 0 else "decreased"
            color = "🔴" if energy_change > 0 else "🟢"
            insights.append(
                f"{color} Energy consumption {direction} by **{abs(energy_change):.1f}%** compared to last week"
            )

        if abs(peak_kw_change) > 5:
            direction = "higher" if peak_kw_change > 0 else "lower"
            insights.append(f"Peak demand is **{abs(peak_kw_change):.1f}%** {direction} than last week")

        if "Average PF_mean" in current_week.index and pd.notna(current_week["Average PF_mean"]):
            if current_week["Average PF_mean"] < pf_target:
                insights.append(
                    f"⚠️ Power factor ({current_week['Average PF_mean']:.3f}) is below target ({pf_target})"
                )

        # Check if current week peak exceeds warning threshold
        if current_week["Total kW_max"] >= (MIC * demand_warning_pct / 100):
            insights.append(
                f"⚠️ Peak demand reached **{(current_week['Total kW_max']/MIC*100):.1f}%** of MIC - demand penalty risk"
            )

        if insights:
            for insight in insights:
                st.info(insight)
        else:
            st.success("✅ Energy usage is stable week-over-week")

    elif len(weekly_stats) == 1:
        st.info("Need at least 2 weeks of data for week-over-week comparison")
    else:
        st.info("Not enough data for weekly comparison")
else:
    st.info("Need at least 7 days of data for week-over-week comparison")
