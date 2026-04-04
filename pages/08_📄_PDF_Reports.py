"""PDF Report Generation page"""

import streamlit as st
from datetime import datetime
import sys
sys.path.append('..')

# Import PDF generation functions from the original app file
# (These functions are still in app_cobh_analysis.py)
import importlib.util
spec = importlib.util.spec_from_file_location("pdf_funcs", "app_cobh_analysis.py")
pdf_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pdf_module)

st.title("📄 PDF Reports")
st.markdown("**Generate Comprehensive Reports**")

# Get data from session state
if 'df' not in st.session_state:
    st.warning("⚠️ Please return to the main page first")
    st.stop()

df = st.session_state.df

# Create tabs for different report types
tab1, tab2 = st.tabs(["Single Cabinet Report", "Multi-Cabinet Comparison Report"])

with tab1:
    st.subheader("Generate Single Cabinet Report")

    if 'selected_cabinet' in st.session_state:
        selected_cabinet = st.session_state.selected_cabinet
        is_freezer = st.session_state.is_freezer

        st.info(f"📊 Selected Cabinet: **{selected_cabinet}**")

        cabinet_df = df[df['cabinet'] == selected_cabinet]

        if st.button("🔄 Generate PDF Report", key="single", use_container_width=True):
            with st.spinner("Generating comprehensive PDF report..."):
                try:
                    pdf_buffer = pdf_module.generate_pdf_report(selected_cabinet, cabinet_df, is_freezer)
                    st.success("✅ PDF Report Generated!")

                    st.download_button(
                        label="📥 Download PDF Report",
                        data=pdf_buffer,
                        file_name=f"{selected_cabinet}_analysis_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
                        mime="application/pdf",
                        use_container_width=True
                    )
                except Exception as e:
                    st.error(f"Error generating PDF: {str(e)}")
    else:
        st.warning("⚠️ Please select a cabinet from the main page first")

with tab2:
    st.subheader("Generate Multi-Cabinet Comparison Report")

    # Cabinet type selector
    comparison_type = st.selectbox(
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
        multi_cabinets = st.multiselect(
            "Select Cabinets (2-15)",
            sorted(df['cabinet'].unique()),
            default=[]
        )

    if comparison_type != "Custom Selection":
        st.info(f"📊 {len(multi_cabinets)} cabinets selected")

    if st.button("📊 Generate Comparison PDF", key="multi", use_container_width=True):
        if len(multi_cabinets) >= 2:
            with st.spinner(f"Generating comparison report for {len(multi_cabinets)} cabinets..."):
                try:
                    pdf_buffer = pdf_module.generate_multi_cabinet_pdf_report(multi_cabinets, df)
                    st.success("✅ Comparison Report Generated!")

                    st.download_button(
                        label="📥 Download Comparison PDF",
                        data=pdf_buffer,
                        file_name=f"multi_cabinet_comparison_{comparison_type.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
                        mime="application/pdf",
                        use_container_width=True
                    )
                except Exception as e:
                    st.error(f"Error generating comparison PDF: {str(e)}")
        else:
            st.warning("⚠️ Please select at least 2 cabinets")

# Report features
st.markdown("---")
st.subheader("📋 Report Features")

col1, col2 = st.columns(2)

with col1:
    st.markdown("""
    **Single Cabinet Report Includes:**
    - Executive summary & health score
    - Temperature distribution charts
    - Cooling & defrost cycle analysis
    - Recovery time analysis
    - Food safety compliance metrics
    - Maintenance recommendations
    - Daily statistics with trends
    """)

with col2:
    st.markdown("""
    **Multi-Cabinet Report Includes:**
    - Fleet-wide health comparison
    - Temperature stability ranking
    - Compliance benchmarking
    - Performance rankings
    - Temperature drift analysis
    - Detailed metrics table
    - Automated recommendations
    """)