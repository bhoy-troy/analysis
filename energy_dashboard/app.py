import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import extra_streamlit_components as stx
import pandas as pd
import streamlit as st

# Add parent directory to path to import utils
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.dynamodb import get_table, parse_data, query_by_gateway_and_timestamp

MIC_DEFAULT = 290
# 69a58037-ff2b-5a9c-8fe2-9adf3d3b08a2
GATEWAY_ID = "69a58037-ff2b-5a9c-8fe2-9adf3d3b08a2"  # Fixed gateway ID

# Authentication credentials
USERNAME = "energy"
PASSWORD = "energy"

st.set_page_config(page_title="Energy Dashboard", layout="wide")

# Initialize cookie manager
cookie_manager = stx.CookieManager()


# ── Authentication ────────────────────────────────────────────────────────────
def check_authentication():
    """Check if user is authenticated via session state or cookie."""
    # First check session state
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    # If not authenticated in session, check cookie
    if not st.session_state.authenticated:
        # Get all cookies (this is async, need to check if ready)
        auth_cookie = cookie_manager.get("energy_auth")

        if auth_cookie:
            # Check if cookie has valid timestamp and hasn't expired
            try:
                login_time = float(auth_cookie)
                current_time = datetime.now(UTC).timestamp()

                # Check if less than 60 minutes (3600 seconds) have passed
                if (current_time - login_time) < 3600:
                    st.session_state.authenticated = True
                else:
                    # Cookie expired, remove it
                    cookie_manager.delete("energy_auth")
            except (ValueError, TypeError):
                # Invalid cookie format, ignore
                pass

    return st.session_state.authenticated


def login_page():
    """Display login page."""
    st.title("🔒 Energy Dashboard Login")
    st.markdown("Please enter your credentials to access the dashboard")

    # Custom CSS for green login button
    st.markdown(
        """
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
    """,
        unsafe_allow_html=True,
    )

    with st.form("login_form"):
        username = st.text_input("Username", key="login_username")
        password = st.text_input("Password", type="password", key="login_password")
        submit = st.form_submit_button("Login", use_container_width=True)

        if submit:
            if username == USERNAME and password == PASSWORD:
                # Set session state
                st.session_state.authenticated = True

                # Set cookie with current timestamp (expires in 60 minutes)
                login_timestamp = str(datetime.now(UTC).timestamp())
                cookie_manager.set(
                    "energy_auth",
                    login_timestamp,
                    expires_at=datetime.now(UTC) + timedelta(minutes=60),
                )

                st.success("✅ Login successful!")
                st.rerun()
            else:
                st.error("❌ Invalid username or password")


def logout():
    """Logout user and clear authentication cookie."""
    st.session_state.authenticated = False

    # Clear the authentication cookie
    cookie_manager.delete("energy_auth")

    st.rerun()


# Check authentication
if not check_authentication():
    login_page()
    st.stop()

# ── Main Dashboard (only shown if authenticated) ──────────────────────────────
st.title("Energy Usage Dashboard")
st.caption("Connected Resource & Energy Intelligence Monitoring")

# Navigation hint
st.info(
    "👈 **Use the page selector in the sidebar** to access different analysis tools (Energy Overview, Peak Demand, Load Analysis, Phase Balance, etc.)"
)

# ── Sidebar ───────────────────────────────────────────────────────────────────
# Note: Streamlit automatically adds page navigation at the top of sidebar

st.sidebar.markdown("---")
st.sidebar.header("📅 Data Selection")

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

with st.sidebar.expander("🔧 Date & Gateway Settings", expanded=True):
    st.info(f"Gateway ID: {GATEWAY_ID}")

    end_date = st.date_input(
        "End Date",
        value=default_end,
    )

    days_back = st.slider("Days to load", min_value=1, max_value=31, value=days_in_prev_month)
    start_date = end_date - timedelta(days=days_back - 1)  # -1 to include end_date

    st.info(f"📊 {start_date} to {end_date} ({days_back} days)")

    # Show month name if loading a full month
    if days_back == days_in_prev_month and start_date == first_day_of_prev_month:
        month_name = first_day_of_prev_month.strftime("%B %Y")
        st.success(f"📅 Full month: {month_name}")

    # Add a load data button to force refresh
    load_data = st.button("🔄 Refresh Data", use_container_width=True, type="primary")

