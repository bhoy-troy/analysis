from datetime import datetime, timedelta
from io import BytesIO

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak, Image
from reportlab.lib.enums import TA_CENTER
import tempfile
import os

st.set_page_config(page_title="Supermarket Cabinet Temperature Analysis", layout="wide")


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

    for idx, defrost in defrost_cycles.iterrows():
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
        warning_min, warning_max = -15, -10
        critical_threshold = -10
    else:
        optimal_min, optimal_max = 0, 5
        warning_min, warning_max = 5, 8
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
    health_score = sum(s * w for s, w in zip(scores, weights)) / total_weight

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

def generate_pdf_report(cabinet_name, cabinet_data, is_freezer):
    """
    Generate a comprehensive PDF report for the selected cabinet.
    """
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=0.5*inch, bottomMargin=0.5*inch)
    story = []
    styles = getSampleStyleSheet()

    # Initialize temp file paths
    temp_dist_path = None
    health_chart_path = None
    cycles_chart_path = None
    defrost_chart_path = None
    recovery_chart_path = None
    compliance_chart_path = None
    trend_chart_path = None
    daily_chart_path = None

    # Custom styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#1f77b4'),
        spaceAfter=30,
        alignment=TA_CENTER
    )

    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=16,
        textColor=colors.HexColor('#2c3e50'),
        spaceAfter=12,
        spaceBefore=12
    )

    # Title
    story.append(Paragraph(f"Temperature Analysis Report", title_style))
    story.append(Paragraph(f"Cabinet: {cabinet_name}", styles['Heading2']))
    story.append(Paragraph(f"Report Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", styles['Normal']))
    story.append(Spacer(1, 0.3*inch))

    # Executive Summary
    story.append(Paragraph("Executive Summary", heading_style))

    health_data = calculate_health_score(cabinet_data, is_freezer)
    status, _, _ = get_health_status(health_data['overall_score'])
    time_range = calculate_time_in_range(cabinet_data, is_freezer)

    summary_data = [
        ['Metric', 'Value'],
        ['Health Status', status],
        ['Health Score', f"{health_data['overall_score']:.1f}/100"],
        ['Average Temperature', f"{cabinet_data['temperature_celsius'].mean():.2f}°C"],
        ['Temperature Range', f"{cabinet_data['temperature_celsius'].min():.2f}°C to {cabinet_data['temperature_celsius'].max():.2f}°C"],
        ['Temperature Std Dev', f"{health_data['temp_std']:.2f}°C"],
        ['Time in Optimal Range', f"{time_range['optimal_pct']:.1f}%"],
        ['Time in Critical Range', f"{time_range['critical_pct']:.1f}%"],
        ['Total Readings', f"{len(cabinet_data):,}"],
        ['Date Range', f"{cabinet_data['timestamp'].min().strftime('%Y-%m-%d')} to {cabinet_data['timestamp'].max().strftime('%Y-%m-%d')}"]
    ]

    summary_table = Table(summary_data, colWidths=[3*inch, 3*inch])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3498db')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey])
    ]))

    story.append(summary_table)
    story.append(Spacer(1, 0.3*inch))

    # Temperature Distribution Chart
    story.append(Paragraph("Temperature Distribution", heading_style))

    fig_temp_dist = px.histogram(
        cabinet_data,
        x='temperature_celsius',
        nbins=50,
        title=f"Temperature Distribution - {cabinet_name}",
        labels={'temperature_celsius': 'Temperature (°C)', 'count': 'Frequency'}
    )
    fig_temp_dist.update_layout(width=700, height=400, showlegend=False)

    # Save chart as image
    temp_dist_path = tempfile.NamedTemporaryFile(delete=False, suffix='.png').name
    fig_temp_dist.write_image(temp_dist_path, width=700, height=400)

    img_temp_dist = Image(temp_dist_path, width=6*inch, height=3.4*inch)
    story.append(img_temp_dist)
    story.append(Spacer(1, 0.3*inch))

    # Health Score Breakdown
    story.append(Paragraph("Health Score Breakdown", heading_style))

    health_breakdown = [
        ['Component', 'Score', 'Weight'],
        ['Temperature Stability', f"{health_data['stability_score']:.0f}/100", '30%'],
        ['Time-in-Range', f"{health_data['range_score']:.0f}/100", '35%'],
        ['Trend Analysis', f"{health_data['trend_score']:.0f}/100", '20%'],
        ['Critical Events Avoidance', f"{health_data['critical_score']:.0f}/100", '15%'],
    ]

    health_table = Table(health_breakdown, colWidths=[2.5*inch, 2*inch, 1.5*inch])
    health_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2ecc71')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 11),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey])
    ]))

    story.append(health_table)
    story.append(Spacer(1, 0.3*inch))

    # Health Score Visualization
    factors_df_chart = pd.DataFrame({
        'Factor': ['Stability\n(30%)', 'Time-in-Range\n(35%)', 'Trend\n(20%)', 'Critical Events\n(15%)'],
        'Score': [
            health_data['stability_score'],
            health_data['range_score'],
            health_data['trend_score'],
            health_data['critical_score']
        ]
    })

    fig_health = px.bar(
        factors_df_chart,
        x='Factor',
        y='Score',
        title="Health Score Components",
        color='Score',
        color_continuous_scale=['red', 'orange', 'yellow', 'green'],
        range_color=[0, 100]
    )
    fig_health.update_layout(width=700, height=400, yaxis_range=[0, 100], showlegend=False)
    fig_health.update_traces(text=factors_df_chart['Score'].apply(lambda x: f'{x:.0f}'), textposition='outside')

    health_chart_path = tempfile.NamedTemporaryFile(delete=False, suffix='.png').name
    fig_health.write_image(health_chart_path, width=700, height=400)

    img_health = Image(health_chart_path, width=6*inch, height=3.4*inch)
    story.append(img_health)
    story.append(Spacer(1, 0.3*inch))

    # Cooling Cycles Analysis
    story.append(Paragraph("Cooling Cycles Analysis", heading_style))
    cycles_df = detect_cooling_cycles(cabinet_data)

    if len(cycles_df) > 0:
        cycles_df['date'] = pd.to_datetime(cycles_df['start_time']).dt.date
        cycles_per_day = cycles_df.groupby('date').size()

        cycles_summary = [
            ['Metric', 'Value'],
            ['Total Cycles Detected', f"{len(cycles_df)}"],
            ['Average Cycles per Day', f"{cycles_per_day.mean():.1f}"],
            ['Average Cycle Duration', f"{cycles_df['duration_minutes'].mean():.1f} minutes"],
            ['Min Cycle Duration', f"{cycles_df['duration_minutes'].min():.1f} minutes"],
            ['Max Cycle Duration', f"{cycles_df['duration_minutes'].max():.1f} minutes"],
            ['Average Temperature Range', f"{cycles_df['temp_range'].mean():.2f}°C"],
        ]

        cycles_table = Table(cycles_summary, colWidths=[3*inch, 3*inch])
        cycles_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#9b59b6')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey])
        ]))

        story.append(cycles_table)
        story.append(Spacer(1, 0.2*inch))

        # Cooling Cycles Chart
        cycles_df['date'] = pd.to_datetime(cycles_df['start_time']).dt.date
        cycles_per_day = cycles_df.groupby('date').size().reset_index(name='cycle_count')

        fig_cycles = px.bar(
            cycles_per_day,
            x='date',
            y='cycle_count',
            title="Cooling Cycles per Day",
            labels={'date': 'Date', 'cycle_count': 'Number of Cycles'}
        )
        fig_cycles.update_layout(width=700, height=400, showlegend=False)

        cycles_chart_path = tempfile.NamedTemporaryFile(delete=False, suffix='.png').name
        fig_cycles.write_image(cycles_chart_path, width=700, height=400)

        img_cycles = Image(cycles_chart_path, width=6*inch, height=3.4*inch)
        story.append(img_cycles)
    else:
        story.append(Paragraph("No cooling cycles detected.", styles['Normal']))

    story.append(Spacer(1, 0.3*inch))

    # Defrost Cycles Analysis
    story.append(Paragraph("Defrost Cycles Analysis", heading_style))
    defrost_df = detect_defrost_cycles(cabinet_data, is_freezer)
    recovery_df = pd.DataFrame()  # Initialize

    if len(defrost_df) > 0:
        defrost_summary = [
            ['Metric', 'Value'],
            ['Total Defrost Cycles', f"{len(defrost_df)}"],
            ['Average Defrost Duration', f"{defrost_df['duration_minutes'].mean():.1f} minutes"],
            ['Average Temperature Rise', f"{defrost_df['temp_rise'].mean():.2f}°C"],
            ['Max Temperature During Defrost', f"{defrost_df['max_temp'].max():.2f}°C"],
        ]

        defrost_table = Table(defrost_summary, colWidths=[3*inch, 3*inch])
        defrost_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e74c3c')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey])
        ]))

        story.append(defrost_table)
        story.append(Spacer(1, 0.2*inch))

        # Defrost Cycles Chart
        defrost_df['date'] = pd.to_datetime(defrost_df['start_time']).dt.date
        defrost_per_day = defrost_df.groupby('date').size().reset_index(name='defrost_count')

        fig_defrost = px.bar(
            defrost_per_day,
            x='date',
            y='defrost_count',
            title="Defrost Cycles per Day",
            labels={'date': 'Date', 'defrost_count': 'Number of Defrost Cycles'}
        )
        fig_defrost.update_layout(width=700, height=400, showlegend=False)

        defrost_chart_path = tempfile.NamedTemporaryFile(delete=False, suffix='.png').name
        fig_defrost.write_image(defrost_chart_path, width=700, height=400)

        img_defrost = Image(defrost_chart_path, width=6*inch, height=3.4*inch)
        story.append(img_defrost)
        story.append(Spacer(1, 0.3*inch))

        # Recovery Time Analysis
        recovery_df = calculate_recovery_time(cabinet_data, defrost_df, is_freezer)

        if len(recovery_df) > 0:
            story.append(Paragraph("Defrost Recovery Analysis", heading_style))

            recovery_summary = [
                ['Metric', 'Value'],
                ['Average Recovery Time', f"{recovery_df['recovery_duration_minutes'].mean():.1f} minutes"],
                ['Min Recovery Time', f"{recovery_df['recovery_duration_minutes'].min():.1f} minutes"],
                ['Max Recovery Time', f"{recovery_df['recovery_duration_minutes'].max():.1f} minutes"],
            ]

            recovery_table = Table(recovery_summary, colWidths=[3*inch, 3*inch])
            recovery_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#16a085')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey])
            ]))

            story.append(recovery_table)
            story.append(Spacer(1, 0.2*inch))

            # Recovery Time Chart
            recovery_display = recovery_df.copy()
            recovery_display['defrost_start'] = pd.to_datetime(recovery_display['defrost_start'])

            fig_recovery = px.scatter(
                recovery_display,
                x='defrost_start',
                y='recovery_duration_minutes',
                title="Defrost Recovery Time Over Time",
                labels={'defrost_start': 'Date', 'recovery_duration_minutes': 'Recovery Time (minutes)'}
            )
            fig_recovery.add_hline(y=40, line_dash="dash", line_color="orange", annotation_text="Warning (40 min)")
            fig_recovery.add_hline(y=60, line_dash="dash", line_color="red", annotation_text="Critical (60 min)")
            fig_recovery.update_layout(width=700, height=400)

            recovery_chart_path = tempfile.NamedTemporaryFile(delete=False, suffix='.png').name
            fig_recovery.write_image(recovery_chart_path, width=700, height=400)

            img_recovery = Image(recovery_chart_path, width=6*inch, height=3.4*inch)
            story.append(img_recovery)
    else:
        story.append(Paragraph("No defrost cycles detected.", styles['Normal']))

    story.append(Spacer(1, 0.3*inch))

    # Compliance Analysis
    story.append(PageBreak())
    story.append(Paragraph("Food Safety Compliance", heading_style))

    optimal_min_str = str(time_range['optimal_range']).split(' to ')[0] if ' to ' in str(time_range['optimal_range']) else str(time_range['optimal_range'])

    compliance_data = [
        ['Temperature Range', 'Percentage', 'Status'],
        [str(time_range['optimal_range']), f"{time_range['optimal_pct']:.1f}%", 'Optimal'],
        [str(time_range['warning_range']), f"{time_range['warning_pct']:.1f}%", 'Warning'],
        [str(time_range['critical_threshold']), f"{time_range['critical_pct']:.1f}%", 'Critical'],
        [f"Below {optimal_min_str}", f"{time_range['below_optimal_pct']:.1f}%", 'Too Cold'],
    ]

    compliance_table = Table(compliance_data, colWidths=[2.5*inch, 2*inch, 1.5*inch])
    compliance_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f39c12')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey])
    ]))

    story.append(compliance_table)
    story.append(Spacer(1, 0.2*inch))

    # Compliance Pie Chart
    fig_compliance = go.Figure(data=[go.Pie(
        labels=['Optimal', 'Warning', 'Critical', 'Below Optimal'],
        values=[
            time_range['optimal_pct'],
            time_range['warning_pct'],
            time_range['critical_pct'],
            time_range['below_optimal_pct']
        ],
        marker=dict(colors=['green', 'orange', 'red', 'lightblue']),
        hole=0.4
    )])
    fig_compliance.update_layout(
        title="Time-in-Range Distribution",
        width=700,
        height=400
    )

    compliance_chart_path = tempfile.NamedTemporaryFile(delete=False, suffix='.png').name
    fig_compliance.write_image(compliance_chart_path, width=700, height=400)

    img_compliance = Image(compliance_chart_path, width=6*inch, height=3.4*inch)
    story.append(img_compliance)
    story.append(Spacer(1, 0.3*inch))

    # Temperature Trend Over Time
    story.append(PageBreak())
    story.append(Paragraph("Temperature Trend Analysis", heading_style))

    # Sample data for chart (use last 7 days or all data if less)
    chart_data = cabinet_data.tail(min(len(cabinet_data), 2000))  # Limit to last 2000 points for performance

    fig_trend = go.Figure()
    fig_trend.add_trace(go.Scatter(
        x=chart_data['timestamp'],
        y=chart_data['temperature_celsius'],
        mode='lines',
        name='Temperature',
        line=dict(color='blue', width=1)
    ))
    fig_trend.update_layout(
        title=f"Temperature Timeline - {cabinet_name} (Recent Data)",
        xaxis_title="Time",
        yaxis_title="Temperature (°C)",
        width=700,
        height=400,
        showlegend=False
    )

    trend_chart_path = tempfile.NamedTemporaryFile(delete=False, suffix='.png').name
    fig_trend.write_image(trend_chart_path, width=700, height=400)

    img_trend = Image(trend_chart_path, width=6*inch, height=3.4*inch)
    story.append(img_trend)
    story.append(Spacer(1, 0.3*inch))

    # Maintenance Recommendations
    story.append(Paragraph("Maintenance Recommendations", heading_style))

    recommendations = []

    if health_data['overall_score'] < 60:
        recommendations.append("URGENT: Schedule immediate maintenance inspection")

    if health_data['stability_score'] < 70:
        recommendations.append("High temperature variance - check door seals and gaskets")

    if health_data['temp_drift'] > 1:
        recommendations.append("Temperature creeping up - check refrigerant levels")

    if health_data['range_score'] < 80:
        recommendations.append("Frequently out of optimal range - verify thermostat calibration")

    if len(recovery_df) > 0 and recovery_df['recovery_duration_minutes'].mean() > 60:
        recommendations.append("Slow defrost recovery - check compressor performance")

    if time_range['critical_pct'] > 5:
        recommendations.append("Excessive time in critical temperature range - immediate attention required")

    if not recommendations:
        recommendations.append("No maintenance issues detected. Equipment is operating normally.")

    for i, rec in enumerate(recommendations, 1):
        story.append(Paragraph(f"{i}. {rec}", styles['Normal']))
        story.append(Spacer(1, 0.1*inch))

    # Daily Statistics (last 7 days)
    story.append(Spacer(1, 0.2*inch))
    story.append(Paragraph("Daily Statistics (Last 7 Days)", heading_style))

    daily_stats = cabinet_data.groupby('date')['temperature_celsius'].agg(['count', 'mean', 'min', 'max', 'std']).round(2)
    daily_stats = daily_stats.tail(7).reset_index()

    daily_data = [['Date', 'Readings', 'Avg Temp', 'Min Temp', 'Max Temp', 'Std Dev']]
    for _, row in daily_stats.iterrows():
        daily_data.append([
            str(row['date']),
            str(int(row['count'])),
            f"{row['mean']:.2f}°C",
            f"{row['min']:.2f}°C",
            f"{row['max']:.2f}°C",
            f"{row['std']:.2f}°C"
        ])

    daily_table = Table(daily_data, colWidths=[1.2*inch, 1*inch, 1*inch, 1*inch, 1*inch, 1*inch])
    daily_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#34495e')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey])
    ]))

    story.append(daily_table)
    story.append(Spacer(1, 0.2*inch))

    # Daily Temperature Trend Chart
    daily_stats_chart = cabinet_data.groupby('date')['temperature_celsius'].agg(['mean', 'min', 'max']).reset_index()
    daily_stats_chart = daily_stats_chart.tail(14)  # Last 14 days

    fig_daily = go.Figure()
    fig_daily.add_trace(go.Scatter(
        x=daily_stats_chart['date'],
        y=daily_stats_chart['max'],
        mode='lines',
        name='Max',
        line=dict(color='red', width=1, dash='dash')
    ))
    fig_daily.add_trace(go.Scatter(
        x=daily_stats_chart['date'],
        y=daily_stats_chart['mean'],
        mode='lines+markers',
        name='Average',
        line=dict(color='blue', width=2)
    ))
    fig_daily.add_trace(go.Scatter(
        x=daily_stats_chart['date'],
        y=daily_stats_chart['min'],
        mode='lines',
        name='Min',
        line=dict(color='lightblue', width=1, dash='dash'),
        fill='tonexty',
        fillcolor='rgba(135, 206, 250, 0.2)'
    ))
    fig_daily.update_layout(
        title="Daily Temperature Range (Last 14 Days)",
        xaxis_title="Date",
        yaxis_title="Temperature (°C)",
        width=700,
        height=400
    )

    daily_chart_path = tempfile.NamedTemporaryFile(delete=False, suffix='.png').name
    fig_daily.write_image(daily_chart_path, width=700, height=400)

    img_daily = Image(daily_chart_path, width=6*inch, height=3.4*inch)
    story.append(img_daily)

    # Footer
    story.append(Spacer(1, 0.5*inch))
    story.append(Paragraph(
        f"<i>Generated by Supermarket Cabinet Temperature Analysis System - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</i>",
        styles['Normal']
    ))

    # Build PDF
    doc.build(story)

    # Clean up temporary image files
    temp_files = [
        temp_dist_path, health_chart_path, cycles_chart_path,
        defrost_chart_path, recovery_chart_path, compliance_chart_path,
        trend_chart_path, daily_chart_path
    ]

    for temp_file in temp_files:
        try:
            if temp_file and os.path.exists(temp_file):
                os.remove(temp_file)
        except:
            pass

    buffer.seek(0)
    return buffer

