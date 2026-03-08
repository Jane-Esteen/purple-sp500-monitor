import yfinance as yf
import pandas as pd
from fredapi import Fred
import os
import sys

def update():
    # 1. 抓取 Yahoo 数据
    print("--- 开始同步 Yahoo Finance 数据 ---")
    try:
        tickers = ["^GSPC", "^VIX", "SPY"]
        data = yf.download(tickers, period='2y')['Close']
        if not data.empty:
            data.to_csv('market_data.csv')
            print("✅ market_data.csv 写入成功")
        else:
            print("❌ Yahoo 下载结果为空")
    except Exception as e:
        print(f"❌ Yahoo 报错: {e}")

    # 2. 抓取 FRED 数据 (严格模式)
    print("--- 开始同步 FRED 真实数据 ---")
    api_key = os.getenv('FRED_API_KEY')
    
    if not api_key:
        print("❌ 错误：环境变量 FRED_API_KEY 为空！请检查 GitHub Secrets 配置。")
        sys.exit(1) # 强制报错，中断流程
        
    try:
        fred = Fred(api_key=api_key)
        # 获取标普 500 股息率 (真实历史数据序列)
        # 如果这个 ID 报错，说明该 Key 权限无法访问此数据
        s_data = fred.get_series('SP500DY') 
        if s_data is not None and not s_data.empty:
            s_data.dropna().tail(240).to_csv('pe_data.csv')
            print(f"✅ pe_data.csv 写入成功，样本数: {len(s_data)}")
        else:
            print("❌ FRED 返回了空序列")
            sys.exit(1)
    except Exception as e:
        print(f"❌ FRED API 报错详情: {e}")
        sys.exit(1) # 只有报错，Actions 才会显示红叉，我们才能看日志

if __name__ == "__main__":
    update()
