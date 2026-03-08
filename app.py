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
    st.error("❌ 未在 Secrets 中配置 FRED_API_KEY")
    st.stop()

# --- 2. 资产账户逻辑 ---
TOTAL_FUNDS = 50000 
CURRENT_POSITION_PCT = 0.50 
invested_funds = TOTAL_FUNDS * CURRENT_POSITION_PCT
cash_available = TOTAL_FUNDS - invested_funds

st.title("📈 标普500 核心指标量化看板")
st.info(f"**账户概览：** 资金库 **{TOTAL_FUNDS:,.0f} RMB** ｜ 当前仓位 **{CURRENT_POSITION_PCT*100}%** ｜ 可用现金 **{cash_available:,.0f} RMB**")

# --- 3. 核心 ETL 管道 (V4：彻底解决 NoneType 比较与 Pickle 冲突) ---
@st.cache_data(ttl=86400)
def get_market_data_v4():
    # 模拟人为随机延迟，避开云端 IP 并发高峰
    time.sleep(random.uniform(1, 3))
    
    # 初始化输出容器（这种结构最稳，能防止序列化报错）
    data_store = {
        "price": None, "dev": None, "rsi": None, "vix": None,
        "pe": None, "pe_pct": None, "chart_p": None,
        "chart_v": None, "chart_r": None, "hist_pe_pct": None,
        "error": None
    }

    try:
        # A. 批量下载 Yahoo 数据
        tickers = ["^GSPC", "^VIX", "SPY"]
        raw_data = yf.download(tickers, period='2y', progress=False, timeout=20)
        
        if raw_data.empty:
            data_store["error"] = "Yahoo Finance 限流中"
            return data_store

        # 提取标普 500
        sp500_close = raw_data['Close']['^GSPC'].dropna()
        sp500 = pd.Series(sp500_close.values.flatten(), index=sp500_close.index)
        data_store["price"] = float(sp500.iloc[-1])
        
        # 提取 VIX
        vix_series = raw_data['Close']['^VIX'].dropna()
        data_store["vix"] = float(vix_series.iloc[-1])
        
        # 提取 SPY PE
        data_store["pe"] = yf.Ticker('SPY').info.get('trailingPE', 26.8)
        
        # B. 技术指标计算
        ma200_series = sp500.rolling(window=200).mean().dropna()
        data_store["dev"] = ((data_store["price"] / ma200_series.iloc[-1]) - 1) * 100
        
        delta = sp500.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rsi_series = 100 - (100 / (1 + (gain / loss))).dropna()
        data_store["rsi"] = float(rsi_series.iloc[-1])

        # C. FRED 历史百分位 (数据降级逻辑)
        try:
            dy_history = fred.get_series('SP500DY').dropna().tail(240)
            current_pe = data_store["pe"]
            data_store["pe_pct"] = float((dy_history > (1/current_pe * 100)).mean() * 100)
            
            # 构造百分位趋势图数据
            implied_eps = data_store["price"] / current_pe
            data_store["hist_pe_pct"] = sp500.apply(lambda x: (dy_history > (1/(x/implied_eps) * 100)).mean() * 100)
        except Exception:
            pass # 允许百分位缺失，不中断主流程

        # D. 图表对齐
        data_store["chart_p"] = pd.DataFrame({"现价": sp500[-252:], "200日线": ma200_series[-252:]})
        data_store["chart_v"] = vix_series[-252:]
        data_store["chart_r"] = rsi_series[-252:]

    except Exception as e:
        data_store["error"] = str(e)

    return data_store

# --- 4. 运行管道 ---
res = get_market_data_v4()

# --- 5. 前端渲染逻辑（强化空值校验） ---
if res.get("error"):
    st.error(f"🔴 数据抓取异常: {res['error']}")
    st.info("提示：请在右上角菜单点击 'Clear Cache' 后等待几分钟再刷新。")
else:
    # 渲染卡片指标
    st.markdown("### 1️⃣ 实时监控指标")
    c1, c2, c3, c4 = st.columns(4)
    
    # 针对 PE 百分位的 NoneType 保护
    pe_v = res.get("pe")
    pe_p = res.get("pe_pct")
    if pe_v and pe_p is not None:
        status = "高估" if pe_p > 80 else ("低估" if pe_p < 30 else "合理")
        c1.metric("1. 真实 PE (20年分位)", f"{pe_v:.2f}倍", f"分位: {pe_p:.1f}% ({status})", delta_color="inverse" if pe_p > 80 else "normal")
    else:
        c1.metric("1. 真实 PE", "获取中", "❌ 接口限流", delta_color="off")
    
    if res.get("dev") is not None:
        c2.metric("2. 200日线偏离", f"{res['dev']:+.2f}%", f"现价: {res['price']:,.0f}")
    
    if res.get("vix") is not None:
        c3.metric("3. VIX 恐慌指数", f"{res['vix']:.2f}", "恐慌" if res["vix"] > 25 else "平稳", delta_color="inverse" if res["vix"] > 25 else "normal")
        
    if res.get("rsi") is not None:
        c4.metric("4. 14日 RSI 动量", f"{res['rsi']:.1f}", "超买" if res["rsi"] > 70 else ("超卖" if res["rsi"] < 30 else "中性"), delta_color="normal" if res["rsi"] < 30 else "inverse")

    # 历史图表
    st.markdown("---")
    t1, t2, t3 = st.tabs(["估值百分位走势", "价格走势图", "情绪动量图"])
    with t1:
        if res.get("hist_pe_pct") is not None:
            st.line_chart(res["hist_pe_pct"].tail(252), color="#8b5cf6")
        else: st.warning("PE 趋势图暂时无法加载")
    with t2:
        if res.get("chart_p") is not None:
            st.line_chart(res["chart_p"], color=["#3b82f6", "#ef4444"])
    with t3:
        cv, cr = st.columns(2)
        if res.get("chart_v") is not None:
            with cv: st.area_chart(res["chart_v"], color="#f59e0b")
        if res.get("chart_r") is not None:
            with cr: st.line_chart(res["chart_r"], color="#10b981")

    # --- 6. 量化决策逻辑（空值安全版） ---
    st.markdown("---")
    st.markdown("### 2️⃣ 机器人决策建议")
    
    # 默认值处理，防止比较时崩溃
    safe_pe_pct = pe_p if pe_p is not None else 50.0
    safe_vix = res.get("vix") if res.get("vix") is not None else 20.0
    safe_rsi = res.get("rsi") if res.get("rsi") is not None else 50.0
    safe_dev = res.get("dev") if res.get("dev") is not None else 0.0
    
    risk_score = (safe_pe_pct * 0.4) + (safe_rsi * 0.3) + ((100 - min(safe_vix*2, 100)) * 0.3)
    
    if safe_pe_pct > 85 and safe_rsi > 65:
        st.error(f"**🔴 【建议减仓】风险分: {risk_score:.1f}** —— 估值极高，动能透支。")
    elif safe_vix > 25 and safe_rsi < 35:
        st.success(f"**🟢 【建议买入】风险分: {risk_score:.1f}** —— 恐慌性超卖，建议动用 5,000 RMB。")
    elif safe_dev < -5:
        st.success(f"**🟢 【强力买入】风险分: {risk_score:.1f}** —— 价格跌破 200 日线，长线买点。")
    else:
        st.warning(f"**🟡 【持仓观望】风险分: {risk_score:.1f}** —— 指标中性。维持当前 50% 仓位。")

with st.expander("📚 策略逻辑字典"):
    st.write("数据源: FRED, Yahoo Finance. 容错处理: 开启. 缓存状态: V4版本.")