def generate_multi_cabinet_pdf_report(cabinet_names, df_data):
    """
    Generate a comprehensive PDF report comparing multiple cabinets.
    """
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=0.5*inch, bottomMargin=0.5*inch)
    story = []
    styles = getSampleStyleSheet()

    # Initialize temp file paths
    temp_files = []

    # Custom styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#1f77b4'),
        spaceAfter=30,
        alignment=TA_CENTER
    )

    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=16,
        textColor=colors.HexColor('#2c3e50'),
        spaceAfter=12,
        spaceBefore=12
    )

    # Title
    story.append(Paragraph("Multi-Cabinet Comparison Report", title_style))
    story.append(Paragraph(f"Comparing {len(cabinet_names)} Cabinets", styles['Heading2']))
    story.append(Paragraph(f"Report Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", styles['Normal']))
    story.append(Spacer(1, 0.3*inch))

    # Calculate metrics for all cabinets
    comparison_data = []

    for cabinet in cabinet_names:
        cab_data = df_data[df_data['cabinet'] == cabinet].copy()
        cab_is_freezer = 'freezer' in cabinet.lower()

        health = calculate_health_score(cab_data, cab_is_freezer)
        time_range = calculate_time_in_range(cab_data, cab_is_freezer)
        defrost = detect_defrost_cycles(cab_data, cab_is_freezer)
        cycles = detect_cooling_cycles(cab_data)

        comparison_data.append({
            'Cabinet': cabinet,
            'Health Score': health['overall_score'],
            'Avg Temp (°C)': cab_data['temperature_celsius'].mean(),
            'Temp Std Dev': cab_data['temperature_celsius'].std(),
            'Optimal %': time_range['optimal_pct'],
            'Critical %': time_range['critical_pct'],
            'Defrost Cycles': len(defrost),
            'Cooling Cycles': len(cycles),
            'Temp Drift': health['temp_drift'],
            'Stability Score': health['stability_score'],
            'Range Score': health['range_score']
        })

    comparison_df = pd.DataFrame(comparison_data)

    # Executive Summary Table
    story.append(Paragraph("Executive Summary", heading_style))

    summary_data = [['Cabinet', 'Health Score', 'Avg Temp', 'Optimal %', 'Critical %']]
    for _, row in comparison_df.iterrows():
        summary_data.append([
            row['Cabinet'][:20],  # Truncate long names
            f"{row['Health Score']:.1f}",
            f"{row['Avg Temp (°C)']:.2f}°C",
            f"{row['Optimal %']:.1f}%",
            f"{row['Critical %']:.1f}%"
        ])

    summary_table = Table(summary_data, colWidths=[2.2*inch, 1.2*inch, 1.2*inch, 1.2*inch, 1.2*inch])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3498db')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey])
    ]))

    story.append(summary_table)
    story.append(Spacer(1, 0.3*inch))

    # Health Score Comparison Chart
    story.append(Paragraph("Health Score Comparison", heading_style))

    fig_health = px.bar(
        comparison_df.sort_values('Health Score', ascending=False),
        x='Cabinet',
        y='Health Score',
        title="Equipment Health Scores",
        color='Health Score',
        color_continuous_scale=['red', 'orange', 'yellow', 'green'],
        range_color=[0, 100],
        text='Health Score'
    )
    fig_health.update_traces(texttemplate='%{text:.1f}', textposition='outside')
    fig_health.update_layout(width=700, height=450, showlegend=False, yaxis_range=[0, 105])
    fig_health.add_hline(y=75, line_dash="dash", line_color="orange", annotation_text="Good (75)")
    fig_health.add_hline(y=90, line_dash="dash", line_color="green", annotation_text="Excellent (90)")

    health_path = tempfile.NamedTemporaryFile(delete=False, suffix='.png').name
    temp_files.append(health_path)
    fig_health.write_image(health_path, width=700, height=450)
    story.append(Image(health_path, width=6*inch, height=3.9*inch))
    story.append(Spacer(1, 0.3*inch))

    # Temperature Stability Comparison
    story.append(Paragraph("Temperature Stability Comparison", heading_style))

    fig_stability = px.bar(
        comparison_df.sort_values('Temp Std Dev'),
        x='Cabinet',
        y='Temp Std Dev',
        title="Temperature Standard Deviation (Lower is Better)",
        color='Temp Std Dev',
        color_continuous_scale='Reds',
        text='Temp Std Dev'
    )
    fig_stability.update_traces(texttemplate='%{text:.2f}', textposition='outside')
    fig_stability.update_layout(width=700, height=450, showlegend=False)

    stability_path = tempfile.NamedTemporaryFile(delete=False, suffix='.png').name
    temp_files.append(stability_path)
    fig_stability.write_image(stability_path, width=700, height=450)
    story.append(Image(stability_path, width=6*inch, height=3.9*inch))
    story.append(Spacer(1, 0.3*inch))

    # Page Break
    story.append(PageBreak())

    # Time-in-Range Compliance Comparison
    story.append(Paragraph("Time-in-Range Compliance", heading_style))

    fig_compliance = px.bar(
        comparison_df.sort_values('Optimal %', ascending=False),
        x='Cabinet',
        y='Optimal %',
        title="% Time in Optimal Temperature Range",
        color='Optimal %',
        color_continuous_scale='Greens',
        range_color=[0, 100],
        text='Optimal %'
    )
    fig_compliance.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
    fig_compliance.update_layout(width=700, height=450, yaxis_range=[0, 105])
    fig_compliance.add_hline(y=95, line_dash="dash", line_color="green", annotation_text="Target (95%)")

    compliance_path = tempfile.NamedTemporaryFile(delete=False, suffix='.png').name
    temp_files.append(compliance_path)
    fig_compliance.write_image(compliance_path, width=700, height=450)
    story.append(Image(compliance_path, width=6*inch, height=3.9*inch))
    story.append(Spacer(1, 0.3*inch))

    # Average Temperature Comparison
    story.append(Paragraph("Average Temperature Comparison", heading_style))

    fig_avg_temp = px.bar(
        comparison_df.sort_values('Avg Temp (°C)'),
        x='Cabinet',
        y='Avg Temp (°C)',
        title="Average Operating Temperature",
        color='Avg Temp (°C)',
        color_continuous_scale='RdBu_r',
        text='Avg Temp (°C)'
    )
    fig_avg_temp.update_traces(texttemplate='%{text:.2f}°C', textposition='outside')
    fig_avg_temp.update_layout(width=700, height=450)

    avg_temp_path = tempfile.NamedTemporaryFile(delete=False, suffix='.png').name
    temp_files.append(avg_temp_path)
    fig_avg_temp.write_image(avg_temp_path, width=700, height=450)
    story.append(Image(avg_temp_path, width=6*inch, height=3.9*inch))
    story.append(Spacer(1, 0.3*inch))

    # Page Break
    story.append(PageBreak())

    # Critical Temperature Exposure
    story.append(Paragraph("Critical Temperature Exposure", heading_style))

    fig_critical = px.bar(
        comparison_df.sort_values('Critical %', ascending=False),
        x='Cabinet',
        y='Critical %',
        title="% Time in Critical Temperature Range",
        color='Critical %',
        color_continuous_scale='Reds',
        text='Critical %'
    )
    fig_critical.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
    fig_critical.update_layout(width=700, height=450)
    fig_critical.add_hline(y=5, line_dash="dash", line_color="red", annotation_text="Warning (5%)")

    critical_path = tempfile.NamedTemporaryFile(delete=False, suffix='.png').name
    temp_files.append(critical_path)
    fig_critical.write_image(critical_path, width=700, height=450)
    story.append(Image(critical_path, width=6*inch, height=3.9*inch))
    story.append(Spacer(1, 0.3*inch))

    # Temperature Drift Analysis
    story.append(Paragraph("Temperature Drift Analysis", heading_style))

    fig_drift = px.bar(
        comparison_df.sort_values('Temp Drift', ascending=False),
        x='Cabinet',
        y='Temp Drift',
        title="Temperature Drift (°C)",
        color='Temp Drift',
        color_continuous_scale='RdYlGn_r',
        text='Temp Drift'
    )
    fig_drift.update_traces(texttemplate='%{text:+.2f}°C', textposition='outside')
    fig_drift.update_layout(width=700, height=450)
    fig_drift.add_hline(y=1, line_dash="dash", line_color="orange", annotation_text="Warning (+1°C)")
    fig_drift.add_hline(y=-1, line_dash="dash", line_color="blue")

    drift_path = tempfile.NamedTemporaryFile(delete=False, suffix='.png').name
    temp_files.append(drift_path)
    fig_drift.write_image(drift_path, width=700, height=450)
    story.append(Image(drift_path, width=6*inch, height=3.9*inch))
    story.append(Spacer(1, 0.3*inch))

    # Page Break
    story.append(PageBreak())

    # Performance Rankings
    story.append(Paragraph("Performance Rankings", heading_style))

    # Best Performers
    best_performers = comparison_df.nlargest(min(5, len(comparison_df)), 'Health Score')
    best_data = [['Rank', 'Cabinet', 'Health Score', 'Status']]
    for idx, (_, row) in enumerate(best_performers.iterrows(), 1):
        status, _, _ = get_health_status(row['Health Score'])
        best_data.append([
            str(idx),
            row['Cabinet'][:25],
            f"{row['Health Score']:.1f}",
            status
        ])

    best_table = Table(best_data, colWidths=[0.7*inch, 3*inch, 1.5*inch, 1.5*inch])
    best_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2ecc71')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey])
    ]))

    story.append(Paragraph("Top Performers", styles['Heading3']))
    story.append(best_table)
    story.append(Spacer(1, 0.3*inch))

    # Worst Performers
    worst_performers = comparison_df.nsmallest(min(5, len(comparison_df)), 'Health Score')
    worst_data = [['Rank', 'Cabinet', 'Health Score', 'Status']]
    for idx, (_, row) in enumerate(worst_performers.iterrows(), 1):
        status, _, _ = get_health_status(row['Health Score'])
        worst_data.append([
            str(idx),
            row['Cabinet'][:25],
            f"{row['Health Score']:.1f}",
            status
        ])

    worst_table = Table(worst_data, colWidths=[0.7*inch, 3*inch, 1.5*inch, 1.5*inch])
    worst_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e74c3c')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey])
    ]))

    story.append(Paragraph("Needs Attention", styles['Heading3']))
    story.append(worst_table)
    story.append(Spacer(1, 0.3*inch))

    # Detailed Metrics Table
    story.append(PageBreak())
    story.append(Paragraph("Detailed Metrics Comparison", heading_style))

    detailed_data = [['Cabinet', 'Health', 'Stability', 'Range', 'Defrost', 'Cycles']]
    for _, row in comparison_df.iterrows():
        detailed_data.append([
            row['Cabinet'][:20],
            f"{row['Health Score']:.0f}",
            f"{row['Stability Score']:.0f}",
            f"{row['Range Score']:.0f}",
            str(row['Defrost Cycles']),
            str(row['Cooling Cycles'])
        ])

    detailed_table = Table(detailed_data, colWidths=[2*inch, 1*inch, 1*inch, 1*inch, 1*inch, 1*inch])
    detailed_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#34495e')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey])
    ]))

    story.append(detailed_table)
    story.append(Spacer(1, 0.3*inch))

    # Key Findings and Recommendations
    story.append(Paragraph("Key Findings & Recommendations", heading_style))

    findings = []

    # Identify cabinets needing attention
    critical_cabinets = comparison_df[comparison_df['Health Score'] < 60]
    if len(critical_cabinets) > 0:
        findings.append(f"URGENT: {len(critical_cabinets)} cabinet(s) require immediate maintenance attention")

    # High critical exposure
    high_critical = comparison_df[comparison_df['Critical %'] > 5]
    if len(high_critical) > 0:
        findings.append(f"WARNING: {len(high_critical)} cabinet(s) spending excessive time in critical temperature range")

    # Poor compliance
    poor_compliance = comparison_df[comparison_df['Optimal %'] < 80]
    if len(poor_compliance) > 0:
        findings.append(f"{len(poor_compliance)} cabinet(s) have suboptimal compliance (<80% in optimal range)")

    # Temperature drift
    drifting = comparison_df[comparison_df['Temp Drift'] > 1]
    if len(drifting) > 0:
        findings.append(f"{len(drifting)} cabinet(s) showing concerning temperature drift")

    # Best performer
    best_cab = comparison_df.loc[comparison_df['Health Score'].idxmax()]
    findings.append(f"Best performer: {best_cab['Cabinet']} (Health Score: {best_cab['Health Score']:.1f})")

    # Average health
    avg_health = comparison_df['Health Score'].mean()
    findings.append(f"Fleet average health score: {avg_health:.1f}/100")

    if not findings:
        findings.append("All cabinets are operating within acceptable parameters")

    for i, finding in enumerate(findings, 1):
        story.append(Paragraph(f"{i}. {finding}", styles['Normal']))
        story.append(Spacer(1, 0.1*inch))

    # Footer
    story.append(Spacer(1, 0.5*inch))
    story.append(Paragraph(
        f"<i>Multi-Cabinet Comparison Report - Generated {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</i>",
        styles['Normal']
    ))

    # Build PDF
    doc.build(story)

    # Clean up temporary files
    for temp_file in temp_files:
        try:
            if temp_file and os.path.exists(temp_file):
                os.remove(temp_file)
        except:
            pass

    buffer.seek(0)
    return buffer


