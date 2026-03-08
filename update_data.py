import yfinance as yf
import pandas as pd
from fredapi import Fred
import os

def update():
    # 1. 抓取量价数据
    try:
        print("开始抓取 Yahoo Finance 数据...")
        tickers = ["^GSPC", "^VIX", "SPY"]
        data = yf.download(tickers, period='2y')['Close']
        if not data.empty:
            data.to_csv('market_data.csv')
            print("market_data.csv 生成成功")
    except Exception as e:
        print(f"Yahoo 数据抓取异常: {e}")
    
    # 2. 抓取 FRED 数据
    try:
        print("开始抓取 FRED 数据...")
        api_key = os.getenv('FRED_API_KEY')
        if api_key:
            fred = Fred(api_key=api_key)
            pe_hist = fred.get_series('SP500DY').dropna().tail(240)
            pe_hist.to_csv('pe_data.csv')
            print("pe_data.csv 生成成功")
        else:
            print("未找到 FRED_API_KEY 环境变量")
    except Exception as e:
        print(f"FRED 抓取异常: {e}")

if __name__ == "__main__":
    update()
