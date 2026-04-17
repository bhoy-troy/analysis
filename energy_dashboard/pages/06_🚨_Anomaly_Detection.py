import sys
from datetime import UTC, datetime
from pathlib import Path

import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# Add parent directory to path to import utils
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

st.set_page_config(page_title="Anomaly Detection", layout="wide")

# ── Session State Validation ──────────────────────────────────────────────────
if "df" not in st.session_state or not st.session_state.get("data_loaded", False):
    st.error("⚠️ No data loaded. Please return to the main page and load data first.")
    st.stop()

# Get variables from session state
df = st.session_state.df

# ── Tab 6: Anomaly Detection ──────────────────────────────────────────────────
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

        fig_anomaly.update_layout(xaxis_title="Date/Time", yaxis_title="Power (kW)", hovermode="closest", height=400)

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