# Main app
st.title("🏪 Supermarket Cabinet Temperature Analysis")
st.markdown("Analysis of temperature cycles and defrost patterns for refrigeration cabinets")

# Load data
with st.spinner("Loading data..."):
    df = load_data()

st.success(f"Loaded {len(df):,} temperature readings from {df['cabinet'].nunique()} cabinets")
st.info(f"Date range: {df['timestamp'].min()} to {df['timestamp'].max()}")

# Sidebar filters
st.sidebar.header("Filters")

cabinet_type = st.sidebar.radio("Cabinet Type", ["All", "Freezers", "Chillers", "M&P", "Other"])

if cabinet_type == "Freezers":
    available_cabinets = df[df["cabinet"].str.contains("Freezer", case=False)]["cabinet"].unique()
elif cabinet_type == "Chillers":
    available_cabinets = df[df["cabinet"].str.contains("Chiller", case=False)]["cabinet"].unique()
elif cabinet_type == "M&P":
    available_cabinets = df[df["cabinet"].str.contains("M&P", case=False)]["cabinet"].unique()
elif cabinet_type == "Other":
    available_cabinets = df[~df["cabinet"].str.contains("Freezer|Chiller|M&P", case=False)]["cabinet"].unique()
else:
    available_cabinets = df["cabinet"].unique()

