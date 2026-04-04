# Supermarket Cabinet Temperature Analysis System

A comprehensive multi-page Streamlit application for analyzing temperature data from supermarket refrigeration cabinets.

## 🚀 Quick Start

```bash
streamlit run app.py
```

Then open http://localhost:8501 in your browser.

## 📁 Project Structure

```
analysis/
├── app.py                          # Main entry point (landing page)
├── app_cobh_analysis.py            # Original single-file app (kept for PDF functions)
├── cobh.csv                        # Temperature data
├── utils/
│   ├── __init__.py
│   └── calculations.py             # Analysis functions
└── pages/
    ├── 01_📊_Overview.py           # Temperature distribution & daily stats
    ├── 02_🔄_Cooling_Cycles.py     # Compressor cycle analysis
    ├── 03_❄️_Defrost_Cycles.py     # Defrost event detection
    ├── 04_📈_Temperature_Trends.py  # Time-series visualization
    ├── 05_🎯_Time_in_Range.py       # Food safety compliance
    ├── 06_🏥_Health_Score.py        # Predictive maintenance
    ├── 07_🔍_Multi_Cabinet_Comparison.py  # Fleet analysis
    └── 08_📄_PDF_Reports.py          # Report generation
```

## 📊 Analysis Pages

1. **Overview** - Temperature distribution & daily statistics
2. **Cooling Cycles** - Compressor on/off cycle analysis  
3. **Defrost Cycles** - Defrost event detection & recovery
4. **Temperature Trends** - Time-series visualization
5. **Time-in-Range** - Food safety compliance
6. **Health Score** - Predictive maintenance
7. **Multi-Cabinet** - Fleet comparison
8. **PDF Reports** - Generate comprehensive reports
