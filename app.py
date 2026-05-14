import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import io

# --- 1. PAGE SETUP ---
st.set_page_config(page_title="Equitas Ultimate Intel", page_icon="🛡️", layout="wide")

st.title("🛡️ Equitas Trade Intelligence & Behavior Analytics")
st.markdown("Analyze live exported terminal data for risk management and pattern detection.")

# --- 2. SIDEBAR: DATA UPLOAD ---
st.sidebar.header("📂 Upload Equitas Data")
st.sidebar.markdown("Upload your exact Equitas History CSV or Excel file here.")
uploaded_file = st.sidebar.file_uploader("Upload Trade History", type=["csv", "xlsx"])

st.sidebar.divider()
st.sidebar.header("⚙️ Behavior Thresholds")
scalp_min = st.sidebar.slider("Scalp Definition (Minutes)", 1, 10, 3)
burst_limit = st.sidebar.slider("Burst Definition (Trades/Min)", 2, 20, 5)

# --- 3. MAIN INTERFACE ---
if uploaded_file is None:
    st.info("👈 Please upload your Equitas trade history file in the sidebar to view your real data.")
else:
    try:
        # Read the uploaded file
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file)
        else:
            df = pd.read_excel(uploaded_file)
            
        # --- DATA CLEANING & MAPPING ---
        df.columns = df.columns.str.strip()
        
        # 1. Extract only completed trades
        if 'PL' in df.columns:
            df['PL'] = pd.to_numeric(df['PL'].astype(str).str.replace(',', ''), errors='coerce')
            df = df.dropna(subset=['PL']).copy()
            df = df.rename(columns={'PL': 'Profit'})
        else:
            st.error("Could not find a 'PL' column. Make sure this is an Equitas trade history export.")
            st.stop()
            
        # 2. Drop original 'Type' column before renaming B/S
        if 'Type' in df.columns:
            df = df.drop(columns=['Type'])
            
        # 3. Map Equitas columns safely
        df = df.rename(columns={
            'Amount': 'Volume',
            'B/S': 'Type',
            'Time': 'Close Time'
        })
        
        # Ensure critical columns exist
        df = df.dropna(subset=['Open Time', 'Close Time', 'Symbol', 'Volume'])
        
        # 4. Convert Times and calculate duration
        df['Open Time'] = pd.to_datetime(df['Open Time'], errors='coerce')
        df['Close Time'] = pd.to_datetime(df['Close Time'], errors='coerce')
        df = df.dropna(subset=['Open Time', 'Close Time']) 
        
        df['Volume'] = pd.to_numeric(df['Volume'], errors='coerce')

        df['Duration_Min'] = (df['Close Time'] - df['Open Time']).dt.total_seconds() / 60.0
        df['Duration_Min'] = df['Duration_Min'].round(2)

        # --- ANALYTICS CALCULATIONS ---
        df['Is_Scalp'] = df['Duration_Min'] <= scalp_min
        df['Open_Min_Key'] = df['Open Time'].dt.strftime('%Y-%m-%d %H:%M')
        burst_check = df.groupby('Open_Min_Key').size()
        burst_mins = burst_check[burst_check >= burst_limit].index.tolist()
        df['Is_Burst'] = df['Open_Min_Key'].isin(burst_mins)

        df = df.sort_values('Close Time')

        # --- TOP ROW: KPI METRICS ---
        st.header("📊 Performance Overview")
        m1, m2, m3, m4 = st.columns(4)
        
        total_profit = df['Profit'].sum()
        win_rate = (len(df[df['Profit'] > 0]) / len(df)) * 100 if len(df) > 0 else 0
        scalp_ratio = (df['Is_Scalp'].sum() / len(df)) * 100 if len(df) > 0 else 0
        
        m1.metric("Net Profit", f"${total_profit:,.2f}")
        m2.metric("Win Rate", f"{win_rate:.1f}%")
        m3.metric("Scalp Ratio", f"{scalp_ratio:.1f}%", delta="High Risk" if scalp_ratio > 30 else None, delta_color="inverse")
        m4.metric("Burst Events", len(burst_mins), delta="Aggressive" if len(burst_mins) > 0 else None, delta_color="inverse")

        # --- EXPORT BUTTON ---
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
            export_cols = ['Ticket', 'Open Time', 'Close Time', 'Symbol', 'Type', 'Volume', 'Profit', 'Duration_Min', 'Is_Scalp', 'Is_Burst']
            df[export_cols].to_excel(writer, sheet_name='Processed Trades', index=False)
            df[df['Is_Scalp']][export_cols].to_excel(writer, sheet_name='Flagged Scalps', index=False)
        
        st.download_button(
            label="📥 Download Analyzed Report (Excel)",
            data=buffer,
            file_name="Equitas_Analyzed_Report.xlsx",
            mime="application/vnd.ms-excel"
        )

        st.divider()

        # --- VISUALS SECTION ---
        st.header("📈 Behavior Visuals")
        c1, c2 = st.columns(2)

        with c1:
            df['Equity'] = df['Profit'].cumsum()
            fig_equity = px.line(df, x='Close Time', y='Equity', title="Cumulative Profit (Equity Curve)", template="plotly_dark")
            st.plotly_chart(fig_equity, use_container_width=True)

        with c2:
            fig_risk = px.scatter(df, x="Duration_Min", y="Profit", color="Is_Scalp", size="Volume",
                                 title="Profit vs. Holding Time", template="plotly_dark")
            st.plotly_chart(fig_risk, use_container_width=True)

        # --- DETAILED LOGS ---
        st.header("📋 Real Trade Logs")
        tab1, tab2, tab3 = st.tabs(["All Trades", "🚩 Flagged Scalps", "🔥 Burst Trades"])
        
        display_cols = ['Ticket', 'Open Time', 'Close Time', 'Symbol', 'Type', 'Volume', 'Profit', 'Duration_Min', 'Is_Scalp', 'Is_Burst']
        
        with tab1:
            st.dataframe(df[display_cols], use_container_width=True)
        with tab2:
            st.dataframe(df[df['Is_Scalp'] == True][display_cols], use_container_width=True)
        with tab3:
            st.dataframe(df[df['Is_Burst'] == True][display_cols], use_container_width=True)

    except Exception as e:
        # Fixed NameError by removing the st.write(df) request from the crash screen
        st.error(f"Error processing file. Please ensure it is a valid export. Error details: {e}")