import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np

# --- 页面配置 ---
st.set_page_config(page_title="标普500看板", page_icon="📈", layout="wide")
st.title("📈 标普500看板")

# --- 账户资金状态 ---
TOTAL_FUNDS = 50000  # 总资金
CURRENT_POSITION_PCT = 0.50  # 仓位比例
invested_funds = TOTAL_FUNDS * CURRENT_POSITION_PCT
cash_available = TOTAL_FUNDS - invested_funds

st.info(f"**资产概览：** 资金库 **{TOTAL_FUNDS:,.0f} RMB** ｜ 当前仓位 **{CURRENT_POSITION_PCT*100}%** ({invested_funds:,.0f} RMB) ｜ 可用现金 **{cash_available:,.0f} RMB**")

# --- 数据抓取与计算 ---
@st.cache_data(ttl=3600) # 缓存1小时
def get_market_data():
    # 获取过去2年的价格数据（用于计算200日均线和趋势图）
    sp500 = yf.download('^GSPC', period='2y', progress=False)['Close']
    vix = yf.download('^VIX', period='2y', progress=False)['Close']
    spy = yf.Ticker('SPY') # 使用SPY ETF作为获取基本面数据的代理
    
    # 1. 价格与均线
    current_price = float(sp500.iloc[-1])
    ma200_series = sp500.rolling(window=200).mean().dropna()
    ma200 = float(ma200_series.iloc[-1])
    ma_deviation = ((current_price / ma200) - 1) * 100
    
    # 2. RSI (14日计算)
    delta = sp500.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    rsi_series = 100 - (100 / (1 + rs))
    rsi_14 = float(rsi_series.dropna().iloc[-1])
    
    # 3. VIX
    current_vix = float(vix.iloc[-1])
    
    # 4. 动态 PE 获取与百分位估算
    try:
        current_pe = spy.info.get('trailingPE', 25.0) # 获取实时PE
    except:
        current_pe = 25.0 # 防御性容错
        
    # 近20年标普500 PE常态分布：均值约16，极高风险区>28
    # 使用动态截断算法映射0-100的百分位估值
    pe_percentile = min(100.0, max(0.0, ((current_pe - 14) / (28 - 14)) * 100))

    # 准备近1年的图表数据 (约252个交易日)
    chart_price = pd.DataFrame({'S&P 500': sp500[-252:], '200日均线': ma200_series[-252:]})
    chart_vix = vix[-252:]
    chart_rsi = rsi_series[-252:]
    
    return current_price, ma_deviation, rsi_14, current_vix, current_pe, pe_percentile, chart_price, chart_vix, chart_rsi

try:
    with st.spinner('正在从华尔街拉取最新量价与基本面数据...'):
        (current_price, ma_deviation, rsi_14, current_vix, 
         current_pe, pe_percentile, chart_price, chart_vix, chart_rsi) = get_market_data()
    
    # --- 核心数据指标卡片 ---
    st.markdown("### 📊 核心监控指标")
    col1, col2, col3, col4 = st.columns(4)
    
    pe_status = "高估" if pe_percentile > 80 else ("低估" if pe_percentile < 30 else "合理")
    col1.metric("1. 动态 PE (估值水位)", f"{current_pe:.1f}倍", f"百分位: {pe_percentile:.1f}% ({pe_status})", delta_color="inverse" if pe_percentile > 80 else "normal")
    
    col2.metric("2. 200日均线偏离", f"{ma_deviation:+.2f}%", f"现价: {current_price:,.0f}点")
    
    vix_status = "恐慌" if current_vix > 25 else "平稳"
    col3.metric("3. VIX 恐慌指数", f"{current_vix:.2f}", vix_status, delta_color="inverse" if current_vix > 25 else "normal")
    
    rsi_status = "超卖(动能弱)" if rsi_14 < 30 else ("超买(动能强)" if rsi_14 > 70 else "中性")
    col4.metric("4. 14日 RSI", f"{rsi_14:.1f}", rsi_status, delta_color="normal" if rsi_14 < 30 else "inverse")

    # --- 历史趋势可视化图表 ---
    st.markdown("---")
    st.markdown("### 📈 近一年历史趋势走势")
    
    tab1, tab2, tab3 = st.tabs(["价格与均线趋势", "VIX 恐慌情绪波动", "RSI 相对强弱动量"])
    
    with tab1:
        st.line_chart(chart_price, color=["#3b82f6", "#ef4444"])
        st.caption("现价与 200 日长期均线的相对位置。现价跌破红线通常视为长线建仓信号。")
        
    with tab2:
        st.area_chart(chart_vix, color="#f59e0b")
        st.caption("VIX 向上突破 25-30 区间，代表市场发生抛售恐慌（别人恐慌我贪婪）。")
        
    with tab3:
        st.line_chart(chart_rsi, color="#10b981")
        st.caption("RSI 跌至 30 以下代表短期超卖，涨至 70 以上代表短期超买。")

    # --- 交易决策引擎 ---
    st.markdown("---")
    st.markdown("### 🤖 仓位管理与操作建议")
    
    # 简单的综合打分逻辑 (0-100分，分越低越该买)
    risk_score = (pe_percentile * 0.4) + (rsi_14 * 0.3) + ((100 - min(current_vix*2, 100)) * 0.3)
    
    if pe_percentile > 85 and rsi_14 > 65:
        st.error(f"**【卖出 / 减仓】系统风险分：{risk_score:.1f}/100**\n\n估值极高且动能透支。建议将当前 {CURRENT_POSITION_PCT*100}% 的仓位缩减，锁定利润。")
    elif current_vix > 25 and rsi_14 < 35:
        st.success(f"**【定投买入】系统风险分：{risk_score:.1f}/100**\n\n短线恐慌盘涌出，触发左侧交易信号。建议动用 25,000 RMB 可用现金中的 20% (5,000 RMB) 逐步接飞镖。")
    elif ma_deviation < -3:
        st.success(f"**【强力加仓】系统风险分：{risk_score:.1f}/100**\n\n价格罕见跌破 200 日牛熊分界线。建议果断动用大额现金加仓。")
    else:
        st.warning(f"**【持有观望】系统风险分：{risk_score:.1f}/100**\n\n市场处于常规震荡区间。保持 50% 仓位不动，无需进行资金操作。")

except Exception as e:
    st.error(f"数据加载失败，请检查网络连接或 API 状态。详情: {e}")
