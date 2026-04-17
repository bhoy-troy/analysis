"""
Phase Balance Analysis Page
Monitors 3-phase electrical system balance and identifies load distribution issues
"""

import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

st.set_page_config(page_title="Phase Balance", page_icon="⚖️", layout="wide")

# ── Session State Validation ──────────────────────────────────────────────────
if "data_loaded" not in st.session_state or not st.session_state.data_loaded:
    st.error("⚠️ No data loaded. Please return to the main page and load data first.")
    st.stop()

# Get data from session state
df = st.session_state.df
raw = st.session_state.raw
MIC = st.session_state.MIC
start_date = st.session_state.start_date
end_date = st.session_state.end_date

# ── Page Header ───────────────────────────────────────────────────────────────
st.title("⚖️ Phase Balance Analysis")
st.markdown("""
Monitor 3-phase electrical system balance. Imbalanced loads cause:
- Increased neutral currents and cable heating
- Motor vibration and reduced lifespan
- Transformer overheating
- Higher energy losses
""")

# ── Check if phase data is available ──────────────────────────────────────────
required_cols = ["Current I1", "Current I2", "Current I3"]
if not all(col in df.columns for col in required_cols):
    st.error(f"⚠️ Phase current data not available. Required columns: {', '.join(required_cols)}")
    st.info(
        "Phase-specific data may not be collected from your meter. "
        "Check that the Modbus registers for I1, I2, I3 are being polled."
    )
    st.stop()

# ── Current Imbalance Analysis ────────────────────────────────────────────────
st.subheader("⚡ Phase Current Balance")

# Calculate instantaneous imbalance
df_imbalance = df.copy()
df_imbalance["Avg Current"] = (df_imbalance["Current I1"] + df_imbalance["Current I2"] + df_imbalance["Current I3"]) / 3

# Calculate max deviation from average
df_imbalance["Max Deviation"] = df_imbalance[["Current I1", "Current I2", "Current I3"]].apply(
    lambda row: max(
        abs(row["Current I1"] - df_imbalance.loc[row.name, "Avg Current"]),
        abs(row["Current I2"] - df_imbalance.loc[row.name, "Avg Current"]),
        abs(row["Current I3"] - df_imbalance.loc[row.name, "Avg Current"]),
    ),
    axis=1,
)

# Imbalance percentage
df_imbalance["Imbalance %"] = (
    df_imbalance["Max Deviation"] / df_imbalance["Avg Current"].replace(0, float("nan"))
) * 100

# Overall statistics
avg_i1 = df["Current I1"].mean()
avg_i2 = df["Current I2"].mean()
avg_i3 = df["Current I3"].mean()
avg_current = (avg_i1 + avg_i2 + avg_i3) / 3

max_deviation = max(abs(avg_i1 - avg_current), abs(avg_i2 - avg_current), abs(avg_i3 - avg_current))
imbalance_pct = (max_deviation / avg_current * 100) if avg_current > 0 else 0

# KPI metrics
col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("Phase 1 Avg", f"{avg_i1:.2f} A")
col2.metric("Phase 2 Avg", f"{avg_i2:.2f} A")
col3.metric("Phase 3 Avg", f"{avg_i3:.2f} A")
col4.metric(
    "Imbalance",
    f"{imbalance_pct:.1f}%",
    delta="Critical" if imbalance_pct > 10 else "Warning" if imbalance_pct > 5 else "OK",
    delta_color="inverse" if imbalance_pct > 5 else "normal",
)

# Check for neutral current if available
if "Neutral Current" in df.columns:
    avg_neutral = df["Neutral Current"].mean()
    col5.metric("Neutral Current", f"{avg_neutral:.2f} A")
else:
    col5.metric("Neutral Current", "N/A")

# Status indicator
st.markdown("---")
if imbalance_pct > 10:
    st.error(
        f"🚨 **CRITICAL IMBALANCE**: {imbalance_pct:.1f}% imbalance detected. "
        "Immediate action required to prevent equipment damage."
    )
elif imbalance_pct > 5:
    st.warning(f"⚠️ **WARNING**: {imbalance_pct:.1f}% imbalance. Monitor and consider load redistribution.")
else:
    st.success(f"✅ **BALANCED**: {imbalance_pct:.1f}% imbalance. System is well-balanced.")

# ── Time Series: Phase Currents ───────────────────────────────────────────────
st.markdown("---")
st.subheader("📈 Phase Current Trends")

fig_currents = go.Figure()

# Add traces for each phase
colors = {"Current I1": "#EF4444", "Current I2": "#3B82F6", "Current I3": "#10B981"}
for phase in ["Current I1", "Current I2", "Current I3"]:
    fig_currents.add_trace(
        go.Scatter(
            x=df["timestamp"],
            y=df[phase],
            name=phase.replace("Current ", "Phase "),
            mode="lines",
            line={"color": colors[phase], "width": 2},
        )
    )

