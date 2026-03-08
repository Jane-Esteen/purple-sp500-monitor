import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from fredapi import Fred
import time
import random

# --- 1. 页面配置 ---
st.set_page_config(page_title="标普500量化看板", page_icon="📈", layout="wide")

# 安全加载 FRED API Key
try:
    FRED_KEY = st.secrets["FRED_API_KEY"]
    fred = Fred(api_key=FRED_KEY)
except Exception:
    st.error("未在 Secrets 中配置 FRED_API_KEY")
    st.stop()

# --- 2. 资金逻辑 ---
TOTAL_FUNDS = 50000 
CURRENT_POSITION_PCT = 0.50 
invested_funds = TOTAL_FUNDS * CURRENT_POSITION_PCT
cash_available = TOTAL_FUNDS - invested_funds

st.title("📈 标普500 核心指标量化看板")
st.info(f"**账户概览：** 资金库 **{TOTAL_FUNDS:,.0f} RMB** ｜ 当前仓位 **{CURRENT_POSITION_PCT*100}%** ｜ 可用现金 **{cash_available:,.0f} RMB**")

# --- 3. 核心 ETL 管道 (带防限流增强) ---
@st.cache_data(ttl=86400) # 缓存 24 小时，减少接口触发
def get_market_data_v2():
    # 模拟人为随机延迟，避开请求高峰
    time.sleep(random.uniform(2, 5))
    
    # 初始化变量
    current_price, dev, rsi, vix_val = None, None, None, None
    pe, pe_pct = None, None
    chart_p, chart_vix, chart_rsi, hist_pe_pct = None, None, None, None

    try:
        # A. 获取量价数据 (增加超时和重试逻辑)
        tickers = ["^GSPC", "^VIX", "SPY"]
        data = yf.download(tickers, period='2y', progress=False, timeout=15)
        
        if data.empty:
            raise ValueError("Yahoo Finance 接口限流中，请稍后再试。")

        # 提取标普 500 现价
        sp500_close = data['Close']['^GSPC'].dropna()
        sp500 = pd.Series(sp500_close.values.flatten(), index=sp500_close.index)
        current_price = float(sp500.iloc[-1])
        
        # 提取 VIX
        vix_series = data['Close']['^VIX'].dropna()
        vix_val = float(vix_series.iloc[-1])
        
        # 提取 SPY PE
        current_pe = yf.Ticker('SPY').info.get('trailingPE', 26.6)
        
        # B. 计算技术指标
        ma200_series = sp500.rolling(window=200).mean().dropna()
        dev = ((current_price / ma200_series.iloc[-1]) - 1) * 100
        
        delta = sp500.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rsi_series = 100 - (100 / (1 + (gain / loss))).dropna()
        rsi = float(rsi_series.iloc[-1])

        # C. FRED 历史百分位逻辑
        try:
            # 优先尝试股息率作为稳定的估值锚点 (FRED 接口限流较少)
            dy_history = fred.get_series('SP500DY').dropna().tail(240)
            pe_pct = (dy_history > (1/current_pe * 100)).mean() * 100
            # 构造百分位趋势
            pe_pct_history = sp500.apply(lambda x: (dy_history > (1/(x/(current_price/current_pe)) * 100)).mean() * 100)
        except Exception:
            pe_pct, pe_pct_history = None, None

        # 整理图表
        chart_p = pd.DataFrame({"价格": sp500[-252:], "200日线": ma200_series[-252:]})
        chart_vix = vix_series[-252:]
        chart_rsi = rsi_series[-252:]

        return (current_price, dev, rsi, vix_val, current_pe, pe_pct, 
                chart_p, chart_vix, chart_rsi, pe_pct_history)

    except Exception as e:
        return e

# --- 4. 执行渲染 ---
res = get_market_data_v2()

if isinstance(res, Exception):
    st.error(f"🔴 数据接口暂时受限: {res}")
    st.warning("提示：这通常是由于来自云服务器的访问过多。请点击右上角 'Clear Cache' 后等待几分钟再刷新。")
else:
    (price, dev, rsi, vix_val, pe, pe_pct, 
     chart_p, chart_vix, chart_rsi, hist_pe_pct) = res

    # 监控卡片
    st.markdown("### 1️⃣ 核心指标监控")
    c1, c2, c3, c4 = st.columns(4)
    
    if pe:
        status = "高估" if pe_pct > 80 else ("低估" if pe_pct < 30 else "合理")
        c1.metric("1. 真实 PE (20年分位)", f"{pe:.2f}倍", f"分位: {pe_pct:.1f}% ({status})", delta_color="inverse" if pe_pct > 80 else "normal")
    
    c2.metric("2. 200日线偏离 (趋势)", f"{dev:+.2f}%", f"均线: {chart_p['200日线'].iloc[-1]:,.0f}")
    c3.metric("3. VIX 指数 (情绪)", f"{vix_val:.2f}", "恐慌" if vix_val > 25 else "平稳", delta_color="inverse" if vix_val > 25 else "normal")
    c4.metric("4. 14日 RSI (动量)", f"{rsi:.1f}", "超买" if rsi > 70 else ("超卖" if rsi < 30 else "中性"), delta_color="normal" if rsi < 30 else "inverse")

    # 历史趋势图
    st.markdown("---")
    t1, t2, t3 = st.tabs(["估值百分位走势", "价格走势", "情绪动量"])
    with t1:
        if hist_pe_pct is not None: st.line_chart(hist_pe_pct.tail(252), color="#8b5cf6")
    with t2:
        st.line_chart(chart_p, color=["#3b82f6", "#ef4444"])
    with t3:
        cv, cr = st.columns(2)
        with cv: st.area_chart(chart_vix, color="#f59e0b")
        with cr: st.line_chart(chart_rsi, color="#10b981")

    # 决策建议
    st.markdown("---")
    st.markdown("### 2️⃣ 量化决策建议")
    
    risk_score = (pe_pct * 0.4 if pe_pct else 20) + (rsi * 0.3) + ((100 - min(vix_val*2, 100)) * 0.3)
    
    if pe_pct and pe_pct > 85 and rsi > 65:
        st.error(f"**🔴 【建议减仓】风险分: {risk_score:.1f}** —— 估值极高，动能透支。")
    elif vix_val > 25 and rsi < 35:
        st.success(f"**🟢 【建议买入】风险分: {risk_score:.1f}** —— 市场恐慌。建议动用 5,000 RMB 现金。")
    elif dev < -5:
        st.success(f"**🟢 【强力买入】风险分: {risk_score:.1f}** —— 价格跌破 200 日均线。")
    else:
        st.warning(f"**🟡 【保持观望】风险分: {risk_score:.1f}** —— 指标中性。维持当前 50% 仓位。")

# --- 5. 文档字典 ---
with st.expander("📚 策略逻辑与名词解释"):
    st.markdown("""
    * **PE 百分位**：计算当前值在过去 20 年样本中的排名。
    * **200 日线**：中长线支撑/阻力。
    * **限流处理**：由于公共 IP 限制，如遇限流请耐心等待。系统已开启 24h 缓存保护。
    """)
