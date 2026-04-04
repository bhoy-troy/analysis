"""
Supermarket Cabinet Temperature Analysis System
Multi-Page Streamlit Application - Main Entry Point
"""

import streamlit as st
import pandas as pd

st.set_page_config(
    page_title="Supermarket Cabinet Temperature Analysis",
    page_icon="🏪",
    layout="wide",
    initial_sidebar_state="expanded"
)

@st.cache_data
def load_data():
    """Load and prepare the temperature data"""
    df = pd.read_csv("cobh.csv")
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.sort_values(["name_label", "timestamp"])
    df["cabinet"] = df["name_label"].str.replace("_temperature", "")
    df["date"] = df["timestamp"].dt.date
    df["week"] = df["timestamp"].dt.isocalendar().week
    df["year"] = df["timestamp"].dt.year
    return df

# Load data
df = load_data()

# Store in session state for access across pages
if 'df' not in st.session_state:
    st.session_state.df = df

# Main page content
st.title("🏪 Supermarket Cabinet Temperature Analysis")
st.markdown("### Comprehensive Temperature Monitoring & Analysis System")

st.success(f"✅ Loaded {len(df):,} temperature readings from {df['cabinet'].nunique()} cabinets")
st.info(f"📅 Data range: {df['timestamp'].min().strftime('%Y-%m-%d')} to {df['timestamp'].max().strftime('%Y-%m-%d')}")

# Cabinet selection
st.markdown("---")
st.subheader("📊 Select Cabinet for Analysis")

col1, col2 = st.columns([2, 1])

with col1:
    cabinet_type = st.radio(
        "Filter by Cabinet Type",
        ["All", "Freezers", "Chillers", "M&P", "Other"],
        horizontal=True
    )

if cabinet_type == "Freezers":
    available_cabinets = df[df['cabinet'].str.contains('Freezer', case=False)]['cabinet'].unique()
elif cabinet_type == "Chillers":
    available_cabinets = df[df['cabinet'].str.contains('Chiller', case=False)]['cabinet'].unique()
elif cabinet_type == "M&P":
    available_cabinets = df[df['cabinet'].str.contains('M&P', case=False)]['cabinet'].unique()
elif cabinet_type == "Other":
    available_cabinets = df[~df['cabinet'].str.contains('Freezer|Chiller|M&P', case=False)]['cabinet'].unique()
else:
    available_cabinets = df['cabinet'].unique()

selected_cabinet = st.selectbox(
    "Choose a cabinet",
    sorted(available_cabinets),
    index=0
)

# Store selected cabinet in session state
st.session_state.selected_cabinet = selected_cabinet
st.session_state.is_freezer = 'freezer' in selected_cabinet.lower()

# Quick stats for selected cabinet
st.markdown("---")
st.subheader(f"Quick Stats: {selected_cabinet}")

cabinet_df = df[df['cabinet'] == selected_cabinet]

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("Total Readings", f"{len(cabinet_df):,}")
with col2:
    avg_temp = cabinet_df['temperature_celsius'].mean()
    st.metric("Average Temperature", f"{avg_temp:.2f}°C")
with col3:
    min_temp = cabinet_df['temperature_celsius'].min()
    st.metric("Min Temperature", f"{min_temp:.2f}°C")
with col4:
    max_temp = cabinet_df['temperature_celsius'].max()
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
