import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# Add parent directory to path to import utils
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.dynamodb import get_table, parse_data, query_by_gateway_and_timestamp
from utils.tariffs import INDUSTRIAL_LEU_TARIFF

MIC_DEFAULT = 290
# 69a58037-ff2b-5a9c-8fe2-9adf3d3b08a2
GATEWAY_ID = "69a58037-ff2b-5a9c-8fe2-9adf3d3b08a2"  # Fixed gateway ID

# Authentication credentials
USERNAME = "energy"
PASSWORD = "energy"

st.set_page_config(page_title="Energy Dashboard", layout="wide")


# ── Authentication ────────────────────────────────────────────────────────────
def check_authentication():
    """Check if user is authenticated."""
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    return st.session_state.authenticated


def login_page():
    """Display login page."""
    st.title("🔒 Energy Dashboard Login")
    st.markdown("Please enter your credentials to access the dashboard")

    # Custom CSS for green login button
    st.markdown("""
        <style>
        /* Target the login form submit button */
        div.stForm button[type="submit"],
        div.stForm button[kind="primaryFormSubmit"],
        div.stForm button[kind="formSubmit"] {
            background-color: #10b981 !important;
            color: white !important;
            border: none !important;
        }
        div.stForm button[type="submit"]:hover,
        div.stForm button[kind="primaryFormSubmit"]:hover,
        div.stForm button[kind="formSubmit"]:hover {
            background-color: #059669 !important;
            color: white !important;
        }
        /* Additional selector for Streamlit's button class */
        .stForm button {
            background-color: #10b981 !important;
            color: white !important;
        }
        .stForm button:hover {
            background-color: #059669 !important;
        }
        </style>
    """, unsafe_allow_html=True)

    with st.form("login_form"):
        username = st.text_input("Username", key="login_username")
        password = st.text_input("Password", type="password", key="login_password")
        submit = st.form_submit_button("Login", use_container_width=True)

        if submit:
            if username == USERNAME and password == PASSWORD:
                st.session_state.authenticated = True
                st.success("✅ Login successful!")
                st.rerun()
            else:
                st.error("❌ Invalid username or password")


def logout():
    """Logout user."""
    st.session_state.authenticated = False
    st.rerun()


# Check authentication
if not check_authentication():
    login_page()
    st.stop()

# ── Main Dashboard (only shown if authenticated) ──────────────────────────────
st.title("Energy Usage Dashboard")
st.caption("Connected Resource & Energy Intelligence Monitoring")

# ── Sidebar ───────────────────────────────────────────────────────────────────
st.sidebar.header("Data Selection")
st.sidebar.info(f"Gateway ID: {GATEWAY_ID}")

# Date range selection - automatically defaults to previous full month
today = datetime.now(UTC).date()

# Calculate first day of previous month
first_of_current_month = today.replace(day=1)
last_day_of_prev_month = first_of_current_month - timedelta(days=1)
first_day_of_prev_month = last_day_of_prev_month.replace(day=1)

# Calculate number of days in previous month
days_in_prev_month = (last_day_of_prev_month - first_day_of_prev_month).days + 1

# Default to full previous month
default_start = first_day_of_prev_month
default_end = last_day_of_prev_month

end_date = st.sidebar.date_input(
    "End Date",
    value=default_end,
)

days_back = st.sidebar.slider("Days to load", min_value=1, max_value=31, value=days_in_prev_month)
start_date = end_date - timedelta(days=days_back - 1)  # -1 to include end_date

st.sidebar.info(f"Date range: {start_date} to {end_date} ({days_back} days)")

# Show month name if loading a full month
if days_back == days_in_prev_month and start_date == first_day_of_prev_month:
    month_name = first_day_of_prev_month.strftime("%B %Y")
    st.sidebar.success(f"📅 Loading full month: {month_name}")

# Add a load data button to force refresh
load_data = st.sidebar.button("🔄 Refresh Data", use_container_width=True, type="primary")

st.sidebar.markdown("---")
st.sidebar.header("Configuration")
MIC = st.sidebar.number_input("MIC (Maximum Import Capacity) kW", value=MIC_DEFAULT, step=10)
demand_warning_pct = st.sidebar.slider("Demand warning threshold (% of MIC)", 70, 95, 90)
pf_target = st.sidebar.slider("Power factor target", 0.80, 1.00, 0.90, step=0.01)

