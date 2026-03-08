import streamlit as st
import pandas as pd
import numpy as np

# --- 1. 页面配置 ---
st.set_page_config(page_title="标普500量化看板", page_icon="📈", layout="wide")

# --- 2. 资金管理逻辑 ---
TOTAL_FUNDS = 50000 
CURRENT_POSITION_PCT = 0.50 
invested_funds = TOTAL_FUNDS * CURRENT_POSITION_PCT
cash_available = TOTAL_FUNDS - invested_funds

st.title("📈 标普500 核心指标量化看板")
st.info(f"**账户概览：** 资金库 **{TOTAL_FUNDS:,.0f} RMB** ｜ 当前仓位 **{CURRENT_POSITION_PCT*100}%** ｜ 可用现金 **{cash_available:,.0f} RMB**")
st.caption("🟢 数据状态：健康 | 架构：GitHub Actions ETL 自动化流水线 | 数据源：FRED & Multpl")

# --- 3. 读取本地数据仓库 (极速秒开) ---
@st.cache_data(ttl=3600)
def load_data():
    try:
        # 读取价格数据 (FRED SP500, Daily)
        market_df = pd.read_csv('market_data.csv', index_col=0, parse_dates=True)
        price_s = market_df.iloc[:, 0].dropna() 
        
        # 读取 PE 数据 (Multpl, Monthly)
        pe_df = pd.read_csv('pe_data.csv')
        pe_df['Date'] = pd.to_datetime(pe_df['Date'])
        # Multpl 默认是倒序的（最新的在最上面），我们把它翻转成正序画图
        pe_df = pe_df.sort_values('Date').reset_index(drop=True) 
        
        return price_s, pe_df
    except Exception as e:
        return None, None

price_s, pe_df = load_data()

if price_s is not None and not price_s.empty:
    # --- 4. 计算核心量化指标 ---
    current_p = float(price_s.iloc[-1])
    
    # 计算 200日均线及偏离度
    ma200_series = price_s.rolling(window=200).mean().dropna()
    if not ma200_series.empty:
        ma200 = float(ma200_series.iloc[-1])
        dev = ((current_p / ma200) - 1) * 100
    else:
        ma200, dev = current_p, 0.0
        
    # 计算 14日 RSI 动量指标
    delta = price_s.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rsi_series = 100 - (100 / (1 + (gain / loss))).dropna()
    rsi = float(rsi_series.iloc[-1]) if not rsi_series.empty else 50.0

    # 计算真实 PE 百分位 (基于过去 20 年 = 240 个月)
    recent_pe_df = pe_df.tail(240) 
    current_pe = float(pe_df['PE'].iloc[-1])
    # 核心公式：当前 PE 在过去20年中击败了多少个月份？
    pe_pct = (recent_pe_df['PE'] < current_pe).mean() * 100

    # --- 5. 渲染顶部监控卡片 ---
    st.markdown("### 1️⃣ 实时核心监控指标")
    c1, c2, c3, c4 = st.columns(4)
    
    status = "高估" if pe_pct > 80 else ("低估" if pe_pct < 30 else "合理")
    c1.metric("1. 真实 PE (20年分位)", f"{current_pe:.2f}倍", f"历史分位: {pe_pct:.1f}% ({status})", delta_color="inverse" if pe_pct > 80 else "normal")
    c2.metric("2. 标普500现价", f"{current_p:,.2f}", f"日环比: {price_s.pct_change().iloc[-1]*100:+.2f}%")
    c3.metric("3. 200日均线偏离", f"{dev:+.2f}%", f"强弱分水岭: {ma200:,.0f}", delta_color="normal" if dev > 0 else "inverse")
    c4.metric("4. 14日 RSI 动量", f"{rsi:.1f}", "超买" if rsi > 70 else ("超卖" if rsi < 30 else "中性"), delta_color="normal" if rsi < 30 else "inverse")

    # --- 6. 数据可视化呈现 ---
    st.markdown("---")
    t1, t2 = st.tabs(["📊 价格与 200日线趋势", "🔥 历史 PE 估值走势 (近20年)"])
    
    with t1:
        chart_p = pd.DataFrame({"标普500": price_s[-500:], "200日均线": ma200_series[-500:]})
        st.line_chart(chart_p, color=["#3b82f6", "#ef4444"])
    with t2:
        recent_pe_df_indexed = recent_pe_df.set_index('Date')
        st.line_chart(recent_pe_df_indexed['PE'], color="#8b5cf6")

    # --- 7. 量化决策引擎 ---
    st.markdown("---")
    st.markdown("### 2️⃣ 机器人决策建议")
    
    # 简化的双因子风险评分模型 (估值 50% + 动量 50%)
    risk_score = (pe_pct * 0.5) + (rsi * 0.5) 
    
    if pe_pct > 85 and rsi > 65:
        st.error(f"**🔴 【建议减仓】风险分: {risk_score:.1f}** —— 估值极高且动能超买。建议降低仓位，锁定利润。")
    elif pe_pct < 20 and rsi < 35:
        st.success(f"**🟢 【强力买入】风险分: {risk_score:.1f}** —— 估值处于黄金坑，且市场超卖。建议动用 {cash_available:,.0f} RMB 现金加仓。")
    elif dev < -5:
        st.success(f"**🟢 【长线买点】风险分: {risk_score:.1f}** —— 价格跌破 200 日线，长期配置的绝佳右侧买点。")
    else:
        st.warning(f"**🟡 【持仓观望】风险分: {risk_score:.1f}** —— 市场无极端偏离。维持当前 50% 仓位。")

else:
    st.error("⏳ 数据读取失败。请检查 GitHub 仓库中 market_data.csv 的格式是否正确。")