# Add average current line
fig_currents.add_trace(
    go.Scatter(
        x=df["timestamp"],
        y=df_imbalance["Avg Current"],
        name="Average",
        mode="lines",
        line={"color": "#94A3B8", "width": 2, "dash": "dash"},
    )
)

fig_currents.update_layout(
    xaxis_title="Time",
    yaxis_title="Current (A)",
    legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "xanchor": "center", "x": 0.5},
    hovermode="x unified",
    height=400,
)

st.plotly_chart(fig_currents, use_container_width=True)

# ── Imbalance % Over Time ─────────────────────────────────────────────────────
st.markdown("---")
st.subheader("📊 Imbalance Percentage Over Time")

fig_imbalance = go.Figure()

fig_imbalance.add_trace(
    go.Scatter(
        x=df_imbalance["timestamp"],
        y=df_imbalance["Imbalance %"],
        name="Imbalance %",
        mode="lines",
        fill="tozeroy",
        line={"color": "#F59E0B", "width": 2},
    )
)

# Add threshold lines
fig_imbalance.add_hline(
    y=5,
    line_dash="dot",
    line_color="orange",
    annotation_text="Warning (5%)",
    annotation_position="right",
)

fig_imbalance.add_hline(
    y=10,
    line_dash="dot",
    line_color="red",
    annotation_text="Critical (10%)",
    annotation_position="right",
)

fig_imbalance.update_layout(
    xaxis_title="Time",
    yaxis_title="Imbalance (%)",
    hovermode="x unified",
    height=400,
)

st.plotly_chart(fig_imbalance, use_container_width=True)

# ── Phase Power Distribution ──────────────────────────────────────────────────
if all(col in df.columns for col in ["kW1", "kW2", "kW3"]):
    st.markdown("---")
    st.subheader("⚡ Phase Power Distribution")

    avg_kw1 = df["kW1"].mean()
    avg_kw2 = df["kW2"].mean()
    avg_kw3 = df["kW3"].mean()
    total_avg_kw = avg_kw1 + avg_kw2 + avg_kw3

    # Power distribution pie chart
    fig_power_dist = go.Figure(
        data=[
            go.Pie(
                labels=["Phase 1", "Phase 2", "Phase 3"],
                values=[avg_kw1, avg_kw2, avg_kw3],
                marker={"colors": ["#EF4444", "#3B82F6", "#10B981"]},
                hole=0.4,
            )
        ]
    )

    fig_power_dist.update_layout(
        title="Average Power Distribution by Phase",
        annotations=[
            {"text": f"{total_avg_kw:.1f} kW<br>Total", "x": 0.5, "y": 0.5, "font_size": 16, "showarrow": False}
        ],
        height=400,
    )

    col1, col2 = st.columns([1, 1])

    with col1:
        st.plotly_chart(fig_power_dist, use_container_width=True)

    with col2:
        st.markdown("### Phase Power Statistics")
        power_data = pd.DataFrame(
            {
                "Phase": ["Phase 1", "Phase 2", "Phase 3"],
                "Avg Power (kW)": [avg_kw1, avg_kw2, avg_kw3],
                "% of Total": [
                    (avg_kw1 / total_avg_kw * 100) if total_avg_kw > 0 else 0,
                    (avg_kw2 / total_avg_kw * 100) if total_avg_kw > 0 else 0,
                    (avg_kw3 / total_avg_kw * 100) if total_avg_kw > 0 else 0,
                ],
                "Peak (kW)": [df["kW1"].max(), df["kW2"].max(), df["kW3"].max()],
            }
        )

        st.dataframe(
            power_data.style.background_gradient(subset=["Avg Power (kW)"], cmap="RdYlGn_r").format(
                {"Avg Power (kW)": "{:.2f}", "% of Total": "{:.1f}%", "Peak (kW)": "{:.2f}"}
            ),
            use_container_width=True,
            hide_index=True,
        )