# Tariff Information
st.sidebar.markdown("---")
with st.sidebar.expander("📋 View Tariff Rates"):
    st.markdown("### Industrial (LEU) Tariff")
    st.caption("Contract ends: 31 Oct 2025 | Max Capacity: 290 kVA")

    tariff_data = {
        "Charge Type": [
            "Energy Rate",
            "DUoS Standing Charge",
            "DUoS Capacity Charge",
            "DUoS Peak Rate",
            "DUoS Day Rate (Off-Peak)",
            "DUoS Night Rate",
            "Demand Network Capacity",
            "TUoS Day Rate",
            "TUoS Night Rate",
            "Supplier Capacity Charge",
            "Imperfections Charge",
            "Market Operator Charge",
            "PSO Levy",
            "Electricity Tax",
            "VAT",
        ],
        "Rate": [
            "€0.124178/kWh",
            "€401.41/month",
            "€2.8948/kVA",
            "€0.01513/kWh",
            "€0.01376/kWh",
            "€0.00219/kWh",
            "€7.3865/MWh",
            "€31.0312/MWh",
            "€31.0312/MWh",
            "€826.62/month",
            "€0.01462/kWh",
            "€0.000641/kWh",
            "€455.30/month",
            "€0.001/kWh",
            "9%",
        ],
    }

    tariff_df = pd.DataFrame(tariff_data)
    st.dataframe(tariff_df, use_container_width=True, hide_index=True)

    st.markdown("**Time Periods:**")
    st.markdown("- **Day**: 08:00 - 23:00")
    st.markdown("- **Night**: 23:00 - 08:00")
    st.markdown("- **Peak**: 08:00-11:00, 17:00-20:00 (verify)")

# Logout button at bottom of sidebar
st.sidebar.markdown("---")
if st.sidebar.button("🚪 Logout", use_container_width=True):
    logout()


# ── Load data from DynamoDB ───────────────────────────────────────────────────
@st.cache_data(ttl=3600)
def load_energy_data(gateway_id: str, start_ts: int, end_ts: int):
    """Load and parse energy data from DynamoDB."""
    table = get_table("energy_dev")

    items = query_by_gateway_and_timestamp(table=table, gateway_id=gateway_id, start_ts=start_ts, end_ts=end_ts)

    if not items:
        return pd.DataFrame()

    # Parse all items and flatten
    df_rows = []
    for item in items:
        try:
            parsed = parse_data(item)
            df_rows.extend(parsed)
        except Exception as e:
            st.warning(f"Failed to parse item: {e}")
            continue

    if not df_rows:
        return pd.DataFrame()

    return pd.DataFrame(df_rows)


# Convert dates to timestamps
start_ts = int(datetime.combine(start_date, datetime.min.time()).replace(tzinfo=UTC).timestamp())
end_ts = int(datetime.combine(end_date, datetime.max.time()).replace(tzinfo=UTC).timestamp())

# Clear cache if refresh button is clicked
if load_data:
    load_energy_data.clear()
    st.sidebar.success("Cache cleared - reloading data...")

with st.spinner(f"Loading energy data from DynamoDB for {days_back} days..."):
    raw = load_energy_data(GATEWAY_ID, start_ts, end_ts)

if raw.empty:
    st.error(f"No data found for gateway {GATEWAY_ID} between {start_date} and {end_date}")
    st.info("Please adjust the date range or check if data exists in DynamoDB.")
    st.stop()

# Show data load status
st.success(f"✅ Loaded {len(raw)} records | Date range: {start_date} to {end_date}")

# ── Parse timestamps (Unix epoch seconds) ────────────────────────────────────
# DynamoDB returns Unix epoch seconds
raw["timestamp"] = pd.to_datetime(raw["timestamp"], unit="s", utc=True).dt.tz_localize(None)

# Ensure we have required columns
required_cols = {"name", "timestamp"}
if not required_cols.issubset(raw.columns):
    st.error(f"Missing columns in DynamoDB data: {required_cols - set(raw.columns)}")
    st.error(f"Available columns: {list(raw.columns)}")
    st.stop()

# Check if 'value' column exists, if not try to infer from other columns
if "value" not in raw.columns:
    # Try to find a numeric column that could be the value
    numeric_cols = raw.select_dtypes(include=["number"]).columns.tolist()
    if numeric_cols:
        # Use the first numeric column as value
        value_col = [col for col in numeric_cols if col != "timestamp"][0]
        raw["value"] = raw[value_col]
        st.info(f"Using column '{value_col}' as value field")
    else:
        st.error("No 'value' column found in data and no numeric columns available")
        st.dataframe(raw.head(), hide_index=True)
        st.stop()

# ── Pivot: long → wide ────────────────────────────────────────────────────────
METRICS = ["Total kW", "Total kVA", "Total kVAr", "Average PF"]
df_filtered = raw[raw["name"].isin(METRICS)].copy()

df = (
    df_filtered.groupby(["timestamp", "name"])["value"]
    .mean()
    .reset_index()
    .pivot(index="timestamp", columns="name", values="value")
    .reset_index()
    .sort_values("timestamp")
    .reset_index(drop=True)
)
df.columns.name = None

missing = [m for m in METRICS if m not in df.columns]
if missing:
    st.warning(f"Metrics not found in data: {missing}")

df = df.dropna(subset=[m for m in METRICS if m in df.columns], how="all")

