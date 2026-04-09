"""
Analysis and calculation functions for temperature data.
"""

import pandas as pd


def detect_cooling_cycles(cabinet_data, temp_threshold=0.5):
    """
    Detect cooling cycles based on temperature oscillations.
    A cycle is defined as a period from one temperature peak to the next.
    """
    temps = cabinet_data["temperature_celsius"].values
    timestamps = cabinet_data["timestamp"].values

    # Find local maxima (peaks)
    peaks = []
    for i in range(1, len(temps) - 1):
        if temps[i] > temps[i - 1] and temps[i] > temps[i + 1]:
            # Check if this is a significant peak (not just noise)
            if i > 0 and (temps[i] - temps[i - 1] > 0.1 or temps[i] - temps[i + 1] > 0.1):
                peaks.append(i)

    # Calculate cycle durations
    cycles = []
    for i in range(len(peaks) - 1):
        cycle_start = timestamps[peaks[i]]
        cycle_end = timestamps[peaks[i + 1]]
        duration = (cycle_end - cycle_start) / pd.Timedelta(minutes=1)

        cycles.append(
            {
                "start_time": cycle_start,
                "end_time": cycle_end,
                "duration_minutes": duration,
                "start_temp": temps[peaks[i]],
                "min_temp": temps[peaks[i] : peaks[i + 1]].min(),
                "temp_range": temps[peaks[i]] - temps[peaks[i] : peaks[i + 1]].min(),
            }
        )

    return pd.DataFrame(cycles)


def detect_defrost_cycles(cabinet_data, is_freezer=True):
    """
    Detect defrost cycles based on significant temperature spikes.
    For freezers: normal operating range is around -18 to -25°C,
    defrost causes temp to spike above -10°C or rise rapidly.
    """
    temps = cabinet_data["temperature_celsius"].values
    timestamps = cabinet_data["timestamp"].values

    # Determine thresholds based on cabinet type
    if is_freezer:
        # For freezers, defrost typically brings temp above -10°C
        defrost_threshold = -10
        normal_operating_max = -15
    else:
        # For chillers, defrost might bring temp above 10°C
        defrost_threshold = 10
        normal_operating_max = 8

    defrost_cycles = []
    in_defrost = False
    defrost_start = None
    defrost_start_temp = None
    max_defrost_temp = None

    for i in range(len(temps)):
        if not in_defrost and temps[i] > defrost_threshold:
            # Start of defrost cycle
            in_defrost = True
            defrost_start = timestamps[i]
            defrost_start_temp = temps[i - 1] if i > 0 else temps[i]
            max_defrost_temp = temps[i]
        elif in_defrost:
            # Update max temperature during defrost
            if temps[i] > max_defrost_temp:
                max_defrost_temp = temps[i]

            # Check if defrost has ended (temp drops back below normal max)
            if temps[i] < normal_operating_max:
                defrost_end = timestamps[i]
                duration = (defrost_end - defrost_start) / pd.Timedelta(minutes=1)

                defrost_cycles.append(
                    {
                        "start_time": defrost_start,
                        "end_time": defrost_end,
                        "duration_minutes": duration,
                        "start_temp": defrost_start_temp,
                        "max_temp": max_defrost_temp,
                        "end_temp": temps[i],
                        "temp_rise": max_defrost_temp - defrost_start_temp,
                    }
                )

                in_defrost = False

    return pd.DataFrame(defrost_cycles)


def calculate_recovery_time(cabinet_data, defrost_cycles, is_freezer=True):
    """
    Calculate recovery time after each defrost cycle.
    Recovery is the time to return to normal operating temperature.
    """
    if len(defrost_cycles) == 0:
        return pd.DataFrame()

    # Define recovery target temperature
    if is_freezer:
        recovery_target = -18  # Target temp for freezers
    else:
        recovery_target = 5  # Target temp for chillers

    recovery_data = []

    for _idx, defrost in defrost_cycles.iterrows():
        # Ensure end_time is timezone-aware to match timestamp column
        end_time = pd.Timestamp(defrost["end_time"])
        if cabinet_data["timestamp"].dt.tz is not None:
            end_time = end_time.tz_localize(cabinet_data["timestamp"].dt.tz)

        # Get data after defrost end
        post_defrost = cabinet_data[cabinet_data["timestamp"] > end_time].copy()

        if len(post_defrost) == 0:
            continue

        # Find when temperature reaches recovery target
        recovered = post_defrost[post_defrost["temperature_celsius"] <= recovery_target]

        if len(recovered) > 0:
            recovery_time = recovered.iloc[0]["timestamp"]
            recovery_duration = (recovery_time - end_time) / pd.Timedelta(minutes=1)

            recovery_data.append(
                {
                    "defrost_start": defrost["start_time"],
                    "defrost_end": defrost["end_time"],
                    "recovery_time": recovery_time,
                    "recovery_duration_minutes": recovery_duration,
                    "end_temp": defrost["end_temp"],
                    "target_temp": recovery_target,
                }
            )

    return pd.DataFrame(recovery_data)


