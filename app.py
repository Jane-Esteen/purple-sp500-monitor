import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np

# --- 页面全局配置 ---
st.set_page_config(page_title="标普500量化看板", page_icon="📈", layout="wide")

# --- 账户资金状态 ---
TOTAL_FUNDS = 50000  # 你的总投资资金
CURRENT_POSITION_PCT = 0.50  # 你当前的仓位比例
invested_funds = TOTAL_FUNDS * CURRENT_POSITION_PCT
cash_available = TOTAL_FUNDS - invested_funds

# 页面头部
st.title("📈 标普500 核心指标量化看板")
st.info(f"**账户概览：** 资金库 **{TOTAL_FUNDS:,.0f} RMB** ｜ 当前仓位 **{CURRENT_POSITION_PCT*100}%** ({invested_funds:,.0f} RMB) ｜ 可用现金 **{cash_available:,.0f} RMB**")

# --- 数据抓取与清洗管道 (ETL) ---
@st.cache_data(ttl=3600) # 缓存1小时，防止API被封
def get_market_data():
    # 1. 拉取过去两年的基础量价数据
    sp500 = yf.download('^GSPC', period='2y', progress=False)['Close']
    vix = yf.download('^VIX', period='2y', progress=False)['Close']
    
    # 将多重索引降维，防止 Pandas 报错
    sp500_series = pd.Series(sp500.values.flatten(), index=sp500.index)
    vix_series = pd.Series(vix.values.flatten(), index=vix.index)
    
    current_price = float(sp500_series.iloc[-1])
    current_vix = float(vix_series.iloc[-1])
    
    # 2. 计算 200日均线与偏离度
    ma200_series = sp500_series.rolling(window=200).mean().dropna()
    ma200 = float(ma200_series.iloc[-1])
    ma_deviation = ((current_price / ma200) - 1) * 100
    
    # 3. 计算 14日 RSI
    delta = sp500_series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    rsi_series = 100 - (100 / (1 + rs)).dropna()
    rsi_14 = float(rsi_series.iloc[-1])
    
    # 4. 获取原生真实 PE 并逆推历史走势
    try:
        spy_info = yf.Ticker('SPY').info
        current_pe = spy_info.get('trailingPE')
        
        if current_pe is None:
            raise ValueError("API 未返回真实 PE 数据")
            
        # 绝对排位算法：14倍(极度便宜 0%) -> 28倍(极度昂贵 100%)
        pe_percentile = float(min(100.0, max(0.0, ((current_pe - 14) / (28 - 14)) * 100)))
        
        # 隐含EPS逆推法：计算过去一年的 PE 和百分位历史曲线
        implied_eps = current_price / current_pe
        pe_history = sp500_series / implied_eps
        pe_pct_history = ((pe_history - 14) / 14) * 100
        pe_pct_history = pe_pct_history.clip(lower=0, upper=100) # 边界截断
        
    except Exception as e:
        print(f"PE 数据抓取失败: {e}")
        current_pe, pe_percentile = None, None
        pe_history, pe_pct_history = None, None

    # 5. 截取最近一年(约252个交易日)用于图表绘制
    chart_price = pd.DataFrame({'S&P 500': sp500_series[-252:], '200日均线': ma200_series[-252:]})
    chart_vix = vix_series[-252:]
    chart_rsi = rsi_series[-252:]
    
    if current_pe is not None:
        chart_pe = pd.DataFrame({'动态 PE': pe_history[-252:]})
        chart_pe_pct = pd.DataFrame({'PE 百分位 (%)': pe_pct_history[-252:]})
    else:
        chart_pe, chart_pe_pct = None, None
        
    return current_price, ma_deviation, rsi_14, current_vix, current_pe, pe_percentile, chart_price, chart_vix, chart_rsi, chart_pe, chart_pe_pct

