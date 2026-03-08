import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import requests

# --- 页面配置 ---
st.set_page_config(page_title="标普500看板", page_icon="📈", layout="wide")
st.title("📈 标普500看板")

# --- 账户资金状态 ---
TOTAL_FUNDS = 50000  # 总资金
CURRENT_POSITION_PCT = 0.50  # 当前仓位比例
invested_funds = TOTAL_FUNDS * CURRENT_POSITION_PCT
cash_available = TOTAL_FUNDS - invested_funds

st.info(f"**资产概览：** 资金库 **{TOTAL_FUNDS:,.0f} RMB** ｜ 当前仓位 **{CURRENT_POSITION_PCT*100}%** ({invested_funds:,.0f} RMB) ｜ 可用现金 **{cash_available:,.0f} RMB**")

# --- 数据抓取与计算 ---
@st.cache_data(ttl=3600) # 缓存1小时，减轻服务器压力
def get_market_data():
    # 1. 获取量价与情绪数据 (yfinance)
    sp500 = yf.download('^GSPC', period='2y', progress=False)['Close']
    vix = yf.download('^VIX', period='2y', progress=False)['Close']
    
    current_price = float(sp500.iloc[-1])
    ma200_series = sp500.rolling(window=200).mean().dropna()
    ma200 = float(ma200_series.iloc[-1])
    ma_deviation = ((current_price / ma200) - 1) * 100
    
    delta = sp500.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    rsi_series = 100 - (100 / (1 + rs))
    rsi_14 = float(rsi_series.dropna().iloc[-1])
    
    current_vix = float(vix.iloc[-1])
    
    # 2. 获取真实的宏观 PE 并计算百分位 (微型 ETL 管道)
    try:
        url = "https://www.multpl.com/s-p-500-pe-ratio/table/by-month"
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0'}
        response = requests.get(url, headers=headers)
        
        tables = pd.read_html(response.text)
        pe_df = tables[0]
        pe_df.columns = ['Date', 'PE']
        pe_df['PE'] = pe_df['PE'].astype(str).str.replace(' estimate', '').astype(float)
        
        # 截取过去 20 年的数据 (240个月)
        pe_history = pe_df.head(240)['PE']
        current_pe = float(pe_history.iloc[0])
        # 计算绝对百分位
        pe_percentile = float((pe_history < current_pe).mean() * 100)
    except Exception as e:
        print(f"PE 数据抓取失败: {e}")
        current_pe = 25.0
        pe_percentile = 50.0  # 失败时的默认中性值
        
    # 3. 准备图表数据 (修复 Pandas 维度对齐报错问题)
    sp500_hist = pd.Series(sp500.values.flatten(), index=sp500.index)
    ma200_hist = pd.Series(ma200_series.values.flatten(), index=ma200_series.index)
    vix_hist = pd.Series(vix.values.flatten(), index=vix.index)
    rsi_hist = pd.Series(rsi_series.dropna().values.flatten(), index=rsi_series.dropna().index)

    chart_price = pd.DataFrame({
        'S&P 500': sp500_hist[-252:], 
        '200日均线': ma200_hist[-252:]
    }, index=sp500_hist[-252:].index)
    
    chart_vix = vix_hist[-252:]
    chart_rsi = rsi_hist[-252:]
    
    return current_price, ma_deviation, rsi_14, current_vix, current_pe, pe_percentile, chart_price, chart_vix, chart_rsi

# --- 页面渲染区 ---
try:
    with st.spinner('正在执行 ETL 管道，拉取华尔街量价与宏观基本面数据...'):
        (current_price, ma_deviation, rsi_14, current_vix, 
         current_pe, pe_percentile, chart_price, chart_vix, chart_rsi) = get_market_data()
    
    # 核心数据指标卡片
    st.markdown("### 📊 核心监控指标")
    col1, col2, col3, col4 = st.columns(4)
    
    pe_status = "高估风险" if pe_percentile > 80 else ("低估区域" if pe_percentile < 30 else "估值合理")
    col1.metric("1. 真实 PE (20年排位)", f"{current_pe:.1f}倍", f"分位: {pe_percentile:.1f}% ({pe_status})", delta_color="inverse" if pe_percentile > 80 else "normal")
    
    col2.metric("2. 200日均线偏离", f"{ma_deviation:+.2f}%", f"现价: {current_price:,.0f}点")
    
    vix_status = "市场恐慌" if current_vix > 25 else "情绪平稳"
    col3.metric("3. VIX 恐慌指数", f"{current_vix:.2f}", vix_status, delta_color="inverse" if current_vix > 25 else "normal")
    
    rsi_status = "超卖(动能弱)" if rsi_14 < 30 else ("超买(动能强)" if rsi_14 > 70 else "动能中性")
    col4.metric("4. 14日 RSI", f"{rsi_14:.1f}", rsi_status, delta_color="normal" if rsi_14 < 30 else "inverse")

    # 历史趋势可视化图表
    st.markdown("---")
    st.markdown("### 📈 近一年历史趋势走势")
    
    tab1, tab2, tab3 = st.tabs(["价格与均线趋势", "VIX 恐慌情绪波动", "RSI 相对强弱动量"])
    
    with tab1:
        st.line_chart(chart_price, color=["#3b82f6", "#ef4444"])
        st.caption("紫蓝线为标普500现价，红线为200日均线。向下跌破均线属于重大趋势变化。")
        
    with tab2:
        st.area_chart(chart_vix, color="#f59e0b")
        st.caption("观察 VIX 飙升的尖峰时刻。往往对应股票被非理性抛售的绝佳买点。")
        
    with tab3:
        st.line_chart(chart_rsi, color="#10b981")
        st.caption("RSI 在 30（底部）和 70（顶部）之间震荡。")

    # 交易决策引擎
    st.markdown("---")
    st.markdown("### 🤖 仓位管理与操作建议")
    
    risk_score = (pe_percentile * 0.4) + (rsi_14 * 0.3) + ((100 - min(current_vix*2, 100)) * 0.3)
    
    if pe_percentile > 85 and rsi_14 > 65:
        st.error(f"**【卖出 / 减仓】系统风险分：{risk_score:.1f}/100**\n\n数据判定：当前处于过去20年极度高估区间，且短期动能透支。建议削减 {CURRENT_POSITION_PCT*100}% 的部分仓位，锁定利润。")
    elif current_vix > 25 and rsi_14 < 35:
        st.success(f"**【定投买入】系统风险分：{risk_score:.1f}/100**\n\n数据判定：短线恐慌盘涌出，触发左侧交易信号。建议动用 25,000 RMB 可用现金中的 20% (即 5,000 RMB) 逐步买入。")
    elif ma_deviation < -3:
        st.success(f"**【强力加仓】系统风险分：{risk_score:.1f}/100**\n\n数据判定：价格跌破 200 日牛熊分界线，出现长线错杀。建议果断动用大额现金加仓。")
    else:
        st.warning(f"**【持有观望】系统风险分：{risk_score:.1f}/100**\n\n数据判定：市场处于常规震荡区间。请保持 50% 仓位 ({invested_funds:,.0f} RMB) 不动，保留现金弹药。")

except Exception as e:
    st.error(f"系统严重错误：数据清洗与加载失败。请检查依赖或网络。详情: {e}")
