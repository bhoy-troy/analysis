import pandas as pd
import numpy as np
import streamlit as st
from dataclasses import dataclass
from typing import Optional, List, Tuple


@dataclass
class PullDownResult:
    pull_down_time_min: Optional[float]
    start_temp: Optional[float]
    end_temp: Optional[float]


@dataclass
class StabilityResult:
    mean_temp: float
    std_temp: float


@dataclass
class SetpointAdherenceResult:
    fraction_in_band: float
    minutes_in_band: float


@dataclass
class WarmupResult:
    warmup_rate_c_per_min: Optional[float]


@dataclass
class DisturbanceRecoveryResult:
    avg_peak_rise_c: Optional[float]
    median_recovery_time_min: Optional[float]
    n_events: int


@dataclass
class PerformanceIndex:
    index: Optional[float]


def compute_pull_down(df: pd.DataFrame, setpoint: float, band: float) -> PullDownResult:
    temps = df["temperature"].values
    times = df["timestamp"].values
    if len(temps) == 0:
        return PullDownResult(None, None, None)
    start_temp = float(temps[0])
    target = setpoint + band
    idx = np.where(temps <= target)[0]
    if len(idx) == 0:
        return PullDownResult(None, start_temp, None)
    t0 = pd.Timestamp(times[0])
    t_target = pd.Timestamp(times[idx[0]])
    pull_down_time = (t_target - t0).total_seconds() / 60.0
    return PullDownResult(pull_down_time, start_temp, float(temps[idx[0]]))


def compute_stability(df: pd.DataFrame) -> StabilityResult:
    temps = df["temperature"].values
    return StabilityResult(float(np.mean(temps)), float(np.std(temps)))


def compute_setpoint_adherence(
        df: pd.DataFrame, setpoint: float, band: float
) -> SetpointAdherenceResult:
    temps = df["temperature"].values
    times = df["timestamp"].values
    lower = setpoint - band
    upper = setpoint + band
    in_band = (temps >= lower) & (temps <= upper)
    if len(times) < 2:
        return SetpointAdherenceResult(0.0, 0.0)
    dt_minutes = np.median(
        np.diff(times).astype("timedelta64[s]").astype(float)
    ) / 60.0
    minutes_in_band = float(in_band.sum() * dt_minutes)
    fraction_in_band = float(in_band.mean())
    return SetpointAdherenceResult(fraction_in_band, minutes_in_band)


def detect_warmup_segment(
        df: pd.DataFrame, window_min: int = 60
) -> Optional[pd.DataFrame]:
    if len(df) < 3:
        return None
    temps = df["temperature"].values
    times = df["timestamp"].values
    dt_minutes = np.median(
        np.diff(times).astype("timedelta64[s]").astype(float)
    ) / 60.0
    if dt_minutes <= 0:
        return None
    n_window = int(window_min / dt_minutes)
    if n_window < 3 or n_window > len(df):
        return None
    best_start, best_end = None, None
    current_start = 0
    for i in range(1, len(temps)):
        if temps[i] <= temps[i - 1]:
            if i - current_start >= n_window:
                if best_start is None or (i - 1 - current_start) > (best_end - best_start):
                    best_start, best_end = current_start, i - 1
            current_start = i
    if len(temps) - current_start >= n_window:
        if best_start is None or (len(temps) - 1 - current_start) > (best_end - best_start):
            best_start, best_end = current_start, len(temps) - 1
    if best_start is None or best_end is None:
        return None
    return df.iloc[best_start:best_end + 1].copy()


def compute_warmup_rate(df: pd.DataFrame, window_min: int = 60) -> WarmupResult:
    seg = detect_warmup_segment(df, window_min=window_min)
    if seg is None or len(seg) < 3:
        return WarmupResult(None)
    temps = seg["temperature"].values
    times = seg["timestamp"].values
    t0 = times[0]
    t_minutes = np.array(
        [(t - t0).astype("timedelta64[s]").astype(float) / 60.0 for t in times]
    )
    coeffs = np.polyfit(t_minutes, temps, 1)
    return WarmupResult(float(coeffs[0]))