if "Total kW" in df.columns:
    df["Max Demand kW"] = (df["Total kW"] / df["Total kW"].max()) * MIC

# ── KPI tiles ─────────────────────────────────────────────────────────────────
peak_kw = df["Total kW"].max() if "Total kW" in df.columns else None
peak_kva = df["Total kVA"].max() if "Total kVA" in df.columns else None
avg_pf = df["Average PF"].mean() if "Average PF" in df.columns else None
mic_pct = (peak_kw / MIC) * 100 if peak_kw else None
demand_risk = peak_kw >= (demand_warning_pct / 100 * MIC) if peak_kw else False
pf_risk = avg_pf < pf_target if avg_pf else False

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric(
    "Peak Demand (kW)",
    f"{peak_kw:.1f}" if peak_kw else "N/A",
    delta=f"{mic_pct:.1f}% of MIC" if mic_pct else None,
    delta_color="inverse" if demand_risk else "normal",
)
c2.metric("Peak Apparent (kVA)", f"{peak_kva:.1f}" if peak_kva else "N/A")
c3.metric(
    "Avg Power Factor",
    f"{avg_pf:.3f}" if avg_pf else "N/A",
    delta="Below target" if pf_risk else "On target",
    delta_color="inverse" if pf_risk else "normal",
)
c4.metric("MIC", f"{MIC} kW")
c5.metric("Warning threshold", f"{demand_warning_pct}% = {MIC * demand_warning_pct / 100:.0f} kW")

if demand_risk:
    st.warning(f"⚠️ Peak demand {peak_kw:.1f} kW exceeds {demand_warning_pct}% of MIC. Demand penalty risk.")
if pf_risk:
    st.warning(f"⚠️ Avg PF {avg_pf:.3f} is below target {pf_target}. Reactive charges may apply.")

st.markdown("---")

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs(
    [
        "Energy Overview",
        "Peak Demand",
        "Load Analysis",
        "Efficiency Score",
        "Load Forecasting",
        "Anomaly Detection",
        "Period Comparison",
        "Raw Data",
    ]
)

# ── Tab 1: Energy Overview ────────────────────────────────────────────────────
with tab1:
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
            fig.add_trace(
                go.Scatter(x=df["timestamp"], y=df[col], name=col, mode="lines", line={"width": 2, "dash": dash})
            )

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
            duos_capacity = (INDUSTRIAL_LEU_TARIFF["max_import_capacity_kva"] *
                           INDUSTRIAL_LEU_TARIFF["duos_capacity_charge_per_kva"]) / 30
            duos_energy = (day_kwh * INDUSTRIAL_LEU_TARIFF["duos_day_rate"] +
                          night_kwh * INDUSTRIAL_LEU_TARIFF["duos_night_rate"])

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
            subtotal = (energy_cost + duos_standing + duos_capacity + duos_energy +
                       demand_network + tuos_day + tuos_night + supplier_capacity +
                       capacity_social + imperfections + market_op + currency_adj +
                       pso_levy + eeos + elec_tax)

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
            - **VAT**: {INDUSTRIAL_LEU_TARIFF['vat_rate']*100:.0f}%

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
                (
                    (current_week["Total kW_mean"] - previous_week["Total kW_mean"])
                    / previous_week["Total kW_mean"]
                    * 100
                )
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

# ── Tab 2: Peak Demand ────────────────────────────────────────────────────────
with tab2:
    if "Total kW" in df.columns:
        st.subheader("Hourly peak demand vs MIC")
        df["hour"] = df["timestamp"].dt.hour
        hourly_peak = df.groupby("hour")["Total kW"].max().reset_index()
        hourly_peak.columns = ["Hour", "Peak kW"]
        hourly_peak["Status"] = hourly_peak["Peak kW"].apply(
            lambda v: "Over Warning" if v >= MIC * demand_warning_pct / 100 else "Normal"
        )
        fig3 = px.bar(
            hourly_peak,
            x="Hour",
            y="Peak kW",
            color="Status",
            color_discrete_map={"Over Warning": "#EF4444", "Normal": "#3B82F6"},
        )
        fig3.add_hline(y=MIC, line_dash="dot", line_color="red", annotation_text=f"MIC {MIC} kW")
        fig3.add_hline(
            y=MIC * demand_warning_pct / 100,
            line_dash="dot",
            line_color="orange",
            annotation_text=f"Warning {demand_warning_pct}%",
        )
        fig3.update_layout(
            xaxis={"title": "Hour of Day", "dtick": 1},
            yaxis={"title": "Peak kW", "range": [0, MIC * 1.15], "dtick": 50},
            legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "xanchor": "center", "x": 0.5},
        )
        st.plotly_chart(fig3, use_container_width=True)

        st.subheader("Demand as % of MIC over time")
        df["MIC %"] = (df["Total kW"] / MIC) * 100
        fig4 = go.Figure()
        fig4.add_trace(
            go.Scatter(
                x=df["timestamp"], y=df["MIC %"], mode="lines", fill="tozeroy", name="Demand % MIC", line={"width": 2}
            )
        )
        fig4.add_hline(y=100, line_dash="dot", line_color="red", annotation_text="MIC 100%")
        fig4.add_hline(
            y=demand_warning_pct, line_dash="dot", line_color="orange", annotation_text=f"Warning {demand_warning_pct}%"
        )
        fig4.update_layout(
            xaxis={"title": "Timestamp"},
            yaxis={"title": "% of MIC", "range": [0, 115], "dtick": 10},
            hovermode="x unified",
        )
        st.plotly_chart(fig4, use_container_width=True)
    else:
        st.info("Total kW data not available.")

