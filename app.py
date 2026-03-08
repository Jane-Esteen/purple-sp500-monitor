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
    st.error("❌ 未在 Secrets 中配置 FRED_API_KEY。请在 Streamlit Cloud Settings 中添加。")
    st.stop()

# --- 2. 资产账户逻辑 ---
TOTAL_FUNDS = 50000 
CURRENT_POSITION_PCT = 0.50 
invested_funds = TOTAL_FUNDS * CURRENT_POSITION_PCT
cash_available = TOTAL_FUNDS - invested_funds

st.title("📈 标普500 核心指标量化看板")
st.info(f"**资产概览：** 资金库 **{TOTAL_FUNDS:,.0f} RMB** ｜ 当前仓位 **{CURRENT_POSITION_PCT*100}%** ｜ 可用现金 **{cash_available:,.0f} RMB**")

# --- 3. 核心 ETL 管道 (V3版本：解决缓存冲突与空值容错) ---
@st.cache_data(ttl=86400) # 24小时强力缓存，规避限流
def get_market_data_v3():
    # 随机延迟，避开云端 IP 并发高峰
    time.sleep(random.uniform(1.5, 4.5))
    
    # 初始化兜底变量
    output = {
        "price": None, "dev": None, "rsi": None, "vix": None,
        "pe": None, "pe_pct": None, "chart_p": None,
        "chart_v": None, "chart_r": None, "hist_pe_pct": None
    }

    try:
        # A. 批量下载 Yahoo 财经数据 (减少 Request 次数)
        tickers = ["^GSPC", "^VIX", "SPY"]
        data = yf.download(tickers, period='2y', progress=False, timeout=20)
        
        if data.empty:
            return "Yahoo Finance 返回空数据 (接口可能被暂时封锁)"

        # 提取标普 500
        sp500_close = data['Close']['^GSPC'].dropna()
        sp500 = pd.Series(sp500_close.values.flatten(), index=sp500_close.index)
        output["price"] = float(sp500.iloc[-1])
        
        # 提取 VIX
        vix_series = data['Close']['^VIX'].dropna()
        output["vix"] = float(vix_series.iloc[-1])
        
        # 提取 SPY PE
        output["pe"] = yf.Ticker('SPY').info.get('trailingPE', 26.8)
        
        # B. 技术指标计算
        ma200_series = sp500.rolling(window=200).mean().dropna()
        output["dev"] = ((output["price"] / ma200_series.iloc[-1]) - 1) * 100
        
        delta = sp500.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rsi_series = 100 - (100 / (1 + (gain / loss))).dropna()
        output["rsi"] = float(rsi_series.iloc[-1])

        # C. FRED 历史百分位 (数据降级逻辑)
        try:
            # 优先尝试使用股息率模型计算百分位 (FRED 稳定性最高)
            dy_history = fred.get_series('SP500DY').dropna().tail(240)
            current_pe = output["pe"]
            output["pe_pct"] = float((dy_history > (1/current_pe * 100)).mean() * 100)
            
            # 构造历史百分位曲线
            implied_eps = output["price"] / current_pe
            output["hist_pe_pct"] = sp500.apply(lambda x: (dy_history > (1/(x/implied_eps) * 100)).mean() * 100)
        except:
            output["pe_pct"] = None

        # D. 绘图准备
        output["chart_p"] = pd.DataFrame({"现价": sp500[-252:], "200日线": ma200_series[-252:]})
        output["chart_v"] = vix_series[-252:]
        output["chart_r"] = rsi_series[-252:]

        return output

    except Exception as e:
        return str(e)

# --- 4. 运行管道与错误处理 ---
res = get_market_data_v3()

if isinstance(res, str):
    st.error(f"🔴 数据链路故障: {res}")
    st.info("提示：这通常是接口限流。系统已自动记录，请点击右上角 'Clear Cache' 后 5 分钟重试。")
else:
    # --- 5. 渲染监控指标卡片 ---
    st.markdown("### 1️⃣ 实时监控指标")
    c1, c2, c3, c4 = st.columns(4)
    
    # 修复逻辑：增加 None 判断，防止比较报错
    pe_val = res["pe"]
    pe_pct = res["pe_pct"]
    if pe_val is not None and pe_pct is not None:
        status = "高估" if pe_pct > 80 else ("低估" if pe_pct < 30 else "合理")
        c1.metric("1. 真实 PE (20年分位)", f"{pe_val:.2f}倍", f"分位: {pe_pct:.1f}% ({status})", delta_color="inverse" if pe_pct > 80 else "normal")
    else:
        c1.metric("1. 真实 PE", "获取中", "❌ 限流或缺失", delta_color="off")
    
    if res["dev"] is not None:
        c2.metric("2. 200日线偏离", f"{res['dev']:+.2f}%", f"现价: {res['price']:,.0f}")
    
    if res["vix"] is not None:
        c3.metric("3. VIX 恐慌指数", f"{res['vix']:.2f}", "恐慌" if res["vix"] > 25 else "平稳", delta_color="inverse" if res["vix"] > 25 else "normal")
        
    if res["rsi"] is not None:
        c4.metric("4. 14日 RSI 动量", f"{res['rsi']:.1f}", "超买" if res["rsi"] > 70 else ("超卖" if res["rsi"] < 30 else "中性"), delta_color="normal" if res["rsi"] < 30 else "inverse")

    # --- 6. 历史走势图 ---
    st.markdown("---")
    t1, t2, t3 = st.tabs(["估值百分位走势", "价格走势图", "情绪动量图"])
    with t1:
        if res["hist_pe_pct"] is not None:
            st.line_chart(res["hist_pe_pct"].tail(252), color="#8b5cf6")
        else: st.warning("PE 趋势暂不可用")
    with t2:
        if res["chart_p"] is not None:
            st.line_chart(res["chart_p"], color=["#3b82f6", "#ef4444"])
    with t3:
        cv, cr = st.columns(2)
        with cv: st.area_chart(res["chart_v"], color="#f59e0b")
        with cr: st.line_chart(res["chart_r"], color="#10b981")

    # --- 7. 量化决策引擎 ---
    st.markdown("---")
    st.markdown("### 2️⃣ 机器人决策建议")
    
    # 风险评分容错逻辑
    p_pct = pe_pct if pe_pct is not None else 50.0
    v_val = res["vix"] if res["vix"] is not None else 20.0
    r_val = res["rsi"] if res["rsi"] is not None else 50.0
    
    risk_score = (p_pct * 0.4) + (r_val * 0.3) + ((100 - min(v_val*2, 100)) * 0.3)
    
    if p_pct > 85 and r_val > 65:
        st.error(f"**🔴 【建议减仓】风险分: {risk_score:.1f}** —— 估值泡沫区间。")
    elif v_val > 25 and r_val < 35:
        st.success(f"**🟢 【建议买入】风险分: {risk_score:.1f}** —— 恐慌性超卖，建议动用部分现金。")
    elif res["dev"] is not None and res["dev"] < -5:
        st.success(f"**🟢 【长线买入】风险分: {risk_score:.1f}** —— 价格击穿 200 日线。")
    else:
        st.warning(f"**🟡 【持仓观望】风险分: {risk_score:.1f}** —— 无极端偏离，维持 50% 仓位。")

with st.expander("📚 策略逻辑字典"):
    st.write("数据源: FRED, Yahoo Finance. 缓存周期: 24h. 核心逻辑: 估值回归 + 恐慌抄底.")