def detect_disturbances(
        df: pd.DataFrame, threshold_c: float = 2.0, min_gap_min: float = 10.0
) -> List[Tuple[int, int]]:
    temps = df["temperature"].values
    times = df["timestamp"].values
    if len(temps) < 3:
        return []
    dt_minutes = np.median(
        np.diff(times).astype("timedelta64[s]").astype(float)
    ) / 60.0
    if dt_minutes <= 0:
        return []
    min_gap_steps = int(min_gap_min / dt_minutes)
    events: List[Tuple[int, int]] = []
    last_end = -min_gap_steps
    baseline = pd.Series(temps).rolling(window=30, min_periods=10).median().to_numpy()
    i = 1
    while i < len(temps):
        if temps[i] - baseline[i] >= threshold_c and i - last_end >= min_gap_steps:
            start = i
            peak_idx = i
            while i + 1 < len(temps) and temps[i + 1] >= temps[i]:
                i += 1
                if temps[i] > temps[peak_idx]:
                    peak_idx = i
            while i + 1 < len(temps) and temps[i] - baseline[i] > 0.5:
                i += 1
            end = i
            events.append((start, end))
            last_end = end
        i += 1
    return events


def compute_disturbance_recovery(
        df: pd.DataFrame, threshold_c: float = 2.0
) -> DisturbanceRecoveryResult:
    events = detect_disturbances(df, threshold_c=threshold_c)
    if not events:
        return DisturbanceRecoveryResult(None, None, 0)
    temps = df["temperature"].values
    times = df["timestamp"].values
    baseline = pd.Series(temps).rolling(window=30, min_periods=10).median().to_numpy()
    peak_rises = []
    recovery_times = []
    for start, end in events:
        local_baseline = baseline[start]
        peak_temp = temps[start:end + 1].max()
        peak_rises.append(peak_temp - local_baseline)
        t_start = pd.Timestamp(times[start])
        t_end = pd.Timestamp(times[end])
        recovery_times.append((t_end - t_start).total_seconds() / 60.0)
    avg_peak_rise = float(np.mean(peak_rises)) if peak_rises else None
    median_recovery = float(np.median(recovery_times)) if recovery_times else None
    return DisturbanceRecoveryResult(avg_peak_rise, median_recovery, len(events))


def compute_performance_index(
        stability: StabilityResult,
        adherence: SetpointAdherenceResult,
        warmup: WarmupResult,
        disturbance: DisturbanceRecoveryResult,
) -> PerformanceIndex:
    std_norm = min(max(1.0 - stability.std_temp / 2.0, 0.0), 1.0)
    adherence_norm = min(max(adherence.fraction_in_band, 0.0), 1.0)
    warm_norm = (
        0.5
        if warmup.warmup_rate_c_per_min is None
        else min(max(1.0 - (warmup.warmup_rate_c_per_min - 0.01) / 0.09, 0.0), 1.0)
    )
    dist_norm = (
        0.5
        if disturbance.median_recovery_time_min is None
        else min(max(1.0 - (disturbance.median_recovery_time_min - 5.0) / 55.0, 0.0), 1.0)
    )
    weights = np.array([0.3, 0.3, 0.2, 0.2])
    comps = np.array([std_norm, adherence_norm, warm_norm, dist_norm])
    return PerformanceIndex(float(np.dot(weights, comps)))


# ── Page setup ────────────────────────────────────────────────────────────────

st.set_page_config(page_title="Cold Storage Performance", layout="wide")
st.title("Cold Storage Performance Dashboard")

# ── Sidebar ───────────────────────────────────────────────────────────────────

st.sidebar.header("Configuration")
unit_type = st.sidebar.selectbox("Unit type", ["Freezer", "Fridge"])
setpoint = st.sidebar.number_input(
    "Setpoint (°C)", value=-18.0 if unit_type == "Freezer" else 4.0, step=0.5
)
band = st.sidebar.number_input("Band ± (°C)", value=1.0, step=0.1)
warmup_window = st.sidebar.number_input("Warm-up window (min)", value=60, step=5)
dist_threshold = st.sidebar.number_input("Disturbance threshold (°C)", value=2.0, step=0.5)

st.sidebar.markdown("---")
st.sidebar.markdown(
    "**CSV format required:**\n```\ntimestamp,temperature\n2025-01-01T00:00:00,5.2\n```"
)

# ── File upload ───────────────────────────────────────────────────────────────

uploaded_file = st.file_uploader("Upload CSV file", type=["csv"])

if uploaded_file is None:
    st.info("Upload a CSV file with `timestamp` and `temperature` columns to get started.")
    st.stop()

df = pd.read_csv(uploaded_file)

if "timestamp" not in df.columns or "temperature" not in df.columns:
    st.error("CSV must contain 'timestamp' and 'temperature' columns.")
    st.stop()

