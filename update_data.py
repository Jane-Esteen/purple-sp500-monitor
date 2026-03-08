import pandas as pd
import yfinance as yf
import requests
import io
import sys

def update():
    # 1. 抓取量价与恐慌指数 (Yahoo Finance)
    print("--- 开始同步 Yahoo Finance 数据 ---")
    try:
        tickers = ["^GSPC", "^VIX", "SPY"]
        # yfinance 在 GitHub Actions 的服务器上不会被限流
        data = yf.download(tickers, period='2y', progress=False)['Close']
        if not data.empty:
            data.to_csv('market_data.csv')
            print(f"✅ market_data.csv 获取成功，已包含 VIX 和标普现价")
        else:
            print("❌ Yahoo 返回空数据")
            sys.exit(1)
    except Exception as e:
        print(f"❌ Yahoo 获取失败: {e}")
        sys.exit(1)

    # 2. 抓取真实历史 PE 数据 (Multpl 强力清洗版)
    print("--- 开始同步标普500真实历史 PE ---")
    try:
        url = "https://www.multpl.com/s-p-500-pe-ratio/table/by-month"
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        response = requests.get(url, headers=headers)
        
        # 包装 HTML 文本并提取表格
        tables = pd.read_html(io.StringIO(response.text))
        pe_df = tables[0]
        pe_df.columns = ['Date', 'PE']
        
        # 强大的正则清洗，专治各种 † 和 estimate 脏字符
        pe_df['PE'] = pe_df['PE'].astype(str).replace(r'[^\d.]', '', regex=True).astype(float)
        
        pe_df.to_csv('pe_data.csv', index=False)
        print(f"✅ 真实历史 PE 数据获取成功，最新 PE: {pe_df['PE'].iloc[0]:.2f}")
    except Exception as e:
        print(f"❌ PE 获取失败: {e}")
        sys.exit(1)

if __name__ == "__main__":
    update()