selected_cabinet = st.sidebar.selectbox("Select Cabinet", sorted(available_cabinets))

# Filter data for selected cabinet
cabinet_df = df[df["cabinet"] == selected_cabinet].copy()

# Determine if this is a freezer
is_freezer = "freezer" in selected_cabinet.lower()

# Create tabs
tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs(
    [
        "📊 Overview",
        "🔄 Cooling Cycles",
        "❄️ Defrost Cycles",
        "📈 Temperature Trends",
        "🎯 Time-in-Range",
        "🏥 Health Score",
        "🔍 Multi-Cabinet",
    ]
)

with tab1:
    st.header(f"Overview: {selected_cabinet}")

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

    # Temperature distribution
    st.subheader("Temperature Distribution")
    fig = px.histogram(
        cabinet_df, x="temperature_celsius", nbins=50, title=f"Temperature Distribution - {selected_cabinet}"
    )
    fig.update_layout(xaxis_title="Temperature (°C)", yaxis_title="Count")
    st.plotly_chart(fig, use_container_width=True)

    # Daily temperature summary
    st.subheader("Daily Statistics")
    daily_stats = cabinet_df.groupby("date")["temperature_celsius"].agg(["count", "mean", "min", "max", "std"]).round(2)
    daily_stats.columns = ["Readings", "Avg Temp", "Min Temp", "Max Temp", "Std Dev"]
    st.dataframe(daily_stats, use_container_width=True)