def calculate_time_in_range(cabinet_data, is_freezer=True):
    """
    Calculate percentage of time spent in different temperature ranges.
    """
    if is_freezer:
        optimal_min, optimal_max = -25, -18
        critical_threshold = -10
    else:
        optimal_min, optimal_max = 0, 5
        critical_threshold = 8

    total_readings = len(cabinet_data)

    optimal = len(
        cabinet_data[
            (cabinet_data["temperature_celsius"] >= optimal_min) & (cabinet_data["temperature_celsius"] <= optimal_max)
        ]
    )

    warning = len(
        cabinet_data[
            (cabinet_data["temperature_celsius"] > optimal_max)
            & (cabinet_data["temperature_celsius"] <= critical_threshold)
        ]
    )

    critical = len(cabinet_data[cabinet_data["temperature_celsius"] > critical_threshold])

    below_optimal = len(cabinet_data[cabinet_data["temperature_celsius"] < optimal_min])

    return {
        "optimal_pct": (optimal / total_readings) * 100,
        "warning_pct": (warning / total_readings) * 100,
        "critical_pct": (critical / total_readings) * 100,
        "below_optimal_pct": (below_optimal / total_readings) * 100,
        "optimal_range": f"{optimal_min}°C to {optimal_max}°C",
        "warning_range": f"{optimal_max}°C to {critical_threshold}°C",
        "critical_threshold": f"Above {critical_threshold}°C",
    }


def calculate_health_score(cabinet_data, is_freezer=True):
    """
    Calculate equipment health score based on multiple factors.
    Returns a score from 0-100 (100 = excellent health).
    """
    scores = []
    weights = []

    # 1. Temperature stability (30% weight)
    temp_std = cabinet_data["temperature_celsius"].std()
    if is_freezer:
        # Good stability is < 1°C std dev, poor is > 3°C
        stability_score = max(0, min(100, 100 - (temp_std - 0.5) * 33))
    else:
        stability_score = max(0, min(100, 100 - (temp_std - 0.5) * 33))
    scores.append(stability_score)
    weights.append(30)

    # 2. Time in optimal range (35% weight)
    time_range = calculate_time_in_range(cabinet_data, is_freezer)
    range_score = time_range["optimal_pct"]
    scores.append(range_score)
    weights.append(35)

    # 3. Temperature trend (20% weight)
    # Check if average temperature is creeping up over time
    cabinet_data_sorted = cabinet_data.sort_values("timestamp")
    first_half = cabinet_data_sorted.iloc[: len(cabinet_data_sorted) // 2]["temperature_celsius"].mean()
    second_half = cabinet_data_sorted.iloc[len(cabinet_data_sorted) // 2 :]["temperature_celsius"].mean()
    temp_drift = second_half - first_half

    if is_freezer:
        # For freezers, warming trend is bad
        if temp_drift > 2:
            trend_score = 0
        elif temp_drift > 1:
            trend_score = 50
        else:
            trend_score = 100
    else:
        if temp_drift > 2:
            trend_score = 0
        elif temp_drift > 1:
            trend_score = 50
        else:
            trend_score = 100
    scores.append(trend_score)
    weights.append(20)

    # 4. Critical events (15% weight)
    critical_pct = time_range["critical_pct"]
    critical_score = max(0, 100 - (critical_pct * 10))  # Penalize critical temps heavily
    scores.append(critical_score)
    weights.append(15)

    # Calculate weighted average
    total_weight = sum(weights)
    health_score = sum(s * w for s, w in zip(scores, weights, strict=False)) / total_weight

    return {
        "overall_score": health_score,
        "stability_score": stability_score,
        "range_score": range_score,
        "trend_score": trend_score,
        "critical_score": critical_score,
        "temp_std": temp_std,
        "temp_drift": temp_drift,
    }


def get_health_status(score):
    """Get health status and color based on score"""
    if score >= 90:
        return "Excellent", "🟢", "green"
    elif score >= 75:
        return "Good", "🟡", "orange"
    elif score >= 60:
        return "Fair", "🟠", "darkorange"
    else:
        return "Poor", "🔴", "red"
