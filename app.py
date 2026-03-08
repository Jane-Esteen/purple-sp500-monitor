import streamlit as st
import pandas as pd
from data_layer import DataLayer
from factor_engine import FactorEngine
from macro_engine import MacroEngine
from portfolio_engine import PortfolioEngine
from backtest_engine import simple_backtest
import os
from fredapi import Fred
st.write("FRED_KEY 是否读取成功:", bool(os.environ.get("FRED_API_KEY")))


st.set_page_config(page_title="S&P500宏观量化看板", layout="wide")

st.title("📊 S&P500宏观量化投资系统")
st.caption("使用FRED + Yahoo Finance数据 | 中文展示")

FRED_KEY = os.environ.get("FRED_API_KEY")  # 一定要用这个方式读取
if not FRED_KEY:
    raise ValueError("FRED_API_KEY 未设置，请在 Streamlit Cloud Secrets 中添加")
TOTAL_FUNDS = 50000

# --- 数据加载 ---
fred = Fred(api_key=FRED_KEY)
market = data_layer.market_data()
macro = data_layer.macro_data()

price = market["SPX"]
vix = market["VIX"]

current_price = price.iloc[-1]
current_vix = vix.iloc[-1]

# 宏观数据
ten_year = macro["DGS10"].iloc[-1] / 100
two_year = macro["DGS2"].iloc[-1] / 100
yield_curve = ten_year - two_year
hy_spread = macro["HY"].iloc[-1]
gdp = macro["GDP"].iloc[-1]
wilshire = macro["WILL5000"].iloc[-1]

# --- 因子计算 ---
factor = FactorEngine()
rsi_series = factor.rsi(price)
current_rsi = rsi_series.iloc[-1]
ma200 = factor.moving_average(price, 200).iloc[-1]
dev = (current_price / ma200 - 1) * 100
PE_EST = 25
erp = factor.erp(PE_EST, ten_year)
buffett = factor.buffett_indicator(wilshire, gdp)

# --- 市场热度 & 宏观周期 ---
macro_engine = MacroEngine()
heat_score = macro_engine.market_heat(current_vix, current_rsi, buffett, erp)
regime = macro_engine.macro_regime(yield_curve, hy_spread)

# --- 仓位建议 ---
position = PortfolioEngine.position_model(heat_score)
target_value = TOTAL_FUNDS * position

# --- 回测 ---
curve = simple_backtest(price, rsi_series)

# --- Dashboard 展示 ---
st.subheader("📈 核心指标")
c1, c2, c3, c4 = st.columns(4)
c1.metric("S&P500现价", round(current_price))
c2.metric("VIX指数", round(current_vix,1))
c3.metric("RSI指数", round(current_rsi,1))
c4.metric("200日均线偏离", f"{dev:.2f}%")

st.subheader("📊 宏观指标")
c1, c2, c3, c4 = st.columns(4)
c1.metric("ERP(预期收益率)", f"{erp*100:.2f}%")
c2.metric("Buffett指标", f"{buffett:.2f}")
c3.metric("收益率曲线", f"{yield_curve:.2f}")
c4.metric("高收益利差", f"{hy_spread:.2f}")

st.subheader("🔥 市场热度")
st.metric("热度指数", f"{heat_score:.1f}")
if heat_score > 80:
    st.error("市场泡沫风险高")
elif heat_score > 60:
    st.warning("市场偏高")
elif heat_score > 40:
    st.info("市场合理")
else:
    st.success("市场低估，机会大")

st.subheader("📌 宏观周期")
st.write(regime)

st.subheader("💰 仓位建议")
st.write("目标仓位:", f"{position*100:.0f}%")
st.write("建议投资金额:", f"${target_value:,.0f}")

st.subheader("📉 回测曲线")
tab1, tab2, tab3 = st.tabs(["S&P500价格","VIX指数","策略回测"])
with tab1:
    st.line_chart(price[-500:])
with tab2:
    st.area_chart(vix[-500:])
with tab3:
    st.line_chart(curve[-500:])