with tab2:
    st.header("🔄 Cooling Cycles Analysis")

    with st.spinner("Detecting cooling cycles..."):
        cycles_df = detect_cooling_cycles(cabinet_df)

    if len(cycles_df) > 0:
        # Add date and week columns
        cycles_df["date"] = pd.to_datetime(cycles_df["start_time"]).dt.date
        cycles_df["week"] = pd.to_datetime(cycles_df["start_time"]).dt.isocalendar().week

        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric("Total Cycles Detected", len(cycles_df))
        with col2:
            avg_duration = cycles_df["duration_minutes"].mean()
            st.metric("Average Cycle Duration", f"{avg_duration:.1f} min")
        with col3:
            avg_temp_range = cycles_df["temp_range"].mean()
            st.metric("Average Temp Range", f"{avg_temp_range:.2f}°C")

        # Cycles per day
        st.subheader("Cycles per Day")
        cycles_per_day = cycles_df.groupby("date").size().reset_index(name="cycle_count")
        fig = px.bar(cycles_per_day, x="date", y="cycle_count", title="Number of Cooling Cycles per Day")
        fig.update_layout(xaxis_title="Date", yaxis_title="Number of Cycles")
        st.plotly_chart(fig, use_container_width=True)

        # Cycles per week
        st.subheader("Cycles per Week")
        cycles_per_week = cycles_df.groupby("week").size().reset_index(name="cycle_count")
        st.dataframe(cycles_per_week, use_container_width=True)

        # Cycle duration distribution
        st.subheader("Cycle Duration Distribution")
        fig = px.histogram(cycles_df, x="duration_minutes", nbins=30, title="Distribution of Cycle Durations")
        fig.update_layout(xaxis_title="Duration (minutes)", yaxis_title="Count")
        st.plotly_chart(fig, use_container_width=True)

        # Detailed cycle data
        st.subheader("Detailed Cycle Data")
        display_cycles = cycles_df.copy()
        display_cycles["start_time"] = pd.to_datetime(display_cycles["start_time"])
        display_cycles["end_time"] = pd.to_datetime(display_cycles["end_time"])
        st.dataframe(display_cycles, use_container_width=True)
    else:
        st.warning("No cooling cycles detected. Try adjusting the detection parameters.")

