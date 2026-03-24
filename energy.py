import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

MIC_DEFAULT = 290

st.set_page_config(page_title="Energy Dashboard", layout="wide")
st.title("Energy Usage Dashboard")
st.caption("Connected Resource & Energy Intelligence Monitoring")

# ── Sidebar ───────────────────────────────────────────────────────────────────
st.sidebar.header("Configuration")
MIC = st.sidebar.number_input("MIC (Maximum Import Capacity) kW", value=MIC_DEFAULT, step=10)
demand_warning_pct = st.sidebar.slider("Demand warning threshold (% of MIC)", 70, 95, 80)
pf_target = st.sidebar.slider("Power factor target", 0.80, 1.00, 0.90, step=0.01)
st.sidebar.markdown("---")
st.sidebar.markdown(
    "**CSV format required:**\n"
    "```\nregister_num,name,value,timestamp\n"
    "30042,Total kW,150.51,1769619345\n```\n"
    "Timestamps can be Unix epoch (seconds) or ISO datetime."
)

# ── File upload ───────────────────────────────────────────────────────────────
uploaded = st.file_uploader("Upload energy CSV", type=["csv"])

if uploaded is None:
    st.info("Upload a CSV to get started. Expected columns: `register_num`, `name`, `value`, `timestamp`")
    st.stop()

raw = pd.read_csv(uploaded)

required_cols = {"name", "value", "timestamp"}
if not required_cols.issubset(raw.columns):
    st.error(f"Missing columns: {required_cols - set(raw.columns)}")
    st.stop()


# ── Parse timestamps (Unix epoch seconds or ISO string) ──────────────────────
def parse_timestamps(series: pd.Series) -> pd.Series:
    sample = str(series.iloc[0]).strip()
    try:
        val = float(sample)
        if val > 1e12:
            return pd.to_datetime(series.astype(float), unit="ms", utc=True).dt.tz_localize(None)
        else:
            return pd.to_datetime(series.astype(float), unit="s", utc=True).dt.tz_localize(None)
    except ValueError:
        return pd.to_datetime(series)


raw["timestamp"] = parse_timestamps(raw["timestamp"])

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
tab1, tab2, tab3, tab4, tab5 = st.tabs(["Energy Overview", "Power Factor", "Peak Demand", "Load Heatmap", "Raw Data"])

with tab1:
    st.subheader("Energy profile — kW, kVA, kVAr & Max Demand")
    fig = go.Figure()
    for col, dash in [
        ("Total kW", "solid"),
        ("Total kVA", "solid"),
        ("Total kVAr", "solid"),
        ("Max Demand kW", "dash"),
    ]:
        if col in df.columns:
            fig.add_trace(
                go.Scatter(x=df["timestamp"], y=df[col], name=col, mode="lines", line={"width": 2, "dash": dash})
            )
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
    fig.update_layout(
        xaxis={"title": "Timestamp"},
        yaxis={"title": "Power (kW / kVA / kVAr)"},
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "xanchor": "center", "x": 0.5},
        hovermode="x unified",
    )
    st.plotly_chart(fig, use_container_width=True)

with tab2:
    if "Average PF" in df.columns:
        st.subheader("Power factor over time")
        fig2 = go.Figure()
        fig2.add_trace(
            go.Scatter(
                x=df["timestamp"], y=df["Average PF"], mode="lines", fill="tozeroy", name="Avg PF", line={"width": 2}
            )
        )
        fig2.add_hline(
            y=pf_target,
            line_dash="dot",
            line_color="orange",
            annotation_text=f"Target {pf_target}",
            annotation_position="top left",
        )
        fig2.update_layout(
            xaxis={"title": "Timestamp"},
            yaxis={"title": "Power Factor", "range": [0.6, 1.05], "dtick": 0.05},
            hovermode="x unified",
        )
        st.plotly_chart(fig2, use_container_width=True)

        st.subheader("Power factor distribution")
        fig_hist = px.histogram(df, x="Average PF", nbins=40)
        fig_hist.add_vline(x=pf_target, line_dash="dot", line_color="orange", annotation_text=f"Target {pf_target}")
        fig_hist.update_layout(xaxis_title="Power Factor", yaxis_title="Count")
        st.plotly_chart(fig_hist, use_container_width=True)

with tab3:
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

with tab4:
    if "Total kW" in df.columns:
        st.subheader("Load heatmap — avg kW by hour and day")
        df["date"] = df["timestamp"].dt.date
        df["hour"] = df["timestamp"].dt.hour
        pivot = df.pivot_table(values="Total kW", index="date", columns="hour", aggfunc="mean")
        if pivot.shape[0] >= 2:
            fig5 = px.imshow(
                pivot,
                aspect="auto",
                color_continuous_scale="RdYlGn_r",
                labels={"x": "Hour of Day", "y": "Date", "color": "Avg kW"},
            )
            st.plotly_chart(fig5, use_container_width=True)
        else:
            st.info("Upload more than one day of data to see the heatmap.")

with tab5:
    col_a, col_b = st.columns(2)
    with col_a:
        st.subheader("Raw uploaded data")
        st.dataframe(raw, use_container_width=True)
    with col_b:
        st.subheader("Pivoted (wide) data")
        st.dataframe(df, use_container_width=True)
    st.download_button(
        "Download pivoted data as CSV",
        data=df.to_csv(index=False).encode("utf-8"),
        file_name="energy_pivoted.csv",
        mime="text/csv",
    )