# ── Voltage Balance Analysis ──────────────────────────────────────────────────
if all(col in df.columns for col in ["Voltage V1-N", "Voltage V2-N", "Voltage V3-N"]):
    st.markdown("---")
    st.subheader("🔌 Phase Voltage Balance")

    avg_v1 = df["Voltage V1-N"].mean()
    avg_v2 = df["Voltage V2-N"].mean()
    avg_v3 = df["Voltage V3-N"].mean()
    avg_voltage = (avg_v1 + avg_v2 + avg_v3) / 3

    max_v_deviation = max(abs(avg_v1 - avg_voltage), abs(avg_v2 - avg_voltage), abs(avg_v3 - avg_voltage))
    voltage_imbalance_pct = (max_v_deviation / avg_voltage * 100) if avg_voltage > 0 else 0

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Phase 1 Avg", f"{avg_v1:.1f} V")
    col2.metric("Phase 2 Avg", f"{avg_v2:.1f} V")
    col3.metric("Phase 3 Avg", f"{avg_v3:.1f} V")
    col4.metric(
        "Voltage Imbalance",
        f"{voltage_imbalance_pct:.2f}%",
        delta="Warning" if voltage_imbalance_pct > 2 else "OK",
        delta_color="inverse" if voltage_imbalance_pct > 2 else "normal",
    )

    if voltage_imbalance_pct > 2:
        st.warning(
            f"⚠️ Voltage imbalance of {voltage_imbalance_pct:.2f}% detected. "
            "Imbalance >2% can affect sensitive equipment."
        )

    # Voltage trends
    fig_voltages = go.Figure()

    v_colors = {"Voltage V1-N": "#EF4444", "Voltage V2-N": "#3B82F6", "Voltage V3-N": "#10B981"}
    for phase in ["Voltage V1-N", "Voltage V2-N", "Voltage V3-N"]:
        fig_voltages.add_trace(
            go.Scatter(
                x=df["timestamp"],
                y=df[phase],
                name=phase.replace("Voltage ", "Phase ").replace("-N", ""),
                mode="lines",
                line={"color": v_colors[phase], "width": 2},
            )
        )

    fig_voltages.update_layout(
        xaxis_title="Time",
        yaxis_title="Voltage (V)",
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "xanchor": "center", "x": 0.5},
        hovermode="x unified",
        height=400,
    )

    st.plotly_chart(fig_voltages, use_container_width=True)

# ── Recommendations ───────────────────────────────────────────────────────────
st.markdown("---")
st.subheader("💡 Recommendations")

recommendations = []

if imbalance_pct > 10:
    recommendations.append(
        "🚨 **URGENT**: Current imbalance exceeds 10%. Redistribute loads immediately to prevent equipment damage."
    )
elif imbalance_pct > 5:
    recommendations.append("⚠️ Consider redistributing loads across phases to reduce imbalance below 5%.")

if "Neutral Current" in df.columns and df["Neutral Current"].mean() > avg_current * 0.2:
    recommendations.append(
        "⚠️ High neutral current detected (>20% of average phase current). "
        "This indicates harmonics or severe imbalance."
    )

if all(col in df.columns for col in ["kW1", "kW2", "kW3"]):
    # Check if one phase has significantly more load
    max_phase_kw = max(avg_kw1, avg_kw2, avg_kw3)
    min_phase_kw = min(avg_kw1, avg_kw2, avg_kw3)
    if max_phase_kw > min_phase_kw * 1.5:
        heaviest_phase = ["Phase 1", "Phase 2", "Phase 3"][[avg_kw1, avg_kw2, avg_kw3].index(max_phase_kw)]
        recommendations.append(
            f"⚠️ {heaviest_phase} carries significantly more load than other phases. "
            "Consider moving some loads to balance distribution."
        )

if voltage_imbalance_pct > 2:
    recommendations.append(
        "⚠️ Voltage imbalance >2% detected. This may indicate utility supply issues or internal wiring problems."
    )

if not recommendations:
    recommendations.append("✅ System is well-balanced. Continue monitoring for changes.")

for rec in recommendations:
    st.info(rec)

# ── Technical Information ─────────────────────────────────────────────────────
with st.expander("ℹ️ Understanding Phase Imbalance"):
    st.markdown("""
    ### What is Phase Imbalance?

    In a 3-phase electrical system, ideally each phase should carry equal loads. **Phase imbalance** occurs when
    the loads are not evenly distributed across the three phases.

    ### Why It Matters:

    **Current Imbalance Effects:**
    - **<5%**: Normal operating range
    - **5-10%**: Reduced efficiency, increased losses
    - **>10%**: Risk of equipment damage, overheating, motor failure

    **Common Causes:**
    - Uneven distribution of single-phase loads
    - Failed equipment on one phase
    - Faulty motors or drives
    - Incorrect wiring

    ### Calculation Method:

    ```
    Average Current = (I1 + I2 + I3) / 3
    Max Deviation = max(|I1 - Avg|, |I2 - Avg|, |I3 - Avg|)
    Imbalance % = (Max Deviation / Average Current) × 100
    ```

    ### Neutral Current:

    In a balanced 3-phase system, the neutral current should be near zero. High neutral current indicates:
    - Phase imbalance
    - Harmonic distortion (especially 3rd harmonics)
    - Potential overheating of neutral conductor
    """)