with tab3:
    st.header("❄️ Defrost Cycles Analysis")

    with st.spinner("Detecting defrost cycles..."):
        defrost_df = detect_defrost_cycles(cabinet_df, is_freezer=is_freezer)

    if len(defrost_df) > 0:
        # Add date column
        defrost_df["date"] = pd.to_datetime(defrost_df["start_time"]).dt.date
        defrost_df["week"] = pd.to_datetime(defrost_df["start_time"]).dt.isocalendar().week

        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric("Total Defrost Cycles", len(defrost_df))
        with col2:
            avg_defrost_duration = defrost_df["duration_minutes"].mean()
            st.metric("Average Defrost Duration", f"{avg_defrost_duration:.1f} min")
        with col3:
            avg_temp_rise = defrost_df["temp_rise"].mean()
            st.metric("Average Temp Rise", f"{avg_temp_rise:.2f}°C")

        # Defrost cycles per day
        st.subheader("Defrost Cycles per Day")
        defrost_per_day = defrost_df.groupby("date").size().reset_index(name="defrost_count")
        fig = px.bar(defrost_per_day, x="date", y="defrost_count", title="Number of Defrost Cycles per Day")
        fig.update_layout(xaxis_title="Date", yaxis_title="Number of Defrost Cycles")
        st.plotly_chart(fig, use_container_width=True)

        # Defrost cycles per week
        st.subheader("Defrost Cycles per Week")
        defrost_per_week = defrost_df.groupby("week").size().reset_index(name="defrost_count")
        st.dataframe(defrost_per_week, use_container_width=True)

        # Defrost duration over time
        st.subheader("Defrost Duration Over Time")
        defrost_display = defrost_df.copy()
        defrost_display["start_time"] = pd.to_datetime(defrost_display["start_time"])
        fig = px.scatter(
            defrost_display,
            x="start_time",
            y="duration_minutes",
            color="max_temp",
            title="Defrost Duration and Peak Temperature Over Time",
        )
        fig.update_layout(xaxis_title="Time", yaxis_title="Duration (minutes)")
        st.plotly_chart(fig, use_container_width=True)

        # Detailed defrost data
        st.subheader("Detailed Defrost Cycle Data")
        display_defrost = defrost_df.copy()
        display_defrost["start_time"] = pd.to_datetime(display_defrost["start_time"])
        display_defrost["end_time"] = pd.to_datetime(display_defrost["end_time"])
        st.dataframe(display_defrost, use_container_width=True)
    else:
        st.info(
            f"No defrost cycles detected for {selected_cabinet}. This may be normal for some cabinet types or the detection threshold may need adjustment."
        )

with tab4:
    st.header("📈 Temperature Trends")

    # Date range selector
    date_range = st.date_input(
        "Select Date Range",
        value=(cabinet_df["date"].min(), cabinet_df["date"].max()),
        min_value=cabinet_df["date"].min(),
        max_value=cabinet_df["date"].max(),
    )

    if len(date_range) == 2:
        filtered_df = cabinet_df[(cabinet_df["date"] >= date_range[0]) & (cabinet_df["date"] <= date_range[1])]

        st.subheader("Temperature Over Time")
        fig = go.Figure()
        fig.add_trace(
            go.Scatter(
                x=filtered_df["timestamp"],
                y=filtered_df["temperature_celsius"],
                mode="lines",
                name="Temperature",
                line=dict(color="blue", width=1),
            )
        )

        fig.update_layout(
            title=f"Temperature Timeline - {selected_cabinet}",
            xaxis_title="Time",
            yaxis_title="Temperature (°C)",
            hovermode="x unified",
        )
        st.plotly_chart(fig, use_container_width=True)

        # Hourly averages
        st.subheader("Hourly Average Temperature Pattern")
        filtered_df["hour"] = filtered_df["timestamp"].dt.hour
        hourly_avg = filtered_df.groupby("hour")["temperature_celsius"].agg(["mean", "std"]).reset_index()

        fig = go.Figure()
        fig.add_trace(
            go.Scatter(
                x=hourly_avg["hour"],
                y=hourly_avg["mean"],
                mode="lines+markers",
                name="Average",
                line=dict(color="green", width=2),
            )
        )
        fig.add_trace(
            go.Scatter(
                x=hourly_avg["hour"],
                y=hourly_avg["mean"] + hourly_avg["std"],
                mode="lines",
                line=dict(width=0),
                showlegend=False,
            )
        )
        fig.add_trace(
            go.Scatter(
                x=hourly_avg["hour"],
                y=hourly_avg["mean"] - hourly_avg["std"],
                mode="lines",
                line=dict(width=0),
                fillcolor="rgba(0,100,80,0.2)",
                fill="tonexty",
                name="±1 Std Dev",
            )
        )

        fig.update_layout(
            title="Average Temperature by Hour of Day", xaxis_title="Hour of Day", yaxis_title="Temperature (°C)"
        )
        st.plotly_chart(fig, use_container_width=True)

with tab5:
    st.header("🎯 Time-in-Range Analysis")
    st.markdown("**Food Safety Compliance Monitoring**")

    # Calculate time-in-range metrics
    time_range_metrics = calculate_time_in_range(cabinet_df, is_freezer)

    st.subheader("Temperature Range Distribution")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            "Optimal Range", f"{time_range_metrics['optimal_pct']:.1f}%", help=time_range_metrics["optimal_range"]
        )
        st.caption(time_range_metrics["optimal_range"])

    with col2:
        st.metric(
            "Warning Range", f"{time_range_metrics['warning_pct']:.1f}%", help=time_range_metrics["warning_range"]
        )
        st.caption(time_range_metrics["warning_range"])

    with col3:
        st.metric(
            "Critical",
            f"{time_range_metrics['critical_pct']:.1f}%",
            delta=f"{-time_range_metrics['critical_pct']:.1f}%" if time_range_metrics["critical_pct"] > 0 else None,
            delta_color="inverse",
            help=time_range_metrics["critical_threshold"],
        )
        st.caption(time_range_metrics["critical_threshold"])

    with col4:
        st.metric("Below Optimal", f"{time_range_metrics['below_optimal_pct']:.1f}%")
        st.caption("Too cold")

    # Pie chart
    fig = go.Figure(
        data=[
            go.Pie(
                labels=["Optimal", "Warning", "Critical", "Below Optimal"],
                values=[
                    time_range_metrics["optimal_pct"],
                    time_range_metrics["warning_pct"],
                    time_range_metrics["critical_pct"],
                    time_range_metrics["below_optimal_pct"],
                ],
                marker=dict(colors=["green", "orange", "red", "lightblue"]),
                hole=0.4,
            )
        ]
    )
    fig.update_layout(title="Time-in-Range Distribution")
    st.plotly_chart(fig, use_container_width=True)

    # Daily compliance
    st.subheader("Daily Compliance Analysis")

    cabinet_df_daily = cabinet_df.copy()
    cabinet_df_daily["in_optimal"] = (cabinet_df_daily["temperature_celsius"] >= (-25 if is_freezer else 0)) & (
        cabinet_df_daily["temperature_celsius"] <= (-18 if is_freezer else 5)
    )

    daily_compliance = (
        cabinet_df_daily.groupby("date").agg({"in_optimal": lambda x: (x.sum() / len(x)) * 100}).reset_index()
    )
    daily_compliance.columns = ["date", "compliance_pct"]

    fig = px.bar(
        daily_compliance,
        x="date",
        y="compliance_pct",
        title="Daily Compliance Rate (% Time in Optimal Range)",
        color="compliance_pct",
        color_continuous_scale=["red", "orange", "green"],
        range_color=[0, 100],
    )
    fig.update_layout(xaxis_title="Date", yaxis_title="Compliance %", yaxis_range=[0, 105])
    fig.add_hline(y=95, line_dash="dash", line_color="green", annotation_text="95% Target")
    st.plotly_chart(fig, use_container_width=True)

    # Compliance summary
    avg_compliance = daily_compliance["compliance_pct"].mean()
    days_compliant = len(daily_compliance[daily_compliance["compliance_pct"] >= 95])
    total_days = len(daily_compliance)

    st.info(f"""
    **Summary:** {days_compliant}/{total_days} days met 95% compliance target
    (Average: {avg_compliance:.1f}%)
    """)

