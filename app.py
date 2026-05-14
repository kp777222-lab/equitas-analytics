import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import io
from fpdf import FPDF

# --- 1. PAGE SETUP ---
st.set_page_config(page_title="Equitas Ultimate Intel v2", page_icon="🛡️", layout="wide")

st.title("🛡️ Equitas Trade Intelligence & Behavior Analytics")
st.markdown("Advanced B-Book risk management, toxin detection, and PDF reporting via file upload.")

# --- 2. SIDEBAR: DATA UPLOAD ---
st.sidebar.header("📂 Upload Equitas Data")
st.sidebar.markdown("Upload your exact Equitas History CSV or Excel file here.")
uploaded_file = st.sidebar.file_uploader("Upload Trade History", type=["csv", "xlsx"])

st.sidebar.divider()
st.sidebar.header("⚙️ Toxin Thresholds")
scalp_min = st.sidebar.slider("Scalp Definition (Mins)", 1, 10, 3)
burst_limit = st.sidebar.slider("Burst Definition (Trades/Min)", 2, 20, 5)

# --- PDF GENERATOR FUNCTION ---
def create_pdf_report(df, metrics):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(200, 10, txt="EQUITAS TRADER - RISK & INTELLIGENCE REPORT", ln=1, align='C')
    pdf.set_font("Arial", size=12)
    pdf.cell(200, 10, txt=f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M')}", ln=1, align='C')
    pdf.ln(10)
    
    # Add Metrics
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(200, 10, txt="1. Core Performance Metrics", ln=1)
    pdf.set_font("Arial", size=12)
    for key, value in metrics.items():
        pdf.cell(200, 8, txt=f"{key}: {value}", ln=1)
        
    pdf.ln(10)
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(200, 10, txt="2. Toxin & Risk Warnings", ln=1)
    pdf.set_font("Arial", size=12)
    
    if metrics['Scalp Ratio'] > 30:
        pdf.cell(200, 8, txt="[WARNING] High Scalping Ratio Detected. Potential latency/EA risk.", ln=1)
    if metrics['Martingale Events'] > 0:
        pdf.cell(200, 8, txt="[WARNING] Martingale Behavior Detected (Volume spikes after losses).", ln=1)
    if metrics['Burst Events'] > 0:
        pdf.cell(200, 8, txt="[WARNING] High-Frequency Burst Trading Detected.", ln=1)
    if metrics['Latency Arb Events'] > 0:
        pdf.cell(200, 8, txt="[WARNING] Latency Arbitrage Suspects Detected.", ln=1)
        
    return pdf.output(dest='S').encode('latin-1')

# --- 3. MAIN INTERFACE ---
if uploaded_file is None:
    st.info("👈 Please upload your Equitas trade history file in the sidebar to begin analysis.")
else:
    try:
        # Read the uploaded file
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file)
        else:
            df = pd.read_excel(uploaded_file)
            
        df.columns = df.columns.str.strip()
        
        # Base Cleaning (Equitas Mapping)
        if 'PL' in df.columns:
            df['PL'] = pd.to_numeric(df['PL'].astype(str).str.replace(',', ''), errors='coerce')
            df = df.dropna(subset=['PL']).copy()
            df = df.rename(columns={'PL': 'Profit'})
        else:
            st.error("Could not find a 'PL' column. Make sure this is an Equitas trade history export.")
            st.stop()
            
        if 'Type' in df.columns:
            df = df.drop(columns=['Type'])
            
        df = df.rename(columns={'Amount': 'Volume', 'B/S': 'Type', 'Time': 'Close Time'})
        df = df.dropna(subset=['Open Time', 'Close Time', 'Symbol', 'Volume'])
        
        df['Open Time'] = pd.to_datetime(df['Open Time'], errors='coerce')
        df['Close Time'] = pd.to_datetime(df['Close Time'], errors='coerce')
        df = df.dropna(subset=['Open Time', 'Close Time']) 
        df['Volume'] = pd.to_numeric(df['Volume'], errors='coerce')

        df['Duration_Min'] = (df['Close Time'] - df['Open Time']).dt.total_seconds() / 60.0
        df['Duration_Min'] = df['Duration_Min'].round(2)
        df = df.sort_values('Close Time').reset_index(drop=True)

        # --- ADVANCED TOXIN ALGORITHMS ---
        # 1. Scalping & Bursts
        df['Is_Scalp'] = df['Duration_Min'] <= scalp_min
        df['Open_Min_Key'] = df['Open Time'].dt.strftime('%Y-%m-%d %H:%M')
        burst_check = df.groupby('Open_Min_Key').size()
        burst_mins = burst_check[burst_check >= burst_limit].index.tolist()
        df['Is_Burst'] = df['Open_Min_Key'].isin(burst_mins)

        # 2. Martingale / Grid Risk Detection
        df['Prev_Profit'] = df['Profit'].shift(1)
        df['Prev_Volume'] = df['Volume'].shift(1)
        df['Is_Martingale'] = (df['Prev_Profit'] < 0) & (df['Volume'] >= (df['Prev_Volume'] * 1.5))
        
        # 3. Latency Arbitrage Detection
        profit_threshold = df['Profit'].quantile(0.85) if len(df) > 10 else 50
        df['Is_Latency_Arb'] = (df['Duration_Min'] < 1.0) & (df['Profit'] > profit_threshold)

        # --- METRICS CALCULATION ---
        total_profit = df['Profit'].sum()
        win_rate = (len(df[df['Profit'] > 0]) / len(df)) * 100 if len(df) > 0 else 0
        scalp_ratio = (df['Is_Scalp'].sum() / len(df)) * 100 if len(df) > 0 else 0
        martingale_count = df['Is_Martingale'].sum()
        latency_arb_count = df['Is_Latency_Arb'].sum()

        report_metrics = {
            "Total Trades": len(df),
            "Net Profit": f"${total_profit:,.2f}",
            "Win Rate": f"{win_rate:.1f}%",
            "Scalp Ratio": f"{scalp_ratio:.1f}%",
            "Burst Events": len(burst_mins),
            "Martingale Events": martingale_count,
            "Latency Arb Events": latency_arb_count
        }

        # --- TOP ROW: KPI METRICS ---
        st.header("📊 Toxicity & Performance Overview")
        m1, m2, m3, m4, m5 = st.columns(5)
        
        m1.metric("Net Profit", f"${total_profit:,.2f}")
        m2.metric("Win Rate", f"{win_rate:.1f}%")
        m3.metric("Scalp Ratio", f"{scalp_ratio:.1f}%", delta="High Risk" if scalp_ratio > 30 else None, delta_color="inverse")
        m4.metric("Martingale Hits", martingale_count, delta="Grid EA Risk" if martingale_count > 2 else None, delta_color="inverse")
        m5.metric("Latency Arb Risk", latency_arb_count, delta="Toxin Alert" if latency_arb_count > 0 else None, delta_color="inverse")

        # --- EXPORT BUTTONS ---
        st.write("### Actions")
        col_btn1, col_btn2 = st.columns([1, 1])
        
        with col_btn1:
            # Excel Export
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                export_cols = ['Ticket', 'Open Time', 'Close Time', 'Symbol', 'Type', 'Volume', 'Profit', 'Duration_Min', 'Is_Scalp', 'Is_Burst', 'Is_Martingale', 'Is_Latency_Arb']
                df[export_cols].to_excel(writer, sheet_name='All Trades', index=False)
                df[df['Is_Martingale']][export_cols].to_excel(writer, sheet_name='Martingale Risk', index=False)
                df[df['Is_Latency_Arb']][export_cols].to_excel(writer, sheet_name='Latency Arb', index=False)
            st.download_button("📥 Download Full Excel", data=buffer, file_name="Equitas_Intel.xlsx", mime="application/vnd.ms-excel")

        with col_btn2:
            # PDF Export
            pdf_bytes = create_pdf_report(df, report_metrics)
            st.download_button("📄 Download PDF Risk Report", data=pdf_bytes, file_name="Equitas_Risk_Report.pdf", mime="application/pdf")

        st.divider()

        # --- VISUALS SECTION ---
        st.header("📈 Advanced Behavior Visuals")
        c1, c2 = st.columns(2)

        with c1:
            df['Equity'] = df['Profit'].cumsum()
            fig_equity = px.line(df, x='Close Time', y='Equity', title="Client Equity Curve", template="plotly_dark")
            
            # Highlight Martingale points on the equity curve
            martingale_points = df[df['Is_Martingale'] == True]
            if not martingale_points.empty:
                fig_equity.add_scatter(x=martingale_points['Close Time'], y=martingale_points['Equity'], 
                                       mode='markers', marker=dict(color='red', size=10), name='Martingale Bet')
            st.plotly_chart(fig_equity, use_container_width=True)

        with c2:
            fig_risk = px.scatter(df, x="Duration_Min", y="Profit", color="Is_Scalp", size="Volume",
                                 title="Profit vs. Holding Time (Toxin Map)", template="plotly_dark")
            st.plotly_chart(fig_risk, use_container_width=True)

        # --- DETAILED LOGS ---
        st.header("📋 Risk Trade Logs")
        tab1, tab2, tab3 = st.tabs(["All Trades", "🔴 Martingale Bets", "⚡ Latency Arb Suspects"])
        
        display_cols = ['Ticket', 'Open Time', 'Close Time', 'Symbol', 'Type', 'Volume', 'Profit', 'Duration_Min']
        
        with tab1:
            st.dataframe(df[display_cols], use_container_width=True)
        with tab2:
            st.dataframe(df[df['Is_Martingale'] == True][display_cols], use_container_width=True)
        with tab3:
            st.dataframe(df[df['Is_Latency_Arb'] == True][display_cols], use_container_width=True)

    except Exception as e:
        st.error(f"Error processing data. Error details: {e}")
