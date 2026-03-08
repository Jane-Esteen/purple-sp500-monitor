import yfinance as yf
import pandas as pd
from fredapi import Fred
import os

def update():
    # 1. 抓取量价数据 (S&P 500, VIX, SPY)
    tickers = ["^GSPC", "^VIX", "SPY"]
    data = yf.download(tickers, period='2y')['Close']
    data.to_csv('market_data.csv')
    
    # 2. 抓取 FRED PE 数据
    try:
        fred = Fred(api_key=os.getenv('FRED_API_KEY'))
        # 抓取股息率作为估值对标，因为这个 ID 在 FRED 最稳定
        pe_hist = fred.get_series('SP500DY').dropna().tail(240)
        pe_hist.to_csv('pe_data.csv')
    except Exception as e:
        print(f"FRED 数据抓取失败: {e}")

if __name__ == "__main__":
    update()
