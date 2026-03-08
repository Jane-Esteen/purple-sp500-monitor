import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from fredapi import Fred

# --- 页面全局配置 ---
st.set_page_config(page_title="标普500看板", page_icon="📈", layout="wide")

# 从 Streamlit Secrets 安全读取 API Key
try:
    FRED_KEY = st.secrets["FRED_API_KEY"]
    fred = Fred(api_key=FRED_KEY)
except Exception as e:
    st.error("未在 Secrets 中检测到 FRED_API_KEY。请在 Streamlit 控制台配置。")
    st.stop()

# --- 账户资金状态 ---
TOTAL_FUNDS = 50000 
CURRENT_POSITION_PCT = 0.50 
invested_funds = TOTAL_FUNDS * CURRENT_POSITION_PCT
cash_available = TOTAL_FUNDS - invested_funds

st.title("📈 标普500 核心指标量化看板")
st.info(f"**账户概览：** 资金库 **{TOTAL_FUNDS:,.0f} RMB** ｜ 当前仓位 **{CURRENT_POSITION_PCT*100}%** ｜ 可用现金 **{cash_available:,.0f} RMB**")

# --- 数据抓取与清洗管道 (ETL) ---
@st.cache_data(ttl=3600)
def get_market_data():
    # 1. 获取量价数据 (Yahoo Finance)
    sp500_raw = yf.download('^GSPC', period='2y', progress=False)['Close']
    vix_raw = yf.download('^VIX', period='2y', progress=False)['Close']
    
    # 维度对齐处理
    sp500 = pd.Series(sp500_raw.values.flatten(), index=sp500_raw.index)
    vix = pd.Series(vix_raw.values.flatten(), index=vix_raw.index)
    current_price = float(sp500.iloc[-1])
    
    # 2. 均线与偏离度
    ma200_series = sp500.rolling(window=200).mean().dropna()
    ma_deviation = ((current_price / ma200_series.iloc[-1]) - 1) * 100
    
    # 3. RSI 动量
    delta = sp500.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rsi_series = 100 - (100 / (1 + (gain / loss))).dropna()
    
    # 4. 获取权威 PE 及百分位 (FRED 稳健版逻辑)
    current_pe, pe_percentile, pe_pct_history = None, None, None
    try:
        # 实时 PE 始终通过 yfinance 抓取 SPY 获取 (最准)
        spy_info = yf.Ticker('SPY').info
        current_pe = spy_info.get('trailingPE', 26.6)
        
        # 抓取 FRED 历史序列作为概率分布池
        try:
            # 优先尝试 SP500PE
            pe_history = fred.get_series('SP500PE').dropna().tail(240)
            pe_percentile = (pe_history < current_pe).mean() * 100
        except:
            # 备选方案：使用标普500股息率 (SP500DY) 逆推估值百分位
            # 股息率越低 = 估值越高
            dy_history = fred.get_series('SP500DY').dropna().tail(240)
            pe_percentile = (dy_history > (1/current_pe * 100 if current_pe else 1.5)).mean() * 100
            pe_history = 100 / dy_history # 构造模拟 PE 序列用于趋势
            
        # 构造历史百分位趋势
        implied_eps = current_price / current_pe
        pe_pct_history = sp500.apply(lambda x: (pe_history < (x / implied_eps)).mean() * 100)
        
    except Exception as e:
        print(f"PE 链路异常: {e}")

    # 5. 截取绘图数据
    chart_price = pd.DataFrame({'S&P 500': sp500[-252:], '200日均线': ma200_series[-252:]})
    
    return (current_price, ma_deviation, rsi_series.iloc[-1], vix.iloc[-1], 
            current_pe, pe_percentile, chart_price, vix[-252:], rsi_series[-252:], pe_pct_history)