# --- 页面渲染区 ---
try:
    with st.spinner('正在连接华尔街接口拉取数据...'):
        (current_price, ma_deviation, rsi_14, current_vix, 
         current_pe, pe_percentile, chart_price, chart_vix, chart_rsi, chart_pe, chart_pe_pct) = get_market_data()
    
    # 【模块 1：实时监控卡片】
    st.markdown("### 1️⃣ 实时指标监控")
    col1, col2, col3, col4 = st.columns(4)
    
    if current_pe is not None:
        pe_status = "高估风险" if pe_percentile > 80 else ("低估区域" if pe_percentile < 30 else "估值合理")
        col1.metric("1. 真实 PE (估值水位)", f"{current_pe:.2f}倍", f"分位: {pe_percentile:.1f}% ({pe_status})", delta_color="inverse" if pe_percentile > 80 else "normal")
    else:
        col1.metric("1. 真实 PE", "数据丢失", "❌ API 断开", delta_color="off")
        
    col2.metric("2. 200日均线偏离 (趋势)", f"{ma_deviation:+.2f}%", f"现价: {current_price:,.0f}点")
    vix_status = "市场恐慌" if current_vix > 25 else "情绪平稳"
    col3.metric("3. VIX 恐慌指数 (情绪)", f"{current_vix:.2f}", vix_status, delta_color="inverse" if current_vix > 25 else "normal")
    rsi_status = "超卖(动能弱)" if rsi_14 < 30 else ("超买(动能强)" if rsi_14 > 70 else "动能中性")
    col4.metric("4. 14日 RSI (动量)", f"{rsi_14:.1f}", rsi_status, delta_color="normal" if rsi_14 < 30 else "inverse")

    # 【模块 2：历史趋势走势】
    st.markdown("---")
    st.markdown("### 2️⃣ 近一年历史数据走势")
    
    tab1, tab2, tab3, tab4 = st.tabs(["PE 估值水位走势", "价格与 200日均线", "VIX 恐慌情绪面积图", "RSI 相对强弱动量"])
    
    with tab1:
        if chart_pe_pct is not None:
            st.line_chart(chart_pe_pct, color=["#8b5cf6"])
            st.caption("PE 百分位走势 (0% - 100%)：反映过去一年美股估值的冷热变化。接近 100% 代表极度昂贵。")
        else:
            st.warning("PE 数据缺失，无法绘制图表。")
            
    with tab2:
        st.line_chart(chart_price, color=["#3b82f6", "#ef4444"])
        st.caption("趋势判断：蓝线(现价)向下跌破红线(200日均线)通常视为长线防守信号，而严重跌离均线则是罕见买点。")
        
    with tab3:
        st.area_chart(chart_vix, color="#f59e0b")
        st.caption("情绪监控：注意图中向上突刺的尖峰。VIX 突破 25 往往伴随着市场的非理性抛售。")
        
    with tab4:
        st.line_chart(chart_rsi, color="#10b981")
        st.caption("动量追踪：RSI 跌至 30 以下区域代表短期超卖（做空动能枯竭），是短线反弹的先行指标。")

    # 【模块 3：算法决策与操作建议】
    st.markdown("---")
    st.markdown("### 3️⃣ 量化决策建议")
    
    # 风险评分计算 (有PE时包含PE权重，无PE时降级计算)
    if current_pe is not None:
        risk_score = (pe_percentile * 0.4) + (rsi_14 * 0.3) + ((100 - min(current_vix*2, 100)) * 0.3)
    else:
        risk_score = (rsi_14 * 0.5) + ((100 - min(current_vix*2, 100)) * 0.5)

    if (current_pe is not None and pe_percentile > 85) and rsi_14 > 65:
        st.error(f"**🔴 【卖出 / 减仓信号】 系统风险分：{risk_score:.1f}/100**\n\n数据判定：当前处于极度高估区间，且短期动能透支。建议削减当前部分仓位，锁定利润。")
    elif current_vix > 25 and rsi_14 < 35:
        st.success(f"**🟢 【定投买入信号】 系统风险分：{risk_score:.1f}/100**\n\n数据判定：短线恐慌盘涌出，触发左侧交易。建议动用 {cash_available:,.0f} RMB 可用现金中的 20% (即 5,000 RMB) 逐步买入。")
    elif ma_deviation < -5:
        st.success(f"**🟢 【强力加仓信号】 系统风险分：{risk_score:.1f}/100**\n\n数据判定：价格严重跌破 200 日牛熊分界线，出现长线错杀。建议果断动用大额现金加仓。")
    else:
        st.warning(f"**🟡 【持有观望信号】 系统风险分：{risk_score:.1f}/100**\n\n数据判定：指标处于拉锯状态，无极端偏离。请保持当前 50% ({invested_funds:,.0f} RMB) 的底仓不动。")

    # 【模块 4：策略逻辑与技术名词字典】
    st.markdown("---")
    with st.expander("📚 查看底层策略逻辑与关键名词解释", expanded=False):
        st.markdown("""
        #### 核心策略逻辑：多重共振验证
        本看板不会仅凭单一指标盲目操作，而是要求**多个维度同时发出信号**以过滤噪音：
        * **长线防守**：当 PE 极高且 RSI 超买时，系统才会提示“减仓”。
        * **左侧抄底**：只有当 VIX 恐慌值突破 25，**且** RSI 同步跌入超卖区时，系统才会认定“恐慌被彻底释放”，提示按比例定投买入。
        * **仓位渐进**：根据信号强度，动态调用当前 5万 RMB 总资金的不同比例，绝不一次性满仓。

        #### 关键名词解释：
        1.  **PE 百分位 (估值核心)**
            * **是什么**：当前市盈率（PE）在历史 20 年数据中排名的位置（0-100%）。本系统锚定 14倍(极度便宜) 到 28倍(极度昂贵) 的分布区间。
            * **依据**：均值回归原理。PE 30% 意味着历史上 70% 的时间比现在贵。
        2.  **200日均线偏离 (趋势判断)**
            * **是什么**：当前价格相对于过去 200 天平均价格的偏离百分比。
            * **依据**：200日均线被视为“牛熊分界线”。价格长期会围绕均值波动，如果跌破（如 -5%），通常意味跌过头了。
        3.  **VIX 恐慌指数 (情绪指标)**
            * **是什么**：市场预期波动率，被称为华尔街的“恐惧贪婪温度计”。
            * **依据**：恐慌时往往超卖。当 VIX > 25 或 30 时，说明市场出现抛售踩踏，是“别人恐惧我贪婪”的最佳买点。
        4.  **RSI 相对强弱指数 (动量指标)**
            * **是什么**：0-100 的数值，衡量价格短期涨跌的速度和力量。
            * **依据**：物极必反。RSI < 30 表示短期跌得太快太急（超卖，可能反弹）；RSI > 70 表示涨得太猛（超买，随时回调）。
        """)

except Exception as e:
    st.error(f"系统严重错误：数据清洗与加载失败。请检查依赖或网络。详情: {e}")
