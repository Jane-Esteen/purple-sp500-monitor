import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from fredapi import Fred

# --- 页面全局配置 ---
st.set_page_config(page_title="标普500量化看板 (FRED 权威版)", page_icon="📈", layout="wide")

# 从 Streamlit Secrets 安全读取 API Key
try:
    FRED_KEY = st.secrets["FRED_API_KEY"]
    fred = Fred(api_key=FRED_KEY)
except Exception as e:
    st.error("未在 Secrets 中检测到 FRED_API_KEY。请检查配置。")
    st.stop()

# --- 账户资金状态 ---
TOTAL_FUNDS = 50000 
CURRENT_POSITION_PCT = 0.50 
invested_funds = TOTAL_FUNDS * CURRENT_POSITION_PCT
cash_available = TOTAL_FUNDS - invested_funds

st.title("📈 标普500 核心指标量化看板")
st.caption("数据源：Yahoo Finance | FRED (St. Louis Fed) | 策略逻辑：多重共振量化模型")

# --- 核心数据获取管道 ---
@st.cache_data(ttl=3600)
def get_pro_market_data():
    # 1. 获取量价数据 (Yahoo Finance)
    sp500_raw = yf.download('^GSPC', period='2y', progress=False)['Close']
    vix_raw = yf.download('^VIX', period='2y', progress=False)['Close']
    
    # 统一降维处理
    sp500 = pd.Series(sp500_raw.values.flatten(), index=sp500_raw.index)
    vix = pd.Series(vix_raw.values.flatten(), index=vix_raw.index)
    current_price = float(sp500.iloc[-1])
    
    # 2. 计算 200日均线与偏离度
    ma200_series = sp500.rolling(window=200).mean().dropna()
    ma_deviation = ((current_price / ma200_series.iloc[-1]) - 1) * 100
    
    # 3. 计算 14日 RSI
    delta = sp500.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rsi_series = 100 - (100 / (1 + (gain / loss))).dropna()
    
    # 4. 获取权威 PE 数据并计算“绝对真实百分位” (FRED 接口)
    try:
        # 获取标普 500 过去 20 年的 PE 历史序列
        # FRED 对应 ID: SP500PE (注意：FRED 数据可能有滞后，我们用它作为概率分布参考)
        pe_history_raw = fred.get_series('SP500PE')
        pe_history = pe_history_raw.dropna().tail(240) # 过去20年(按月计)或约5000天样本
        
        # 为了获取最实时的当前 PE，我们依然求助 yfinance 的实时 info 接口
        spy_info = yf.Ticker('SPY').info
        current_pe = spy_info.get('trailingPE')
        
        if current_pe is None:
            # 如果 yfinance 没拿到，降级使用 FRED 最新的一个值
            current_pe = pe_history.iloc[-1]
            
        # 【核心算法升级】：计算当前 PE 在过去 20 年真实样本点中的绝对百分位排名
        pe_percentile = (pe_history < current_pe).mean() * 100
        
        # 构造历史 PE 百分位趋势（逆推法）
        pe_pct_history = sp500.apply(lambda x: (pe_history < (x / (current_price/current_pe))).mean() * 100)
        
    except Exception as e:
        st.warning(f"FRED 数据读取异常: {e}")
        current_pe, pe_percentile, pe_pct_history = None, None, None

    return (current_price, ma_deviation, rsi_series.iloc[-1], vix.iloc[-1], 
            current_pe, pe_percentile, sp500, ma200_series, vix, rsi_series, pe_pct_history)

# --- 页面逻辑执行 ---
try:
    with st.spinner('正在调取美联储(FRED)数据库进行历史对标分析...'):
        (price, dev, rsi, vix_val, pe, pe_pct, 
         hist_p, hist_ma, hist_vix, hist_rsi, hist_pe_pct) = get_pro_market_data()

    # 1. 指标展示
    st.markdown("### 📊 核心指标矩阵")
    col1, col2, col3, col4 = st.columns(4)
    
    if pe is not None:
        status = "高估" if pe_pct > 80 else ("低估" if pe_pct < 30 else "合理")
        col1.metric("1. 真实 PE (20年对标)", f"{pe:.2f}倍", f"分位: {pe_pct:.1f}% ({status})", delta_color="inverse" if pe_pct > 80 else "normal")
    
    col2.metric("2. 200日线偏离", f"{dev:+.2f}%", f"均线: {hist_ma.iloc[-1]:,.0f}")
    col3.metric("3. VIX 恐慌情绪", f"{vix_val:.2f}", "恐慌区域" if vix_val > 25 else "平稳")
    col4.metric("4. 14日 RSI 动量", f"{rsi:.1f}", "超买" if rsi > 70 else ("超卖" if rsi < 30 else "中性"))

    # 2. 可视化图表
    st.markdown("---")
    t1, t2, t3 = st.tabs(["估值百分位走势 (基于FRED数据)", "价格趋势", "情绪与动量"])
    
    with t1:
        if hist_pe_pct is not None:
            st.line_chart(hist_pe_pct.tail(252), color="#8b5cf6")
            st.caption("该曲线基于 FRED 历史 PE 概率分布逆推。100% 代表当前价格处于 20 年来最贵时刻。")
    with t2:
        price_data = pd.DataFrame({"价格": hist_p.tail(252), "200日均线": hist_ma.tail(252)})
        st.line_chart(price_data, color=["#3b82f6", "#ef4444"])
    with t3:
        c_v, c_r = st.columns(2)
        with c_v: st.write("VIX 指数 (情绪)"); st.area_chart(hist_vix.tail(252), color="#f59e0b")
        with c_r: st.write("RSI 指数 (动量)"); st.line_chart(hist_rsi.tail(252), color="#10b981")

    # 3. 策略决策
    st.markdown("---")
    st.markdown("### 🤖 最终决策建议")
    
    # 综合风险分 (40% 估值 + 30% 动量 + 30% 情绪)
    risk_score = (pe_pct * 0.4) + (rsi * 0.3) + ((100 - min(vix_val*2, 100)) * 0.3)
    
    if pe_pct > 85 and rsi > 70:
        st.error(f"**🔴 极端高估信号 (风险分: {risk_score:.1f})**：历史罕见高位，建议至少减仓至 30% 仓位。")
    elif vix_val > 25 and rsi < 35:
        st.success(f"**🟢 黄金坑买入信号 (风险分: {risk_score:.1f})**：市场正在恐慌，估值回归，建议分批动用现金。")
    else:
        st.warning(f"**🟡 观望信号 (风险分: {risk_score:.1f})**：当前处于 {pe_pct:.1f}% 分位，既不便宜也不算离谱，维持 50% 底仓。")

    with st.expander("📝 策略字典与数据溯源"):
        st.write("""
        * **数据源**：PE 历史样本池来自美国圣路易斯联储 (FRED) 数据库。
        * **算法逻辑**：不再使用写死的 14/28。系统通过计算当前 PE 值在过去 240 个月样本库中的累积分布函数 (CDF) 得到百分位。
        * **稳定性**：引入了缓存机制 (TTL=3600)，确保不会因频繁请求导致 API 被封。
        """)

except Exception as e:
    st.error(f"ETL 管道运行失败: {e}")