# ── Tab 3: Load Profile Analysis ─────────────────────────────────────────────
with tab3:
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
            x0=8, x1=23,
            fillcolor="rgba(255, 200, 0, 0.1)",
            layer="below",
            line_width=0,
            annotation_text="Day Rate (08:00-23:00)",
            annotation_position="top left",
        )

        fig_hourly.add_vrect(
            x0=23, x1=24,
            fillcolor="rgba(59, 130, 246, 0.1)",
            layer="below",
            line_width=0,
        )

        fig_hourly.add_vrect(
            x0=0, x1=8,
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
        daily_avg = (
            df_profile.groupby("day_name")["Total kW"]
            .agg(["mean", "max"])
            .reindex(day_order)
            .reset_index()
        )

        fig_daily = go.Figure()

        fig_daily.add_trace(
            go.Bar(
                x=daily_avg["day_name"],
                y=daily_avg["mean"],
                name="Average Load",
                marker_color=["#3B82F6" if day not in ["Saturday", "Sunday"] else "#10B981"
                              for day in daily_avg["day_name"]],
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
            df_profile.groupby("time_period")["Total kW"]
            .agg(["mean", "max"])
            .reindex(period_order)
            .reset_index()
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
            insights.append(
                "✅ Your load is relatively consistent throughout the day, indicating steady operations."
            )
        else:
            insights.append(
                f"📊 Your load varies significantly throughout the day (std dev: {load_variability:.1f} kW). "
                "Consider load shifting opportunities during off-peak hours."
            )

        # Peak vs off-peak comparison
        day_hours_avg = df_profile[df_profile["hour"].isin(range(8, 23))]["Total kW"].mean()
        night_hours_avg = df_profile[~df_profile["hour"].isin(range(8, 23))]["Total kW"].mean()

        day_savings_rate = INDUSTRIAL_LEU_TARIFF["duos_day_rate"]
        night_savings_rate = INDUSTRIAL_LEU_TARIFF["duos_night_rate"]
        potential_savings = (day_savings_rate - night_savings_rate) * 100  # per 100 kWh shifted

        if day_hours_avg > night_hours_avg * 1.2:
            insights.append(
                f"💰 Shifting load from day (€{day_savings_rate:.5f}/kWh) to night (€{night_savings_rate:.5f}/kWh) "
                f"could save €{potential_savings:.2f} per 100 kWh shifted on DUoS charges alone."
            )

        for insight in insights:
            st.info(insight)

    else:
        st.info("Total kW data not available.")

# ── Tab 4: Efficiency Score Heatmap ───────────────────────────────────────────
with tab4:
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
        daily_stats["efficiency_score"] = (
            (daily_stats["Average PF"] * 60) + (daily_stats["kW_kVA_ratio"] * 40)
        ).clip(0, 100)

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
                            [0.0, "rgb(178, 34, 34)"],    # Dark red (low/bad)
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

                st.code(f"""
Day {int(sample_day['day_of_month'])} ({sample_day['date']}):
  • Average Power Factor = {pf:.4f}
  • Average kW = {kw:.2f}
  • Average kVA = {kva:.2f}
  • kW/kVA Ratio = {kw:.2f} ÷ {kva:.2f} = {ratio:.4f}

Efficiency Score = ({pf:.4f} × 60) + ({ratio:.4f} × 40)
                = {pf*60:.2f} + {ratio*40:.2f}
                = {score:.2f}%
                """, language="text")
    else:
        st.info("Power Factor or kW/kVA data not available for efficiency calculation")

# ── Tab 5: Load Forecasting ───────────────────────────────────────────────────
with tab5:
    if "Total kW" in df.columns and len(df) > 48:  # Need at least 2 days of data
        st.subheader("⚡ 7-Day Load Forecasting")

        try:
            import numpy as np
            from statsmodels.tsa.holtwinters import ExponentialSmoothing

            # Resample to hourly data for cleaner forecasting
            df_hourly = df.set_index("timestamp").resample("h")["Total kW"].mean().reset_index()
            df_hourly = df_hourly.dropna()

            if len(df_hourly) < 24:
                st.warning("Need at least 24 hours of data for forecasting")
            else:
                # Prepare data
                ts_data = df_hourly.set_index("timestamp")["Total kW"]

                # Train Holt-Winters model
                with st.spinner("Training forecasting model..."):
                    # Determine seasonality (24 hours = daily pattern)
                    seasonal_periods = min(24, len(ts_data) // 2)

                    try:
                        model = ExponentialSmoothing(
                            ts_data,
                            seasonal_periods=seasonal_periods,
                            trend="add",
                            seasonal="add",
                            initialization_method="estimated",
                        )
                        fitted_model = model.fit(optimized=True)

                        # Forecast next 7 days (168 hours)
                        forecast_steps = 168
                        forecast = fitted_model.forecast(steps=forecast_steps)
                        forecast_index = pd.date_range(
                            start=ts_data.index[-1] + pd.Timedelta(hours=1), periods=forecast_steps, freq="h"
                        )

                        # Calculate prediction intervals (approximate)
                        # Using residual standard deviation
                        residuals = fitted_model.fittedvalues - ts_data
                        std_residuals = residuals.std()
                        confidence_level = 1.96  # 95% confidence

                        forecast_df = pd.DataFrame(
                            {
                                "timestamp": forecast_index,
                                "forecast": forecast.values,
                                "lower_bound": forecast.values - (confidence_level * std_residuals),
                                "upper_bound": forecast.values + (confidence_level * std_residuals),
                            }
                        )

                        # Ensure bounds are non-negative
                        forecast_df["lower_bound"] = forecast_df["lower_bound"].clip(lower=0)

                        # Key metrics
                        st.markdown("### 📊 Forecast Summary")
                        col1, col2, col3, col4 = st.columns(4)

                        predicted_peak = forecast_df["forecast"].max()
                        predicted_avg = forecast_df["forecast"].mean()
                        total_forecasted_kwh = forecast_df["forecast"].sum()
                        current_avg = ts_data[-24:].mean()  # Last 24 hours average

                        col1.metric(
                            "Predicted Peak (7d)",
                            f"{predicted_peak:.1f} kW",
                            delta=f"{((predicted_peak/MIC)*100):.1f}% of MIC",
                        )
                        col2.metric(
                            "Avg Load (7d)",
                            f"{predicted_avg:.1f} kW",
                            delta=f"{predicted_avg - current_avg:+.1f} kW vs now",
                        )
                        col3.metric("Total Energy (7d)", f"{total_forecasted_kwh:.0f} kWh")
                        col4.metric("Model Accuracy", f"{(1 - abs(residuals.mean() / ts_data.mean())) * 100:.1f}%")

                        # Visualization
                        st.markdown("### 📈 Historical Data + 7-Day Forecast")

                        fig_forecast = go.Figure()

                        # Historical data (last 7 days)
                        lookback_hours = min(168, len(ts_data))
                        historical = ts_data.iloc[-lookback_hours:]

                        fig_forecast.add_trace(
                            go.Scatter(
                                x=historical.index,
                                y=historical.values,
                                mode="lines",
                                name="Historical",
                                line={"color": "#3B82F6", "width": 2},
                            )
                        )

                        # Forecast
                        fig_forecast.add_trace(
                            go.Scatter(
                                x=forecast_df["timestamp"],
                                y=forecast_df["forecast"],
                                mode="lines",
                                name="Forecast",
                                line={"color": "#10B981", "width": 2, "dash": "dash"},
                            )
                        )

                        # Confidence interval
                        fig_forecast.add_trace(
                            go.Scatter(
                                x=forecast_df["timestamp"].tolist() + forecast_df["timestamp"].tolist()[::-1],
                                y=forecast_df["upper_bound"].tolist() + forecast_df["lower_bound"].tolist()[::-1],
                                fill="toself",
                                fillcolor="rgba(16, 185, 129, 0.2)",
                                line={"color": "rgba(255,255,255,0)"},
                                name="95% Confidence",
                                showlegend=True,
                            )
                        )

                        # Add MIC line
                        fig_forecast.add_hline(
                            y=MIC,
                            line_dash="dot",
                            line_color="red",
                            annotation_text=f"MIC {MIC} kW",
                            annotation_position="top right",
                        )

                        # Add warning threshold
                        fig_forecast.add_hline(
                            y=MIC * demand_warning_pct / 100,
                            line_dash="dot",
                            line_color="orange",
                            annotation_text=f"Warning {demand_warning_pct}%",
                            annotation_position="bottom right",
                        )

                        fig_forecast.update_layout(
                            xaxis_title="Date/Time", yaxis_title="Power (kW)", hovermode="x unified", height=500
                        )

                        st.plotly_chart(fig_forecast, use_container_width=True)

                        # Daily forecast breakdown
                        st.markdown("### 📅 Daily Forecast Breakdown")

                        forecast_df["date"] = forecast_df["timestamp"].dt.date
                        daily_forecast = (
                            forecast_df.groupby("date").agg({"forecast": ["mean", "max", "min", "sum"]}).round(1)
                        )
                        daily_forecast.columns = ["Avg kW", "Peak kW", "Min kW", "Total kWh"]
                        daily_forecast["Peak % of MIC"] = (daily_forecast["Peak kW"] / MIC * 100).round(1)

                        st.dataframe(
                            daily_forecast.style.background_gradient(
                                subset=["Peak % of MIC"], cmap="RdYlGn_r", vmin=50, vmax=100
                            ),
                            use_container_width=True,
                            hide_index=True,
                        )

                        # Insights
                        st.markdown("### 💡 Insights")

                        risk_days = daily_forecast[daily_forecast["Peak kW"] > (MIC * demand_warning_pct / 100)]
                        if len(risk_days) > 0:
                            st.warning(
                                f"⚠️ **{len(risk_days)} day(s)** predicted to exceed {demand_warning_pct}% demand threshold:\n"
                                + "\n".join(
                                    [
                                        f"- {date}: Peak {row['Peak kW']:.1f} kW ({row['Peak % of MIC']:.1f}% of MIC)"
                                        for date, row in risk_days.iterrows()
                                    ]
                                )
                            )
                        else:
                            st.success("✅ No demand threshold violations predicted in next 7 days")

                        # Compare to current week
                        avg_change = ((predicted_avg - current_avg) / current_avg) * 100
                        if abs(avg_change) > 5:
                            if avg_change > 0:
                                st.info(
                                    f"📈 Load predicted to increase by {avg_change:.1f}% compared to current average"
                                )
                            else:
                                st.info(
                                    f"📉 Load predicted to decrease by {abs(avg_change):.1f}% compared to current average"
                                )

                    except Exception as e:
                        st.error(f"Forecasting model error: {e}")
                        st.info("Try loading more historical data or check data quality")

        except ImportError:
            st.error("📦 Please install statsmodels: `pip install statsmodels>=0.14.0`")

    else:
        st.info("Need at least 48 hours of data for load forecasting")

# ── Tab 6: Anomaly Detection ──────────────────────────────────────────────────
with tab6:
    if "Total kW" in df.columns and len(df) > 24:
        st.subheader("🚨 Anomaly Detection")

        st.markdown("""
        Anomaly detection identifies unusual energy consumption patterns that deviate from normal behavior.
        This helps identify:
        - Equipment malfunctions or inefficiencies
        - Unexpected operation during off-hours
        - Sudden spikes or drops in demand
        - Irregular consumption patterns that may indicate issues

        The system analyzes power consumption (kW, kVA, PF) along with time-of-day and day-of-week patterns
        to flag readings that are statistically abnormal.
        """)

        try:
            import numpy as np
            from sklearn.ensemble import IsolationForest

            # Prepare features for anomaly detection
            df_anomaly = df.copy()
            df_anomaly["hour"] = df_anomaly["timestamp"].dt.hour
            df_anomaly["day_of_week"] = df_anomaly["timestamp"].dt.dayofweek
            df_anomaly["is_weekend"] = df_anomaly["day_of_week"].isin([5, 6]).astype(int)

            # Features for anomaly detection
            features = ["Total kW"]
            if "Total kVA" in df_anomaly.columns:
                features.append("Total kVA")
            if "Average PF" in df_anomaly.columns:
                features.append("Average PF")

            features.extend(["hour", "is_weekend"])

            X = df_anomaly[features].values

            # Method selection
            st.markdown("### Detection Method")
            st.info("""
            **Isolation Forest (ML)**: Machine learning algorithm that isolates anomalies by randomly partitioning data.
            Better for complex, multi-dimensional patterns.

            **Z-Score (Statistical)**: Classic statistical method measuring how many standard deviations a point is from the mean.
            Simpler and faster, best for single-variable outliers.
            """)
            detection_method = st.radio(
                "Choose detection algorithm:", ["Isolation Forest (ML)", "Z-Score (Statistical)"], horizontal=True
            )

            if detection_method == "Isolation Forest (ML)":
                # Isolation Forest
                contamination = st.slider(
                    "Contamination (expected % of anomalies)",
                    min_value=0.01,
                    max_value=0.20,
                    value=0.05,
                    step=0.01,
                    format="%.2f",
                )

                with st.spinner("Detecting anomalies using Isolation Forest..."):
                    iso_forest = IsolationForest(contamination=contamination, random_state=42, n_estimators=100)
                    df_anomaly["anomaly"] = iso_forest.fit_predict(X)
                    df_anomaly["anomaly_score"] = iso_forest.score_samples(X)

                    # -1 = anomaly, 1 = normal
                    df_anomaly["is_anomaly"] = df_anomaly["anomaly"] == -1

            else:
                # Z-Score method
                z_threshold = st.slider(
                    "Z-Score threshold (std deviations)", min_value=2.0, max_value=4.0, value=3.0, step=0.5
                )

                with st.spinner("Detecting anomalies using Z-Score..."):
                    # Calculate z-scores for kW
                    mean_kw = df_anomaly["Total kW"].mean()
                    std_kw = df_anomaly["Total kW"].std()
                    df_anomaly["z_score"] = np.abs((df_anomaly["Total kW"] - mean_kw) / std_kw)
                    df_anomaly["is_anomaly"] = df_anomaly["z_score"] > z_threshold
                    df_anomaly["anomaly_score"] = -df_anomaly["z_score"]  # Negative for consistency

            # Statistics
            n_anomalies = df_anomaly["is_anomaly"].sum()
            anomaly_pct = (n_anomalies / len(df_anomaly)) * 100

            st.markdown("### 📊 Detection Results")
            col1, col2, col3, col4 = st.columns(4)

            col1.metric("Anomalies Detected", f"{n_anomalies}")
            col2.metric("Anomaly Rate", f"{anomaly_pct:.2f}%")

            if n_anomalies > 0:
                anomaly_data = df_anomaly[df_anomaly["is_anomaly"]]
                col3.metric("Max Anomaly kW", f"{anomaly_data['Total kW'].max():.1f} kW")
                col4.metric("Min Anomaly kW", f"{anomaly_data['Total kW'].min():.1f} kW")

            # Visualization
            st.markdown("### 📈 Time Series with Anomalies")

            fig_anomaly = go.Figure()

            # Normal data
            normal_data = df_anomaly[~df_anomaly["is_anomaly"]]
            fig_anomaly.add_trace(
                go.Scatter(
                    x=normal_data["timestamp"],
                    y=normal_data["Total kW"],
                    mode="markers",
                    name="Normal",
                    marker={"color": "#3B82F6", "size": 4},
                )
            )

            # Anomalies
            if n_anomalies > 0:
                anomaly_data = df_anomaly[df_anomaly["is_anomaly"]]
                fig_anomaly.add_trace(
                    go.Scatter(
                        x=anomaly_data["timestamp"],
                        y=anomaly_data["Total kW"],
                        mode="markers",
                        name="Anomaly",
                        marker={"color": "#EF4444", "size": 10, "symbol": "x"},
                    )
                )

            fig_anomaly.update_layout(
                xaxis_title="Date/Time", yaxis_title="Power (kW)", hovermode="closest", height=400
            )

            st.plotly_chart(fig_anomaly, use_container_width=True)

            # Anomaly details
            if n_anomalies > 0:
                st.markdown("### 🔍 Anomaly Details")

                anomaly_table = anomaly_data[["timestamp", "Total kW", "hour", "day_of_week"]].copy()

                if "Total kVA" in anomaly_table.columns:
                    anomaly_table["Total kVA"] = anomaly_data["Total kVA"]
                if "Average PF" in anomaly_table.columns:
                    anomaly_table["Average PF"] = anomaly_data["Average PF"]

                anomaly_table["anomaly_score"] = anomaly_data["anomaly_score"]
                anomaly_table = anomaly_table.sort_values("timestamp", ascending=False)

                st.dataframe(
                    anomaly_table.head(20).style.background_gradient(subset=["Total kW"], cmap="RdYlGn_r"),
                    use_container_width=True,
                    hide_index=True,
                )

                # Patterns
                st.markdown("### 📊 Anomaly Patterns")

                col1, col2 = st.columns(2)

                with col1:
                    # Hour distribution
                    hourly_anomalies = anomaly_data.groupby("hour").size()
                    fig_hour = px.bar(
                        x=hourly_anomalies.index,
                        y=hourly_anomalies.values,
                        labels={"x": "Hour of Day", "y": "Anomaly Count"},
                        title="Anomalies by Hour",
                    )
                    st.plotly_chart(fig_hour, use_container_width=True)

                with col2:
                    # Day of week distribution
                    dow_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
                    dow_anomalies = anomaly_data.groupby("day_of_week").size().reindex(range(7), fill_value=0)
                    fig_dow = px.bar(
                        x=[dow_names[i] for i in dow_anomalies.index],
                        y=dow_anomalies.values,
                        labels={"x": "Day of Week", "y": "Anomaly Count"},
                        title="Anomalies by Day of Week",
                    )
                    st.plotly_chart(fig_dow, use_container_width=True)

                # Insights
                st.markdown("### 💡 Insights")

                # Most common anomaly hours
                top_hours = hourly_anomalies.nlargest(3)
                if len(top_hours) > 0:
                    st.info(
                        "🕐 Most anomalies occur at: "
                        + ", ".join([f"{h:02d}:00 ({count} times)" for h, count in top_hours.items()])
                    )

                # Weekend vs weekday
                weekend_anomalies = anomaly_data[anomaly_data["is_weekend"] == 1]
                weekday_anomalies = anomaly_data[anomaly_data["is_weekend"] == 0]

                if len(weekend_anomalies) > len(weekday_anomalies):
                    st.warning("⚠️ More anomalies detected on weekends - check if equipment running unnecessarily")
                elif len(weekday_anomalies) > len(weekend_anomalies) * 2:
                    st.info("📊 Anomalies primarily on weekdays - may indicate operational issues")

            # Export
            csv = df_anomaly[df_anomaly["is_anomaly"]][["timestamp", "Total kW", "anomaly_score"]].to_csv(index=False)
            st.download_button(
                "📥 Download Anomalies CSV",
                data=csv,
                file_name=f"anomalies_{datetime.now(UTC).strftime('%Y%m%d')}.csv",
                mime="text/csv",
            )

        except ImportError:
            st.error("📦 Please install scikit-learn: `pip install scikit-learn>=1.3.0`")

    else:
        st.info("Need at least 24 hours of data for anomaly detection")

# ── Tab 7: Period Comparison ──────────────────────────────────────────────────
with tab7:
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
        prev_week_data = df_periods[
            (df_periods["date"] >= prev_week_start) & (df_periods["date"] <= prev_week_end)
        ]

        # Previous month (30 days before today)
        prev_month_start = today - timedelta(days=36)  # 30 days + 7 days
        prev_month_end = today - timedelta(days=7)
        prev_month_data = df_periods[
            (df_periods["date"] >= prev_month_start) & (df_periods["date"] <= prev_month_end)
        ]

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
                    day_kwh * INDUSTRIAL_LEU_TARIFF["duos_day_rate"]
                    + night_kwh * INDUSTRIAL_LEU_TARIFF["duos_night_rate"]
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
                eeos = total_kwh * (
                    INDUSTRIAL_LEU_TARIFF["eeos_charge"] + INDUSTRIAL_LEU_TARIFF["eeos_credit"]
                )

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
        comparison_data = []
        for metrics in [last_7_metrics, prev_week_metrics, prev_month_metrics]:
            if metrics:
                comparison_data.append(metrics)

        if comparison_data:
            comparison_df = pd.DataFrame(comparison_data)

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
                        (
                            last_7_metrics["Estimated Cost (€)"]
                            - prev_week_metrics["Estimated Cost (€)"]
                        )
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
                        (last_7_daily - prev_month_daily) / prev_month_daily * 100
                        if prev_month_daily > 0
                        else 0
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

            periods = [m["Period"] for m in comparison_data]
            total_kwh = [m["Total kWh"] for m in comparison_data]
            day_kwh = [m["Day kWh"] for m in comparison_data]
            night_kwh = [m["Night kWh"] for m in comparison_data]

            fig_comparison.add_trace(
                go.Bar(name="Day (08:00-23:00)", x=periods, y=day_kwh, marker_color="#3B82F6")
            )

            fig_comparison.add_trace(
                go.Bar(name="Night (23:00-08:00)", x=periods, y=night_kwh, marker_color="#1E40AF")
            )

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

            costs = [m["Estimated Cost (€)"] for m in comparison_data]
            avg_daily_costs = [m["Avg Daily Cost (€)"] for m in comparison_data]

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
                    (last_7_metrics["Total kWh"] - prev_week_metrics["Total kWh"])
                    / prev_week_metrics["Total kWh"]
                    * 100
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
                    insights.append(
                        f"Peak demand changed by **{peak_change:+.1f}%** week-over-week"
                    )

            # Day vs Night usage pattern
            if last_7_metrics:
                day_pct = (
                    last_7_metrics["Day kWh"] / last_7_metrics["Total kWh"] * 100
                    if last_7_metrics["Total kWh"] > 0
                    else 0
                )
                night_pct = (
                    last_7_metrics["Night kWh"] / last_7_metrics["Total kWh"] * 100
                    if last_7_metrics["Total kWh"] > 0
                    else 0
                )

                insights.append(
                    f"📊 Last 7 days usage split: **{day_pct:.1f}%** during day, **{night_pct:.1f}%** at night"
                )

                # Cost efficiency
                cost_per_kwh = last_7_metrics["Cost per kWh (€)"]
                insights.append(
                    f"💰 All-in cost per kWh (last 7 days): **€{cost_per_kwh:.4f}**"
                )

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

# ── Tab 8: Raw Data ───────────────────────────────────────────────────────────
with tab8:
    col_a, col_b = st.columns(2)
    with col_a:
        st.subheader("Raw uploaded data")
        st.dataframe(raw, use_container_width=True, hide_index=True)
    with col_b:
        st.subheader("Pivoted (wide) data")
        st.dataframe(df, use_container_width=True, hide_index=True)

    st.download_button(
        "Download pivoted data as CSV",
        data=df.to_csv(index=False).encode("utf-8"),
        file_name="energy_pivoted.csv",
        mime="text/csv",
    )
