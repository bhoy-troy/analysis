import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# Add parent directory to path to import utils
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

st.set_page_config(page_title="Load Forecasting", layout="wide")

# ── Session State Validation ──────────────────────────────────────────────────
if "df" not in st.session_state or not st.session_state.get("data_loaded", False):
    st.error("⚠️ No data loaded. Please return to the main page and load data first.")
    st.stop()

# Get variables from session state
df = st.session_state.df
MIC = st.session_state.MIC
demand_warning_pct = st.session_state.demand_warning_pct

# ── Tab 5: Load Forecasting ───────────────────────────────────────────────────
if "Total kW" in df.columns and len(df) > 48:  # Need at least 2 days of data
    st.subheader("⚡ 7-Day Load Forecasting")

    try:
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
                            st.info(f"📈 Load predicted to increase by {avg_change:.1f}% compared to current average")
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