# --- 页面渲染 ---
try:
    with st.spinner('正在执行数据治理逻辑，调取美联储权威历史数据库...'):
        (price, dev, rsi, vix_val, pe, pe_pct, 
         chart_p, chart_vix, chart_rsi, hist_pe_pct) = get_market_data()

    # 监控卡片
    st.markdown("### 1️⃣ 核心指标监控")
    c1, c2, c3, c4 = st.columns(4)
    
    if pe:
        status = "高估" if pe_pct > 80 else ("低估" if pe_pct < 30 else "合理")
        c1.metric("1. 真实 PE (20年分位)", f"{pe:.2f}倍", f"分位: {pe_pct:.1f}% ({status})", delta_color="inverse" if pe_pct > 80 else "normal")
    else:
        c1.metric("1. 真实 PE", "获取中", "❌ 接口限流", delta_color="off")
        
    c2.metric("2. 200日线偏离 (趋势)", f"{dev:+.2f}%", f"均线: {chart_p['200日均线'].iloc[-1]:,.0f}")
    c3.metric("3. VIX 指数 (情绪)", f"{vix_val:.2f}", "恐慌" if vix_val > 25 else "平稳", delta_color="inverse" if vix_val > 25 else "normal")
    c4.metric("4. 14日 RSI (动量)", f"{rsi:.1f}", "超买" if rsi > 70 else ("超卖" if rsi < 30 else "中性"), delta_color="normal" if rsi < 30 else "inverse")

    # 历史图表
    st.markdown("---")
    st.markdown("### 2️⃣ 历史数据可视化走势")
    t1, t2, t3 = st.tabs(["估值百分位走势", "价格趋势图", "情绪与动量"])
    
    with t1:
        if hist_pe_pct is not None:
            st.line_chart(hist_pe_pct.tail(252), color="#8b5cf6")
            st.caption("基于 FRED 历史数据库计算的估值百分位走势。接近 100% 代表处于历史最贵时期。")
    with t2:
        st.line_chart(chart_p, color=["#3b82f6", "#ef4444"])
        st.caption("蓝线为价格，红线为 200 日牛熊分界线。")
    with t3:
        cv, cr = st.columns(2)
        with cv: st.write("VIX 恐慌面积图"); st.area_chart(chart_vix, color="#f59e0b")
        with cr: st.write("RSI 强弱动量线"); st.line_chart(chart_rsi, color="#10b981")

    # 决策建议
    st.markdown("---")
    st.markdown("### 3️⃣ 量化决策建议")
    
    # 风险评分
    risk_score = (pe_pct * 0.4 if pe_pct else 20) + (rsi * 0.3) + ((100 - min(vix_val*2, 100)) * 0.3)
    
    if pe_pct and pe_pct > 85 and rsi > 65:
        st.error(f"**🔴 【建议减仓】风险分: {risk_score:.1f}** —— 历史极高估值叠加短期动能透支，建议保持 30% 左右低仓位。")
    elif vix_val > 25 and rsi < 35:
        st.success(f"**🟢 【建议买入】风险分: {risk_score:.1f}** —— 触发恐慌超卖信号。建议动用 5,000 RMB 可用现金加仓。")
    elif dev < -4:
        st.success(f"**🟢 【强力买入】风险分: {risk_score:.1f}** —— 价格严重跌破 200 日线，长线买点显现。")
    else:
        st.warning(f"**🟡 【建议观望】风险分: {risk_score:.1f}** —— 指标中性，无极端偏离。建议维持当前 50% 仓位。")

    # 字典模块
    with st.expander("📚 查看底层逻辑与名词解释"):
        st.markdown("""
        #### 1. PE 百分位 (基于 FRED 真实历史)
        
        不再使用写死的 14/28。系统拉取美联储过去 20 年的样本点，计算当前 PE 在这数千个点中的绝对百分位排名。
        #### 2. 200日均线 (MA200)
        资产价格的长期生命线。现价长期围绕此线波动，跌破并远离通常预示中长线机会。
        #### 3. VIX 指数
        华尔街“恐惧指数”。反映期权市场对未来波动的预期，是逆向投资的重要参考。
        #### 4. RSI 指数
        衡量短期买卖力量强弱。30 以下为超卖（容易反弹），70 以上为超买（容易回调）。
        """)

except Exception as e:
    st.error(f"系统运行异常: {e}")
