import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
from fredapi import Fred

# ================================
# CONFIG
# ================================

st.set_page_config(
    page_title="Macro Allocation Dashboard",
    layout="wide"
)

FRED_API_KEY = "YOUR_FRED_API_KEY"

TOTAL_FUNDS = 50000

fred = Fred(api_key=FRED_API_KEY)

st.title("📈 Macro Allocation Dashboard")

st.caption("S&P500 Macro Quant System")

# ================================
# DATA FETCH
# ================================

@st.cache_data(ttl=3600)
def load_market():

    spx = yf.download("^GSPC", start="1990-01-01")['Close']

    vix = yf.download("^VIX", start="1990-01-01")['Close']

    df = pd.DataFrame({
        "SPX": spx,
        "VIX": vix
    })

    return df


@st.cache_data(ttl=3600)
def load_macro():

    dgs10 = fred.get_series("DGS10")

    dgs2 = fred.get_series("DGS2")

    gdp = fred.get_series("GDP")

    wilshire = fred.get_series("WILL5000PRFC")

    hy = fred.get_series("BAMLH0A0HYM2")

    df = pd.DataFrame({
        "DGS10": dgs10,
        "DGS2": dgs2,
        "GDP": gdp,
        "WILL5000": wilshire,
        "HY": hy
    })

    return df


market = load_market()

macro = load_macro()

# ================================
# CORE DATA
# ================================

price = market['SPX']
vix = market['VIX']

current_price = price.iloc[-1]
current_vix = vix.iloc[-1]

ten_year = macro['DGS10'].iloc[-1] / 100
two_year = macro['DGS2'].iloc[-1] / 100

gdp = macro['GDP'].iloc[-1]
wilshire = macro['WILL5000'].iloc[-1]

hy_spread = macro['HY'].iloc[-1]

yield_curve = ten_year - two_year

# ================================
# FACTOR ENGINE
# ================================

def calc_rsi(series, window=14):

    delta = series.diff()

    gain = delta.clip(lower=0)

    loss = -delta.clip(upper=0)

    avg_gain = gain.rolling(window).mean()

    avg_loss = loss.rolling(window).mean()

    rs = avg_gain / avg_loss

    rsi = 100 - (100 / (1 + rs))

    return rsi


rsi = calc_rsi(price)

current_rsi = rsi.iloc[-1]

ma200 = price.rolling(200).mean().iloc[-1]

dev = (current_price / ma200 - 1) * 100

# ================================
# VALUATION
# ================================

PE_ESTIMATE = 25

earnings_yield = 1 / PE_ESTIMATE

erp = earnings_yield - ten_year

buffett = wilshire / gdp

# ================================
# MARKET HEAT MODEL
# ================================

score_vix = 100 - min(current_vix * 3, 100)

score_rsi = current_rsi

score_buffett = min(buffett * 50, 100)

score_erp = max(0, min(erp * 200, 100))

market_heat = (
    0.25 * score_vix +
    0.25 * score_rsi +
    0.25 * score_buffett +
    0.25 * score_erp
)

# ================================
# MACRO REGIME
# ================================

def macro_regime():

    if yield_curve < 0 and hy_spread > 5:
        return "Recession Risk"

    if yield_curve > 1 and hy_spread < 3:
        return "Expansion"

    return "Late Cycle"

regime = macro_regime()

# ================================
# PORTFOLIO ENGINE
# ================================

def position_model(score):

    if score > 80:
        return 0.2

    if score > 65:
        return 0.4

    if score > 50:
        return 0.6

    if score > 35:
        return 0.8

    return 1.0


position = position_model(market_heat)

target_value = TOTAL_FUNDS * position

# ================================
# BACKTEST
# ================================

def backtest():

    signal = (rsi < 40).astype(int)

    returns = price.pct_change()

    strategy = returns * signal.shift()

    curve = (1 + strategy).cumprod()

    return curve


curve = backtest()

# ================================
# DASHBOARD
# ================================

st.subheader("Market Overview")

c1, c2, c3, c4 = st.columns(4)

c1.metric("S&P500", round(current_price))

c2.metric("VIX", round(current_vix,1))

c3.metric("RSI", round(current_rsi,1))

c4.metric("MA200 Dev", f"{dev:.2f}%")

st.divider()

st.subheader("Macro Indicators")

c1, c2, c3, c4 = st.columns(4)

c1.metric("ERP", f"{erp*100:.2f}%")

c2.metric("Buffett Indicator", f"{buffett:.2f}")

c3.metric("Yield Curve", f"{yield_curve:.2f}")

c4.metric("HY Spread", f"{hy_spread:.2f}")

st.divider()

st.subheader("Market Heat Score")

st.metric("Heat Score", f"{market_heat:.1f}")

if market_heat > 80:

    st.error("Market Bubble")

elif market_heat > 60:

    st.warning("Market Overvalued")

elif market_heat > 40:

    st.info("Fair Value")

else:

    st.success("Undervalued")

st.divider()

st.subheader("Macro Regime")

st.write(regime)

st.divider()

st.subheader("Portfolio Allocation")

st.write("Target Position:", f"{position*100:.0f}%")

st.write("Suggested Investment:", f"${target_value:,.0f}")

st.divider()

# ================================
# CHARTS
# ================================

tab1, tab2, tab3 = st.tabs(["S&P500","VIX","Strategy"])

with tab1:

    st.line_chart(price[-500:])

with tab2:

    st.area_chart(vix[-500:])

with tab3:

    st.line_chart(curve)
