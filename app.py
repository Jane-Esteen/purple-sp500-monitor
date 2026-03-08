import streamlit as st
import pandas as pd
import numpy as np

# --- 1. 页面配置 ---
st.set_page_config(page_title="标普500量化看板", page_icon="📈", layout="wide")

# --- 2. 资金管理与策略说明 ---
TOTAL_FUNDS = 50000 
CURRENT_POSITION_PCT = 0.50 
invested_funds = TOTAL_FUNDS * CURRENT_POSITION_PCT
cash_available = TOTAL_FUNDS - invested_funds

st.title("📈 标普500 核心指标量化看板")
st.caption("🟢 数据状态：健康 | 架构：GitHub Actions ETL 流水线 | 数据源：FRED & Multpl")

# 【新增】置顶的专有名词与策略库
with st.expander("📖 投资策略与专有名词库 (点击展开查阅)"):
    st.markdown("""
    ### 核心专有名词
    * **PE (市盈率)**：估值指标。倍数越高代表股票越贵。我们使用的是基于过去 20 年的百分位，80% 以上即为历史高位。
    * **VIX (恐慌指数)**：反映市场对未来 30 天波动的预期。正常区间 15-20；>25 极度恐慌（通常是买点）；<15 极度贪婪。
    * **RSI (相对强弱指数)**：动量指标，范围 0-100。>70 代表短期超买（涨过头了），<30 代表短期超卖（跌过头了）。
    * **200日均线 (MA200)**：牛熊分水岭。价格在均线之上且偏离度适中为牛市；跌破均线通常视为长期布局机会。
    
    ### 本看板量化策略
    **核心思想：估值定大局，情绪找买点，趋势做防守。**
    1. **长线建仓**：当 PE 处于历史极低分位（<20%），或价格跌破 200 日线超过 5% 时，执行左侧买入。
    2. **恐慌抄底**：当 VIX 飙升（>25）且 RSI 极度超卖（<35）时，动用部分现金抄底。
    3. **泡沫减仓**：当 PE 处于历史极高分位（>85%）且 RSI 超买（>65）时，减仓锁定利润。
    """)

# --- 3. 读取本地数据仓库 ---
@st.cache_data(ttl=3600)
def load_data():
    try:
        market_df = pd.read_csv('market_data.csv', index_col=0, parse_dates=True)
        # 【修复】重新引回 VIX 数据
        price_s = market_df['^GSPC'].dropna() 
        vix_s = market_df['^VIX'].dropna()
        
        pe_df = pd.read_csv('pe_data.csv')
        pe_df['Date'] = pd.to_datetime(pe_df['Date'])
        pe_df = pe_df.sort_values('Date').reset_index(drop=True) 
        return price_s, vix_s, pe_df
    except Exception as e:
        return None, None, None

price_s, vix_s, pe_df = load_data()

