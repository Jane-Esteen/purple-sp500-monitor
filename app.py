import streamlit as st
import yfinance as yf
import pandas as pd
import datetime

# --- 页面配置 ---
st.set_page_config(page_title="S&P 500 个人健康分看板", page_icon="🟣", layout="wide")
st.title("🟣 我的标普 500 量化健康分看板")
st.markdown("基于多维数据的每日估值监控与仓位管理")

# --- 账户资金设置 ---
TOTAL_FUNDS = 50000  # 总资金
CURRENT_POSITION_PCT = 0.50  # 当前仓位比例
invested_funds = TOTAL_FUNDS * CURRENT_POSITION_PCT
cash_available = TOTAL_FUNDS - invested_funds

st.info(f"**账户状态：** 投资总额 **{TOTAL_FUNDS:,.0f} RMB** ｜ 当前仓位 **{CURRENT_POSITION_PCT*100}%** ({invested_funds:,.0f} RMB) ｜ 可用现金 **{cash_available:,.0f} RMB**")

# --- 数据抓取与计算 ---
@st.cache_data(ttl=3600) # 缓存1小时，避免频繁请求
def get_market_data():
    # 抓取标普500和VIX过去一年的数据
    sp500 = yf.download('^GSPC', period='1y', progress=False)['Close']
    vix = yf.download('^VIX', period='1d', progress=False)['Close']
    
    # 1. 最新收盘价
    current_price = float(sp500.iloc[-1])
    
    # 2. 200日均线与偏离度
    ma200 = float(sp500.rolling(window=200).mean().iloc[-1])
    ma_deviation = ((current_price / ma200) - 1) * 100
    
    # 3. RSI (14日计算)
    delta = sp500.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    rsi_14 = float(100 - (100 / (1 + rs)).iloc[-1])
    
    # 4. VIX
    current_vix = float(vix.iloc[-1])
    
    return current_price, ma200, ma_deviation, rsi_14, current_vix

try:
    current_price, ma200, ma_deviation, rsi_14, current_vix = get_market_data()
    
    # 宏观 PE 数据（通常需要付费API，此处设为静态输入，可根据每月报告调整）
    pe_percentile = 99.0 

    # --- 指标展示区 ---
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("1. PE 百分位 (极度高估)", f"{pe_percentile}%", "- 长期风险高", delta_color="inverse")
    col2.metric("2. 200日均线偏离", f"{ma_deviation:+.2f}%", f"现价: {current_price:,.0f}")
    
    vix_alert = "恐慌" if current_vix > 25 else "正常"
    col3.metric("3. VIX 恐慌指数", f"{current_vix:.2f}", vix_alert, delta_color="inverse" if current_vix > 25 else "normal")
    
    rsi_alert = "超卖(低估)" if rsi_14 < 30 else ("超买(高估)" if rsi_14 > 70 else "中性")
    col4.metric("4. 14日 RSI 动量", f"{rsi_14:.1f}", rsi_alert, delta_color="normal" if rsi_14 < 30 else "inverse")

    # --- 交易决策逻辑 ---
    st.markdown("---")
    st.subheader("🤖 今日决策建议")
    
    if pe_percentile > 90 and rsi_14 > 60:
        st.error("**【卖出 / 减仓信号】**\n\n系统判定：市场处于极度高估且短期动能过热。建议将 50% 仓位缩减至 30%，锁定利润，增加现金储备。")
    elif current_vix > 25 and rsi_14 < 40:
        st.success(f"**【买入 / 定投信号】**\n\n系统判定：市场出现恐慌性超卖。虽然长期估值偏高，但短期出现“黄金坑”。\n\n**建议操作**：动用可用现金 {cash_available:,.0f} RMB 中的 20% (即 {cash_available * 0.2:,.0f} RMB) 分批买入。")
    elif ma_deviation < -5:
        st.success(f"**【强力买入信号】**\n\n系统判定：标普500已跌破200日长期支撑线并深度偏离。极佳的中长线建仓机会！\n\n**建议操作**：使用可用现金的 50% 甚至更多进行加仓。")
    else:
        st.warning("**【持有 / 观望信号】**\n\n系统判定：各项指标处于拉锯状态。长期估值偏高，但未出现明显短期恐慌。\n\n**建议操作**：保持当前 50% ({invested_funds:,.0f} RMB) 的底仓，按兵不动，保留子弹。")

except Exception as e:
    st.error(f"数据拉取失败，请稍后再试。错误信息: {e}")
