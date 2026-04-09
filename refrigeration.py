"""
Supermarket Cabinet Temperature Analysis System
Multi-Page Streamlit Application - Main Entry Point
"""

import logging
from datetime import datetime, timedelta

import pandas as pd
import streamlit as st

from utils.refrigeration import (
    RefrigerationAPIError,
    get_cabinet_readings,
    get_premises,
    get_units_for_premises,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("app.log"), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

st.set_page_config(
    page_title="Supermarket Cabinet Temperature Analysis",
    page_icon="🏪",
    layout="wide",
    initial_sidebar_state="expanded",
)


@st.cache_data(ttl=3600 * 24)
def load_premises():
    """Load premises from API with caching"""
    logger.info("Loading premises from API")
    try:
        premises = get_premises()
        logger.info(f"Loaded {len(premises)} premises (cached for 1 hour)")
        return premises
    except RefrigerationAPIError as e:
        logger.error(f"Failed to load premises: {e}")
        st.error(f"Failed to load premises: {e}")
        return []


@st.cache_data(ttl=3600 * 24)
def load_units(premises_id):
    """Load units for selected premises with caching"""
    logger.info(f"Loading units for premises {premises_id}")
    try:
        units = get_units_for_premises(premises_id)
        logger.info(f"Loaded {len(units)} units for premises {premises_id} (cached for 30 minutes)")
        return units
    except RefrigerationAPIError as e:
        logger.error(f"Failed to load units for premises {premises_id}: {e}")
        st.error(f"Failed to load units: {e}")
        return []


@st.cache_data(ttl=3600)
def load_readings_for_unit(unit_id, sensors, unit_description, start_dt, end_dt):
    """Load readings for a single unit with caching"""
    logger.info(f"Loading readings for unit {unit_id}:{sensors} ({unit_description}) from {start_dt} to {end_dt}")

    try:
        # readings = get_cabinet_readings(unit_id, start_dt, end_dt, sensors)
        # logger.debug(f"Received {len(readings)} raw readings for {unit_id}")

        # Convert readings to standardized format
        readings_data = []
        for readings in get_cabinet_readings(unit_id, start_dt, end_dt, sensors):
            readings_data.extend(
                [
                    {
                        "unit": reading.get("unit"),
                        "value": reading.get("readings").get(reading.get("id").split("-")[-1]),
                        "id": reading.get("id"),
                        "timestamp": reading.get("timestamp"),
                        # Add columns expected by the rest of the app
                        "temperature_celsius": float(reading.get("readings").get(reading.get("id").split("-")[-1])),
                        "cabinet": unit_description,
                        "name_label": f"{unit_description}_temperature",
                        "unit_id": unit_id,
                    }
                    for reading in readings
                ]
            )

        if readings_data:
            df = pd.DataFrame(readings_data)
            df["timestamp"] = pd.to_datetime(df["timestamp"], unit="s")
            logger.info(f"Converted {len(df)} readings for {unit_description} (cached for 1 hour)")
            return df

        logger.warning(f"No valid readings found for {unit_description}")
        return pd.DataFrame()

    except (RefrigerationAPIError, ValueError) as e:
        logger.error(f"Failed to load readings for {unit_description}: {e}")
        st.error(f"Failed to load readings for {unit_description}: {e}")
        return pd.DataFrame()


def load_all_readings(units, start_dt, end_dt):
    """Load readings for all selected units"""
    logger.info(f"Loading readings for {len(units)} units from {start_dt} to {end_dt}")
    all_data = []

    progress_bar = st.progress(0)
    status_text = st.empty()

    for idx, unit in enumerate(units):
        unit_id = unit.get("unit_id")
        unit_desc = unit.get("description", unit_id)
        sensors = unit.get("sensors", [])

        logger.debug(f"Loading unit {idx + 1}/{len(units)}: {unit_desc} ({unit_id})")
        status_text.text(f"Loading {unit_desc}... ({idx + 1}/{len(units)})")
        # import pdb
        # pdb.set_trace(
        #
        # )

        df = load_readings_for_unit(unit_id, sensors, unit_desc, start_dt, end_dt)
        if not df.empty:
            all_data.append(df)
            logger.debug(f"Added {len(df)} readings for {unit_desc}")
        else:
            logger.warning(f"No data loaded for {unit_desc}")

        progress_bar.progress((idx + 1) / len(units))

    progress_bar.empty()
    status_text.empty()

    if all_data:
        combined_df = pd.concat(all_data, ignore_index=True)
        combined_df = combined_df.sort_values(["cabinet", "timestamp"])
        combined_df["date"] = combined_df["timestamp"].dt.date
        combined_df["week"] = combined_df["timestamp"].dt.isocalendar().week
        combined_df["year"] = combined_df["timestamp"].dt.year
        logger.info(f"Successfully loaded {len(combined_df)} total readings from {len(all_data)} units")
        return combined_df

    logger.warning("No data loaded for any units")
    return pd.DataFrame()


# Initialize session state
if "data_loaded" not in st.session_state:
    st.session_state.data_loaded = False
if "df" not in st.session_state:
    st.session_state.df = pd.DataFrame()
if "selected_cabinet" not in st.session_state:
    st.session_state.selected_cabinet = None

# Main page content
st.title("🏪 Supermarket Cabinet Temperature Analysis")
st.markdown("### Comprehensive Temperature Monitoring & Analysis System")

# Data Selection Sidebar
with st.sidebar:
    st.header("📍 Data Selection")

    # Load premises
    premises_list = load_premises()

    if not premises_list:
        st.error("No premises available. Check API configuration.")
        st.info("Set REFRIGERATION_API_HOST and REFRIGERATION_API_TOKEN in .env")
        st.stop()

    # Premises selection
    premises_options = {f"{p.get('name', p.get('id', 'Unknown'))} (ID: {p.get('id')})": p for p in premises_list}
    selected_premises_label = st.selectbox(
        "Select Premises", options=list(premises_options.keys()), help="Choose premises to analyze"
    )
    selected_premises = premises_options[selected_premises_label]

    st.markdown("---")

    # Date range selection
    st.header("📅 Time Range")

    default_end = datetime.now()
    default_start = default_end - timedelta(days=7)

    start_date = st.date_input("Start Date", value=default_start.date(), max_value=datetime.now().date())

    start_time = st.time_input("Start Time", value=default_start.time())

    end_date = st.date_input("End Date", value=default_end.date(), max_value=datetime.now().date())

    end_time = st.time_input("End Time", value=default_end.time())

    start_datetime = datetime.combine(start_date, start_time)
    end_datetime = datetime.combine(end_date, end_time)

    date_range_days = (end_datetime - start_datetime).days

    if date_range_days > 31:
        st.error("⚠️ Date range cannot exceed 31 days")
        st.stop()
    elif date_range_days < 0:
        st.error("⚠️ End date must be after start date")
        st.stop()

    st.info(f"📊 Range: {date_range_days} days")

    st.markdown("---")

    # Load Data Button
    if st.button("🔄 Load Data", type="primary", use_container_width=True):
        logger.info(
            f"User clicked 'Load Data' for premises {selected_premises.get('id')} ({selected_premises.get('name')})"
        )
        logger.info(f"Date range: {start_datetime} to {end_datetime} ({date_range_days} days)")

        with st.spinner("Loading units..."):
            units = load_units(selected_premises.get("id"))

        if not units:
            logger.warning(f"No units found for premises {selected_premises.get('id')}")
            st.error("No units found for this premises")
            st.stop()

        logger.info(f"Found {len(units)} units for premises {selected_premises.get('id')}")
        st.success(f"Found {len(units)} units")

        with st.spinner("Loading temperature data..."):
            df = load_all_readings(units, start_datetime, end_datetime)

        if df.empty:
            logger.warning(
                f"No data found for premises {selected_premises.get('id')} in date range {start_datetime} to {end_datetime}"
            )
            st.error("No data found for selected time range")
            st.stop()

        logger.info(f"Successfully loaded {len(df)} readings for {df['cabinet'].nunique()} cabinets")
        st.session_state.df = df
        st.session_state.data_loaded = True
        st.session_state.premises_name = selected_premises.get("name", "Unknown")
        st.session_state.start_datetime = start_datetime
        st.session_state.end_datetime = end_datetime
        logger.info("Data stored in session state, triggering rerun")
        st.rerun()

    if st.session_state.data_loaded:
        st.success("✅ Data loaded")
        st.caption(f"📍 {st.session_state.get('premises_name', 'Unknown')}")
        st.caption(f"📊 {len(st.session_state.df):,} readings")

# Main content area
if not st.session_state.data_loaded:
    st.info("👈 Select premises and date range, then click 'Load Data' to begin analysis")
    st.markdown("---")
    st.markdown("### 🚀 Getting Started")
    st.markdown("""
    1. **Select a Premises** from the sidebar dropdown
    2. **Choose Date Range** (up to 31 days)
    3. **Click 'Load Data'** to fetch temperature readings
    4. **Navigate** to different analysis pages using the sidebar
    """)
    st.stop()

# Data is loaded - show overview
df = st.session_state.df

st.success(f"✅ Loaded {len(df):,} temperature readings from {df['cabinet'].nunique()} cabinets")
st.info(
    f"📅 Data range: {df['timestamp'].min().strftime('%Y-%m-%d %H:%M')} to {df['timestamp'].max().strftime('%Y-%m-%d %H:%M')}"
)

# Cabinet selection
st.markdown("---")
st.subheader("📊 Select Cabinet for Analysis")

col1, col2 = st.columns([2, 1])

with col1:
    cabinet_type = st.radio("Filter by Cabinet Type", ["All", "Freezers", "Chillers", "M&P", "Other"], horizontal=True)

if cabinet_type == "Freezers":
    available_cabinets = df[df["cabinet"].str.contains("Freezer", case=False, na=False)]["cabinet"].unique()
elif cabinet_type == "Chillers":
    available_cabinets = df[df["cabinet"].str.contains("Chiller", case=False, na=False)]["cabinet"].unique()
elif cabinet_type == "M&P":
    available_cabinets = df[df["cabinet"].str.contains("M&P", case=False, na=False)]["cabinet"].unique()
elif cabinet_type == "Other":
    available_cabinets = df[~df["cabinet"].str.contains("Freezer|Chiller|M&P", case=False, na=False)][
        "cabinet"
    ].unique()
else:
    available_cabinets = df["cabinet"].unique()

if len(available_cabinets) == 0:
    st.warning("No cabinets match the selected filter")
    st.stop()

selected_cabinet = st.selectbox("Choose a cabinet", sorted(available_cabinets), index=0)

# Store selected cabinet in session state
if "selected_cabinet" not in st.session_state or st.session_state.selected_cabinet != selected_cabinet:
    logger.info(f"User selected cabinet: {selected_cabinet}")

st.session_state.selected_cabinet = selected_cabinet
st.session_state.is_freezer = "freezer" in str(selected_cabinet).lower()

# Quick stats for selected cabinet
st.markdown("---")
st.subheader(f"Quick Stats: {selected_cabinet}")

cabinet_df = df[df["cabinet"] == selected_cabinet]

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

# Navigation guide
st.markdown("---")
st.markdown("### 📖 Navigation Guide")

st.markdown("""
**Use the sidebar to navigate to different analysis pages:**

- **📊 Overview** - Temperature distribution, daily statistics, and summary metrics
- **🔄 Cooling Cycles** - Compressor on/off cycle analysis and patterns
- **❄️ Defrost Cycles** - Defrost event detection and recovery time analysis
- **📈 Temperature Trends** - Time-series visualization and hourly patterns
- **🎯 Time-in-Range** - Food safety compliance and temperature range analysis
- **🏥 Health Score** - Predictive maintenance and equipment health monitoring
- **🔍 Multi-Cabinet Comparison** - Fleet-wide performance comparison
- **📄 PDF Reports** - Generate comprehensive reports for single or multiple cabinets

---
*Select a page from the sidebar to begin your analysis →*
""")

# Footer
st.markdown("---")
st.caption("🔬 Supermarket Cabinet Temperature Analysis System | Powered by Streamlit")
