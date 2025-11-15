import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime
import pandas_ta as ta

st.set_page_config(page_title="Stock to Option Scanner", layout="wide")
st.title("Stock Screener to Best Option Trade (yfinance)")

# ------------------------------------------------------------------
# WATCHLIST
# ------------------------------------------------------------------
WATCHLIST = [
    "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ITC.NS",
    "TATAMOTORS.NS", "MARUTI.NS", "SBIN.NS", "BHARTIARTL.NS", "LT.NS"
]

# ------------------------------------------------------------------
# FETCH & INDICATORS
# ------------------------------------------------------------------
@st.cache_data(ttl=300)
def get_stock_data(symbol, period="90d"):
    try:
        ticker = yf.Ticker(symbol)
        df = ticker.history(period=period)
        if df.empty or len(df) < 50:
            return None
        df = df[['Open', 'High', 'Low', 'Close', 'Volume']].copy()
        df.columns = [col.lower() for col in df.columns]
        return df
    except:
        return None

def add_indicators(df):
    df = df.copy()
    st = ta.supertrend(df['high'], df['low'], df['close'], length=10, multiplier=3)
    df['supertrend'] = st['SUPERT_10_3.0']
    df['st_dir'] = st['SUPERTd_10_3.0']
    df['rsi'] = ta.rsi(df['close'], length=14)
    df['atr'] = ta.atr(df['high'], df['low'], df['close'], length=14)
    df['vol_ma20'] = df['volume'].rolling(20).mean()
    df['vol_surge'] = df['volume'] / df['vol_ma20']
    return df

# ------------------------------------------------------------------
# SCAN STOCKS
# ------------------------------------------------------------------
results = []
with st.spinner("Scanning watchlist with Supertrend + RSI + Volume..."):
    for sym in WATCHLIST:
        try:
            df = get_stock_data(sym)
            if df is None:
                continue
            df = add_indicators(df)
            latest = df.iloc[-1]
            prev = df.iloc[-2]

            bullish_flip = latest['st_dir'] == 1 and prev['st_dir'] == -1
            bearish_flip = latest['st_dir'] == -1 and prev['st_dir'] == 1
            rsi_os = latest['rsi'] < 35
            rsi_ob = latest['rsi'] > 65
            vol_ok = latest['vol_surge'] > 1.3
            atr_ok = latest['atr'] > df['atr'].median()

            score = 0
            signal = "Hold"

            if bullish_flip and rsi_os and vol_ok and atr_ok:
                score = 90 + (35 - latest['rsi'])
                signal = "STRONG BUY"
            elif bullish_flip and vol_ok:
                score = 75
                signal = "BUY"
            elif bearish_flip and rsi_ob and vol_ok:
                score = 80
                signal = "SELL"
            elif rsi_os and vol_ok:
                score = 60
                signal = "WEAK BUY"

            results.append({
                "Symbol": sym.replace(".NS", ""),
                "Close": f"₹{latest['close']:.1f}",
                "RSI": f"{latest['rsi']:.1f}",
                "Trend": "UP" if latest['st_dir'] == 1 else "DOWN",
                "Signal": signal,
                "Score": round(score, 1) if score > 0 else 0,
                "Vol Surge": f"{latest['vol_surge']:.1f}x"
            })
        except Exception as e:
            st.warning(f"Failed {sym}: {e}")
            continue

# ------------------------------------------------------------------
# DISPLAY RESULTS SAFELY
# ------------------------------------------------------------------
st.subheader("Stock Scan Results")

if not results:
    st.warning("No stocks generated signals. Try lowering filters or check market hours (NSE: 9:15 AM – 3:30 PM IST).")
    st.stop()

# Create DataFrame with default columns
scan_df = pd.DataFrame(results, columns=[
    "Symbol", "Close", "RSI", "Trend", "Signal", "Score", "Vol Surge"
])

# Sort only if Score exists and has values
if "Score" in scan_df.columns and scan_df["Score"].sum() > 0:
    scan_df = scan_df.sort_values("Score", ascending=False)

st.dataframe(scan_df.reset_index(drop=True), use_container_width=True)

# ------------------------------------------------------------------
# OPTION CHAIN FOR TOP STOCK
# ------------------------------------------------------------------
top = scan_df.iloc[0]
st.success(f"**Top Pick: {top['Symbol']}** to {top['Signal']}")

underlying = top['Symbol'] + ".NS"
ticker = yf.Ticker(underlying)

expiries = ticker.options
if not expiries:
    st.error(f"No option chain for {top['Symbol']} on Yahoo Finance.")
    st.stop()

expiry = st.selectbox("Select Expiry", expiries, key="expiry_select")

@st.cache_data(ttl=60)
def get_option_chain(symbol, date):
    try:
        opt = ticker.option_chain(date)
        calls = opt.calls.copy()
        puts = opt.puts.copy()
        calls['type'] = 'CE'
        puts['type'] = 'PE'
        chain = pd.concat([calls, puts], ignore_index=True)
        chain = chain[['strike', 'lastPrice', 'bid', 'ask', 'volume', 'openInterest', 'impliedVolatility', 'type']]
        chain.columns = ['strike', 'ltp', 'bid', 'ask', 'volume', 'oi', 'iv', 'type']
        chain['ltp'] = chain[['ltp', 'bid', 'ask']].mean(axis=1)
        chain = chain[chain['volume'] > 0]
        return chain
    except:
        return pd.DataFrame()

opt_df = get_option_chain(underlying, expiry)

if opt_df.empty:
    st.warning("Option chain is empty or not loaded. Try another expiry.")
    st.stop()

st.subheader(f"Option Chain: {top['Symbol']} ({expiry})")

strategy = st.radio("Strategy", ["Long Call", "Long Put", "Cash-Secured Put"], horizontal=True)

opt_df['liquidity'] = opt_df['volume'] + opt_df['oi'] * 0.1
opt_df['prem_iv'] = opt_df['ltp'] / (opt_df['iv'] + 1e-6)

candidates = opt_df.copy()

if