df["timestamp"] = pd.to_datetime(df["timestamp"])
df = df.sort_values("timestamp").dropna(subset=["temperature"]).reset_index(drop=True)

# ── Compute metrics ───────────────────────────────────────────────────────────

pull = compute_pull_down(df, setpoint, band)
stab = compute_stability(df)
adh = compute_setpoint_adherence(df, setpoint, band)
warm = compute_warmup_rate(df, window_min=int(warmup_window))
dist = compute_disturbance_recovery(df, threshold_c=dist_threshold)
perf = compute_performance_index(stab, adh, warm, dist)

# ── Header summary ────────────────────────────────────────────────────────────

st.subheader(f"{unit_type} — {uploaded_file.name}")
st.caption(
    f"Setpoint: {setpoint} °C  |  Band: ±{band} °C  |  "
    f"Records: {len(df):,}  |  "
    f"From: {df['timestamp'].min().strftime('%Y-%m-%d %H:%M')}  "
    f"To: {df['timestamp'].max().strftime('%Y-%m-%d %H:%M')}"
)

# ── KPI tiles ─────────────────────────────────────────────────────────────────

c1, c2, c3, c4, c5 = st.columns(5)

with c1:
    st.metric(
        "Performance index",
        "N/A" if perf.index is None else f"{perf.index:.3f}",
        help="Composite 0–1 score (higher is better)"
    )
with c2:
    st.metric("Mean temp (°C)", f"{stab.mean_temp:.2f}")
    st.metric("Std dev (°C)", f"{stab.std_temp:.2f}")
with c3:
    st.metric("In-band time", f"{adh.fraction_in_band * 100:.1f}%")
    st.metric("Minutes in band", f"{adh.minutes_in_band:.0f}")
with c4:
    st.metric(
        "Pull-down time (min)",
        "N/A" if pull.pull_down_time_min is None else f"{pull.pull_down_time_min:.1f}"
    )
    st.metric(
        "Start temp (°C)",
        "N/A" if pull.start_temp is None else f"{pull.start_temp:.1f}"
    )
with c5:
    st.metric("Disturbance events", dist.n_events)
    st.metric(
        "Median recovery (min)",
        "N/A" if dist.median_recovery_time_min is None else f"{dist.median_recovery_time_min:.1f}"
    )

# ── Temperature chart ─────────────────────────────────────────────────────────

st.subheader("Temperature over time")
st.line_chart(df.set_index("timestamp")["temperature"])

# ── Warm-up rate ──────────────────────────────────────────────────────────────

st.subheader("Insulation / warm-up rate")
if warm.warmup_rate_c_per_min is not None:
    st.metric("Warm-up rate (°C/min)", f"{warm.warmup_rate_c_per_min:.4f}")
    st.caption("Lower = better insulation and door seals")
else:
    st.info("No clear warm-up segment detected in this dataset.")

# ── Disturbance detail ────────────────────────────────────────────────────────

st.subheader("Disturbance events")
if dist.n_events > 0:
    d1, d2, d3 = st.columns(3)
    d1.metric("Events detected", dist.n_events)
    d2.metric(
        "Avg peak rise (°C)",
        "N/A" if dist.avg_peak_rise_c is None else f"{dist.avg_peak_rise_c:.2f}"
    )
    d3.metric(
        "Median recovery (min)",
        "N/A" if dist.median_recovery_time_min is None else f"{dist.median_recovery_time_min:.1f}"
    )
else:
    st.info(f"No disturbance events detected above {dist_threshold} °C threshold.")

# ── Raw data + export ─────────────────────────────────────────────────────────

with st.expander("Raw data preview"):
    st.dataframe(df, use_container_width=True)

st.download_button(
    label="Download metrics summary as CSV",
    data=pd.DataFrame([{
        "unit_type": unit_type,
        "file": uploaded_file.name,
        "setpoint_c": setpoint,
        "band_c": band,
        "mean_temp_c": stab.mean_temp,
        "std_temp_c": stab.std_temp,
        "in_band_pct": adh.fraction_in_band * 100,
        "minutes_in_band": adh.minutes_in_band,
        "pull_down_min": pull.pull_down_time_min,
        "warmup_rate_c_per_min": warm.warmup_rate_c_per_min,
        "disturbance_events": dist.n_events,
        "avg_peak_rise_c": dist.avg_peak_rise_c,
        "median_recovery_min": dist.median_recovery_time_min,
        "performance_index": perf.index,
    }]).to_csv(index=False).encode("utf-8"),
    file_name="metrics_summary.csv",
    mime="text/csv",
)