if price_s is not None and not price_s.empty:
    # --- 4. 计算核心量化指标 ---
    current_p = float(price_s.iloc[-1])
    daily_return = price_s.pct_change().iloc[-1] * 100
    
    current_vix = float(vix_s.iloc[-1])
    vix_change = vix_s.pct_change().iloc[-1] * 100
    
    # 均线偏离
    ma200_series = price_s.rolling(window=200).mean().dropna()
    ma200 = float(ma200_series.iloc[-1]) if not ma200_series.empty else current_p
    dev = ((current_p / ma200) - 1) * 100
        
    # RSI
    delta = price_s.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rsi_series = 100 - (100 / (1 + (gain / loss))).dropna()
    rsi = float(rsi_series.iloc[-1]) if not rsi_series.empty else 50.0

    # PE 分位
    recent_pe_df = pe_df.tail(240) 
    current_pe = float(pe_df['PE'].iloc[-1])
    pe_pct = (recent_pe_df['PE'] < current_pe).mean() * 100

    # --- 5. 渲染顶部监控卡片 ---
    st.markdown("### 1️⃣ 实时核心监控指标")
    c1, c2, c3, c4 = st.columns(4)
    
    status = "高估" if pe_pct > 80 else ("低估" if pe_pct < 30 else "合理")
    c1.metric("1. 真实 PE (20年分位)", f"{current_pe:.2f}倍", f"历史分位: {pe_pct:.1f}% ({status})", delta_color="inverse" if pe_pct > 80 else "normal")
    c2.metric("2. 标普500现价", f"{current_p:,.2f}", f"日均线偏离: {dev:+.2f}%")
    # 【修复】把 VIX 指标卡片加回来
    c3.metric("3. VIX 恐慌指数", f"{current_vix:.2f}", f"日变动: {vix_change:+.1f}%", delta_color="inverse" if current_vix > 25 else "normal")
    c4.metric("4. 14日 RSI 动量", f"{rsi:.1f}", "超买" if rsi > 70 else ("超卖" if rsi < 30 else "中立"), delta_color="normal" if rsi < 30 else "inverse")

    # --- 6. 归因分析模块 (逻辑推演引擎) ---
    st.markdown("---")
    st.markdown("### 📰 每日盘面解析指北 (市场异动归因)")
    
    # 利用量价与情绪的背离推演宏观环境
    col_attr1, col_attr2 = st.columns([1, 2])
    with col_attr1:
        st.write(f"**大盘涨跌：** {daily_return:+.2f}%")
        st.write(f"**恐慌情绪：** {vix_change:+.2f}%")
    with col_attr2:
        if daily_return > 0.5 and vix_change < -2:
            st.success("推演逻辑：**【宏观利好 / 情绪修复】** 大盘上涨且恐慌情绪消退。通常受降息预期、强劲宏观数据或重磅企业财报超预期驱动，市场风险偏好提升。")
        elif daily_return < -0.5 and vix_change > 5:
            st.error("推演逻辑：**【避险模式 / 宏观利空】** 大盘下跌且恐慌指数飙升。通常因为突发黑天鹅事件、加息恐慌或重要公司暴雷。资金正在撤离股市买入避险资产。")
        elif daily_return > 0.5 and vix_change > 2:
            st.warning("推演逻辑：**【FOMO 逼空行情】** 价格上涨但 VIX 也在涨。这种背离说明市场极度兴奋（怕错过），但大资金同时在疯狂买入看跌期权做对冲，随时可能回调。")
        elif daily_return > -0.5 and daily_return < 0.5:
            st.info("推演逻辑：**【震荡盘整】** 市场波动率极小，通常在等待关键的宏观数据（如非农、CPI）出炉或美联储决议，资金处于观望状态。")
        else:
            st.info("推演逻辑：**【常规波动】** 今日市场表现无极端情绪背离，受板块轮动或日常资金面影响为主。")

    # --- 7. 数据可视化 ---
    st.markdown("---")
    t1, t2, t3 = st.tabs(["📊 价格与 200日线趋势", "🔥 历史 PE 估值走势 (近20年)", "⚡ VIX 恐慌情绪轨迹"])
    with t1:
        chart_p = pd.DataFrame({"标普500": price_s[-252:], "200日均线": ma200_series[-252:]})
        st.line_chart(chart_p, color=["#3b82f6", "#ef4444"])
    with t2:
        recent_pe_df_indexed = recent_pe_df.set_index('Date')
        st.line_chart(recent_pe_df_indexed['PE'], color="#8b5cf6")
    with t3:
        st.area_chart(vix_s[-252:], color="#f59e0b")

    # --- 8. 详细量化决策建议 (动态逻辑修复版) ---
    st.markdown("---")
    st.markdown("### 🤖 机器人投资执行报告")
    
    # 1. 独立生成各个指标的动态定性描述 (拒绝硬编码)
    if pe_pct > 80:
        pe_desc = f"🚨 估值高企：历史分位高达 **{pe_pct:.1f}%**，处于明显的泡沫高估区间。"
    elif pe_pct < 30:
        pe_desc = f"🌟 估值低洼：历史分位仅 **{pe_pct:.1f}%**，具备极高的安全边际。"
    else:
        pe_desc = f"⚖️ 估值温和：历史分位 **{pe_pct:.1f}%**，处于长期的合理定价区间。"

    if current_vix > 25:
        vix_desc = f"🌩️ 极度恐慌：VIX 飙升至 **{current_vix:.2f}**，市场处于非理性避险抛售中。"
    elif current_vix < 15:
        vix_desc = f"☀️ 极度贪婪：VIX 降至 **{current_vix:.2f}**，市场毫无防备，警惕回调。"
    else:
        vix_desc = f"☁️ 情绪平稳：VIX 处于 **{current_vix:.2f}**，市场波动在正常预期范围内。"

    if rsi > 70:
        rsi_desc = f"🔥 严重超买：RSI 达 **{rsi:.1f}**，短期买盘动能透支。"
    elif rsi < 30:
        rsi_desc = f"🧊 严重超卖：RSI 降至 **{rsi:.1f}**，短期抛压已释放殆尽。"
    else:
        rsi_desc = f"🌊 动能中性：RSI 处于 **{rsi:.1f}**，多空力量相对均衡。"

    # 2. 综合打分与交易动作决策
    risk_score = (pe_pct * 0.5) + (rsi * 0.5)
    
    if pe_pct > 80 and rsi > 60:
        st.error("#### 🔴 结论：右侧减仓，锁定利润")
        st.write(f"**综合风险分: {risk_score:.1f}** —— 资产极度昂贵且动能透支。建议将仓位降低至 30%。")
    elif current_vix > 25 or (pe_pct < 30 and rsi < 40):
        # 只要发生极度恐慌，或者低估且超卖，就触发买入
        st.success("#### 🟢 结论：左侧建仓，恐慌买入")
        st.write(f"**综合风险分: {risk_score:.1f}** —— 市场出现黄金坑。建议动用 {cash_available:,.0f} RMB 现金分批加仓。")
    elif dev < -5:
        st.success("#### 🟢 结论：均线破位，长线定投")
        st.write(f"**综合风险分: {risk_score:.1f}** —— 价格跌穿 200 日线超过 5%，长线赔率极佳。")
    else:
        st.warning("#### 🟡 结论：信号分化，维持观望")
        st.write(f"**综合风险分: {risk_score:.1f}** —— 未出现共振的极端交易信号。建议持有当前 {CURRENT_POSITION_PCT*100}% 仓位。")

    # 3. 打印真实的判定依据
    st.markdown("**🔍 详细判定依据：**")
    st.write(pe_desc)
    st.write(vix_desc)
    st.write(rsi_desc)
    
else:
    st.error("⏳ 数据读取失败。请检查 GitHub 仓库中 market_data.csv 的格式是否正确。")