st.sidebar.markdown("---")

with st.sidebar.expander("⚙️ Configuration Settings", expanded=True):
    MIC = st.number_input("MIC (Maximum Import Capacity) kW", value=MIC_DEFAULT, step=10)
    demand_warning_pct = st.slider("Demand warning threshold (% of MIC)", 70, 95, 90)
    pf_target = st.slider("Power factor target", 0.80, 1.00, 0.90, step=0.01)

# Tariff Information
with st.sidebar.expander("💰 Tariff Rates", expanded=False):
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
# Core metrics
METRICS = [
    "Total kW",
    "Total kVA",
    "Total kVAr",
    "Average PF",
    # Phase-specific power for imbalance detection
    "kW1",
    "kW2",
    "kW3",
    # Phase currents
    "Current I1",
    "Current I2",
    "Current I3",
    # Phase voltages
    "Voltage V1-N",
    "Voltage V2-N",
    "Voltage V3-N",
    # Additional useful metrics
    "Frequency",
    "Neutral Current",
]
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

# Calculate phase imbalance
phase_imbalance = None
imbalance_risk = False
if all(col in df.columns for col in ["Current I1", "Current I2", "Current I3"]):
    avg_i1 = df["Current I1"].mean()
    avg_i2 = df["Current I2"].mean()
    avg_i3 = df["Current I3"].mean()
    avg_current = (avg_i1 + avg_i2 + avg_i3) / 3
    if avg_current > 0:
        max_deviation = max(abs(avg_i1 - avg_current), abs(avg_i2 - avg_current), abs(avg_i3 - avg_current))
        phase_imbalance = (max_deviation / avg_current) * 100
        imbalance_risk = phase_imbalance > 10  # >10% imbalance is problematic

c1, c2, c3, c4, c5, c6 = st.columns(6)
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
c4.metric(
    "Phase Imbalance",
    f"{phase_imbalance:.1f}%" if phase_imbalance is not None else "N/A",
    delta="Unbalanced" if imbalance_risk else "Balanced",
    delta_color="inverse" if imbalance_risk else "normal",
)
c5.metric("MIC", f"{MIC} kW")
c6.metric("Warning threshold", f"{demand_warning_pct}% = {MIC * demand_warning_pct / 100:.0f} kW")

if demand_risk:
    st.warning(f"⚠️ Peak demand {peak_kw:.1f} kW exceeds {demand_warning_pct}% of MIC. Demand penalty risk.")
if pf_risk:
    st.warning(f"⚠️ Avg PF {avg_pf:.3f} is below target {pf_target}. Reactive charges may apply.")
if imbalance_risk:
    st.warning(
        f"⚠️ Phase current imbalance detected: {phase_imbalance:.1f}%. "
        "Imbalance >10% can cause equipment damage and reduce efficiency. Check Phase Balance page."
    )

st.markdown("---")

# ── Store data in session state for pages ─────────────────────────────────────
st.session_state.df = df
st.session_state.raw = raw
st.session_state.data_loaded = True
st.session_state.MIC = MIC
st.session_state.demand_warning_pct = demand_warning_pct
st.session_state.pf_target = pf_target
st.session_state.start_date = start_date
st.session_state.end_date = end_date

# ── Navigation Instructions ───────────────────────────────────────────────────
st.success(
    "✅ Data loaded successfully! Use the **page navigation at the top of the sidebar** to explore different analyses."
)

with st.expander("📖 Available Analysis Pages", expanded=False):
    st.markdown("""
    **Navigate using the page selector at the top of the sidebar:**

    1. **⚡ Energy Overview** - Daily summaries, costs, and week-over-week comparison
    2. **📊 Peak Demand** - Hourly peaks vs MIC analysis
    3. **📈 Load Analysis** - 24-hour profiles, weekday/weekend patterns
    4. **⭐ Efficiency Score** - Daily power factor and efficiency heatmaps
    5. **🔮 Load Forecasting** - 7-day ahead predictions using ML models
    6. **🚨 Anomaly Detection** - Identify unusual consumption patterns
    7. **📊 Period Comparison** - Compare consumption across different time periods
    8. **📄 Raw Data** - View and download raw data
    9. **⚖️ Phase Balance** - 3-phase current/voltage/power balance analysis
    """)