with tab6:
    st.header("🏥 Equipment Health Score")
    st.markdown("**Predictive Maintenance Analysis**")

    # Calculate health score
    health_data = calculate_health_score(cabinet_df, is_freezer)
    status, emoji, color = get_health_status(health_data["overall_score"])

    # Overall health display
    col1, col2, col3 = st.columns([2, 1, 1])

    with col1:
        st.markdown(f"### {emoji} Overall Health: {status}")
        st.progress(health_data["overall_score"] / 100)
        st.metric("Health Score", f"{health_data['overall_score']:.1f}/100")

    with col2:
        st.metric("Temp Stability (σ)", f"{health_data['temp_std']:.2f}°C")
        st.metric("Temp Drift", f"{health_data['temp_drift']:+.2f}°C")

    with col3:
        if health_data["overall_score"] < 60:
            st.error("⚠️ Maintenance Required")
        elif health_data["overall_score"] < 75:
            st.warning("⚡ Monitor Closely")
        else:
            st.success("✅ Healthy")

    # Component scores
    st.subheader("Component Health Breakdown")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            "Stability", f"{health_data['stability_score']:.0f}/100", help="Based on temperature standard deviation"
        )
        st.progress(health_data["stability_score"] / 100)

    with col2:
        st.metric("Time-in-Range", f"{health_data['range_score']:.0f}/100", help="% of time in optimal range")
        st.progress(health_data["range_score"] / 100)

    with col3:
        st.metric("Trend Analysis", f"{health_data['trend_score']:.0f}/100", help="Temperature drift over time")
        st.progress(health_data["trend_score"] / 100)

    with col4:
        st.metric(
            "Critical Events", f"{health_data['critical_score']:.0f}/100", help="Avoidance of critical temperatures"
        )
        st.progress(health_data["critical_score"] / 100)

    # Health factors chart
    st.subheader("Health Score Factors")

    factors_df = pd.DataFrame(
        {
            "Factor": ["Stability (30%)", "Time-in-Range (35%)", "Trend (20%)", "Critical Events (15%)"],
            "Score": [
                health_data["stability_score"],
                health_data["range_score"],
                health_data["trend_score"],
                health_data["critical_score"],
            ],
        }
    )

    fig = px.bar(
        factors_df,
        x="Score",
        y="Factor",
        orientation="h",
        title="Health Score Components",
        color="Score",
        color_continuous_scale=["red", "orange", "yellow", "green"],
        range_color=[0, 100],
    )
    fig.update_layout(xaxis_range=[0, 100])
    st.plotly_chart(fig, use_container_width=True)

    # Recovery time analysis
    st.subheader("Defrost Recovery Analysis")

    defrost_df = detect_defrost_cycles(cabinet_df, is_freezer)
    recovery_df = pd.DataFrame()  # Initialize to avoid NameError

    if len(defrost_df) > 0:
        recovery_df = calculate_recovery_time(cabinet_df, defrost_df, is_freezer)

        if len(recovery_df) > 0:
            avg_recovery = recovery_df["recovery_duration_minutes"].mean()
            max_recovery = recovery_df["recovery_duration_minutes"].max()

            col1, col2, col3 = st.columns(3)

            with col1:
                st.metric("Average Recovery Time", f"{avg_recovery:.1f} min")
            with col2:
                st.metric("Max Recovery Time", f"{max_recovery:.1f} min")
            with col3:
                # Flag slow recovery
                if avg_recovery > 60:
                    st.error("⚠️ Slow Recovery")
                elif avg_recovery > 40:
                    st.warning("⚡ Monitor")
                else:
                    st.success("✅ Normal")

            # Recovery time trend
            recovery_display = recovery_df.copy()
            recovery_display["defrost_start"] = pd.to_datetime(recovery_display["defrost_start"])

            fig = px.scatter(
                recovery_display,
                x="defrost_start",
                y="recovery_duration_minutes",
                title="Defrost Recovery Time Over Time",
                trendline="lowess",
                labels={"defrost_start": "Date", "recovery_duration_minutes": "Recovery Time (min)"},
            )
            fig.add_hline(y=40, line_dash="dash", line_color="orange", annotation_text="Warning Threshold")
            fig.add_hline(y=60, line_dash="dash", line_color="red", annotation_text="Critical Threshold")
            st.plotly_chart(fig, use_container_width=True)

            # Detailed recovery data
            with st.expander("View Detailed Recovery Data"):
                st.dataframe(recovery_display, use_container_width=True)
        else:
            st.info("No recovery data available - defrost cycles may not have completed.")
    else:
        st.info("No defrost cycles detected for this cabinet.")

    # Maintenance recommendations
    st.subheader("Maintenance Recommendations")

    recommendations = []

    if health_data["overall_score"] < 60:
        recommendations.append("🔴 **URGENT:** Schedule immediate maintenance inspection")

    if health_data["stability_score"] < 70:
        recommendations.append("⚠️ High temperature variance - check door seals and gaskets")

    if health_data["temp_drift"] > 1:
        recommendations.append("⚠️ Temperature creeping up - check refrigerant levels")

    if health_data["range_score"] < 80:
        recommendations.append("⚠️ Frequently out of optimal range - verify thermostat calibration")

    if len(recovery_df) > 0 and recovery_df["recovery_duration_minutes"].mean() > 60:
        recommendations.append("⚠️ Slow defrost recovery - check compressor performance")

    if time_range_metrics["critical_pct"] > 5:
        recommendations.append("🔴 Excessive time in critical temperature range - immediate attention required")

    if not recommendations:
        st.success("✅ No maintenance issues detected. Equipment is operating normally.")
    else:
        for rec in recommendations:
            st.warning(rec)

with tab7:
    st.header("🔍 Multi-Cabinet Comparison")
    st.markdown("**Identify Problem Units**")

    # Cabinet selection for comparison
    st.subheader("Select Cabinets to Compare")

    # Filter by cabinet type
    compare_type = st.radio(
        "Cabinet Type for Comparison", ["Freezers Only", "Chillers Only", "All Cabinets"], horizontal=True
    )

    if compare_type == "Freezers Only":
        compare_cabinets = sorted(df[df["cabinet"].str.contains("Freezer", case=False)]["cabinet"].unique())
    elif compare_type == "Chillers Only":
        compare_cabinets = sorted(df[df["cabinet"].str.contains("Chiller", case=False)]["cabinet"].unique())
    else:
        compare_cabinets = sorted(df["cabinet"].unique())

    selected_for_comparison = st.multiselect(
        "Select 2-10 cabinets to compare",
        compare_cabinets,
        default=[selected_cabinet] if selected_cabinet in compare_cabinets else [],
    )

    if len(selected_for_comparison) >= 2:
        # Calculate metrics for all selected cabinets
        comparison_data = []

        with st.spinner("Calculating metrics for selected cabinets..."):
            for cabinet in selected_for_comparison:
                cab_data = df[df["cabinet"] == cabinet].copy()
                cab_is_freezer = "freezer" in cabinet.lower()

                # Calculate all metrics
                health = calculate_health_score(cab_data, cab_is_freezer)
                time_range = calculate_time_in_range(cab_data, cab_is_freezer)
                defrost = detect_defrost_cycles(cab_data, cab_is_freezer)
                cycles = detect_cooling_cycles(cab_data)

                comparison_data.append(
                    {
                        "Cabinet": cabinet,
                        "Health Score": health["overall_score"],
                        "Avg Temp (°C)": cab_data["temperature_celsius"].mean(),
                        "Temp Std Dev": cab_data["temperature_celsius"].std(),
                        "Optimal %": time_range["optimal_pct"],
                        "Critical %": time_range["critical_pct"],
                        "Defrost Cycles": len(defrost),
                        "Cooling Cycles": len(cycles),
                        "Temp Drift": health["temp_drift"],
                    }
                )

        comparison_df = pd.DataFrame(comparison_data)

        # Overall comparison table
        st.subheader("Comparison Summary")
        st.dataframe(
            comparison_df.style.background_gradient(subset=["Health Score"], cmap="RdYlGn", vmin=0, vmax=100)
            .background_gradient(subset=["Optimal %"], cmap="RdYlGn", vmin=0, vmax=100)
            .background_gradient(subset=["Critical %"], cmap="RdYlGn_r", vmin=0, vmax=10)
            .format(
                {
                    "Health Score": "{:.1f}",
                    "Avg Temp (°C)": "{:.2f}",
                    "Temp Std Dev": "{:.2f}",
                    "Optimal %": "{:.1f}",
                    "Critical %": "{:.1f}",
                    "Temp Drift": "{:.2f}",
                }
            ),
            use_container_width=True,
        )

        # Health score comparison
        st.subheader("Health Score Comparison")
        fig = px.bar(
            comparison_df.sort_values("Health Score", ascending=False),
            x="Cabinet",
            y="Health Score",
            title="Equipment Health Scores",
            color="Health Score",
            color_continuous_scale=["red", "orange", "yellow", "green"],
            range_color=[0, 100],
        )
        fig.add_hline(y=75, line_dash="dash", line_color="orange", annotation_text="Good")
        fig.add_hline(y=90, line_dash="dash", line_color="green", annotation_text="Excellent")
        st.plotly_chart(fig, use_container_width=True)

        # Temperature stability comparison
        st.subheader("Temperature Stability")
        fig = px.bar(
            comparison_df.sort_values("Temp Std Dev"),
            x="Cabinet",
            y="Temp Std Dev",
            title="Temperature Standard Deviation (lower is better)",
            color="Temp Std Dev",
            color_continuous_scale="Reds",
        )
        st.plotly_chart(fig, use_container_width=True)

        # Compliance comparison
        st.subheader("Time-in-Range Compliance")
        fig = px.bar(
            comparison_df.sort_values("Optimal %", ascending=False),
            x="Cabinet",
            y="Optimal %",
            title="% Time in Optimal Temperature Range",
            color="Optimal %",
            color_continuous_scale="Greens",
            range_color=[0, 100],
        )
        fig.add_hline(y=95, line_dash="dash", line_color="green", annotation_text="Target")
        st.plotly_chart(fig, use_container_width=True)

        # Identify best and worst performers
        st.subheader("Performance Rankings")

        col1, col2 = st.columns(2)

        with col1:
            st.markdown("### 🏆 Best Performers")
            best = comparison_df.nlargest(3, "Health Score")[["Cabinet", "Health Score"]]
            for idx, row in best.iterrows():
                st.success(f"**{row['Cabinet']}**: {row['Health Score']:.1f}/100")

        with col2:
            st.markdown("### ⚠️ Needs Attention")
            worst = comparison_df.nsmallest(3, "Health Score")[["Cabinet", "Health Score"]]
            for idx, row in worst.iterrows():
                st.error(f"**{row['Cabinet']}**: {row['Health Score']:.1f}/100")

        # Temperature drift analysis
        st.subheader("Temperature Drift Analysis")
        drifting = comparison_df[comparison_df["Temp Drift"] > 1]

        if len(drifting) > 0:
            st.warning(f"⚠️ {len(drifting)} cabinet(s) showing significant temperature drift:")
            st.dataframe(drifting[["Cabinet", "Temp Drift"]], use_container_width=True)
        else:
            st.success("✅ No cabinets showing significant temperature drift")

    elif len(selected_for_comparison) == 1:
        st.info("Please select at least 2 cabinets to compare")
    else:
        st.info("Select cabinets above to begin comparison")

# Download options
st.sidebar.markdown("---")
st.sidebar.subheader("Export Data")

# PDF Report Generation
st.sidebar.markdown("### 📄 Generate PDF Report")
if st.sidebar.button("🔄 Generate PDF Report", use_container_width=True):
    with st.spinner("Generating comprehensive PDF report..."):
        try:
            pdf_buffer = generate_pdf_report(selected_cabinet, cabinet_df, is_freezer)
            st.sidebar.success("✅ PDF Report Generated!")

            st.sidebar.download_button(
                label="📥 Download PDF Report",
                data=pdf_buffer,
                file_name=f"{selected_cabinet}_analysis_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
                mime="application/pdf",
                use_container_width=True
            )
        except Exception as e:
            st.sidebar.error(f"Error generating PDF: {str(e)}")

st.sidebar.markdown("---")
st.sidebar.markdown("### 🔍 Multi-Cabinet Comparison Report")

# Cabinet type selector for comparison
comparison_type = st.sidebar.selectbox(
    "Select Cabinet Type",
    ["All Freezers", "All Chillers", "All M&P", "Custom Selection"]
)

# Get cabinet list based on selection
if comparison_type == "All Freezers":
    multi_cabinets = sorted(df[df['cabinet'].str.contains('Freezer', case=False)]['cabinet'].unique())
elif comparison_type == "All Chillers":
    multi_cabinets = sorted(df[df['cabinet'].str.contains('Chiller', case=False)]['cabinet'].unique())
elif comparison_type == "All M&P":
    multi_cabinets = sorted(df[df['cabinet'].str.contains('M&P', case=False)]['cabinet'].unique())
else:
    multi_cabinets = st.sidebar.multiselect(
        "Select Cabinets (2-15)",
        sorted(df['cabinet'].unique()),
        default=[]
    )

if comparison_type != "Custom Selection":
    st.sidebar.info(f"📊 {len(multi_cabinets)} cabinets selected")

if st.sidebar.button("📊 Generate Comparison PDF", use_container_width=True):
    if len(multi_cabinets) >= 2:
        with st.spinner(f"Generating comparison report for {len(multi_cabinets)} cabinets..."):
            try:
                pdf_buffer = generate_multi_cabinet_pdf_report(multi_cabinets, df)
                st.sidebar.success("✅ Comparison Report Generated!")

                st.sidebar.download_button(
                    label="📥 Download Comparison PDF",
                    data=pdf_buffer,
                    file_name=f"multi_cabinet_comparison_{comparison_type.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )
            except Exception as e:
                st.sidebar.error(f"Error generating comparison PDF: {str(e)}")
    else:
        st.sidebar.warning("⚠️ Please select at least 2 cabinets")

st.sidebar.markdown("---")
st.sidebar.markdown("### 📊 Export Raw Data")

if st.sidebar.button("Export Cycles to CSV"):
    cycles_df = detect_cooling_cycles(cabinet_df)
    if len(cycles_df) > 0:
        csv = cycles_df.to_csv(index=False)
        st.sidebar.download_button(
            label="Download Cooling Cycles CSV",
            data=csv,
            file_name=f"{selected_cabinet}_cooling_cycles.csv",
            mime="text/csv",
        )

if st.sidebar.button("Export Defrost Cycles to CSV"):
    defrost_df = detect_defrost_cycles(cabinet_df, is_freezer=is_freezer)
    if len(defrost_df) > 0:
        csv = defrost_df.to_csv(index=False)
        st.sidebar.download_button(
            label="Download Defrost Cycles CSV",
            data=csv,
            file_name=f"{selected_cabinet}_defrost_cycles.csv",
            mime="text/csv",
        )
