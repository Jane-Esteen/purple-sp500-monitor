import pandas as pd
from fredapi import Fred
import os
import requests
import sys
import io

def update():
    # 1. 抓取标普500指数 (FRED 官方源)
    print("--- 开始同步 FRED 标普500指数 ---")
    api_key = os.getenv('FRED_API_KEY')
    if not api_key:
        print("❌ 错误：环境变量 FRED_API_KEY 为空")
        sys.exit(1)
        
    try:
        fred = Fred(api_key=api_key)
        sp500_price = fred.get_series('SP500').dropna()
        sp500_price.to_csv('market_data.csv')
        print(f"✅ FRED SP500 获取成功，最新点位: {sp500_price.iloc[-1]:.2f}")
    except Exception as e:
        print(f"❌ FRED 获取失败: {e}")
        sys.exit(1)

    # 2. 抓取真实历史 PE 数据 (Multpl 源)
    print("--- 开始同步标普500真实历史 PE ---")
    try:
        url = "https://www.multpl.com/s-p-500-pe-ratio/table/by-month"
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        response = requests.get(url, headers=headers)
        
        # 修复 Pandas 警告：使用 io.StringIO 包装 HTML 文本
        tables = pd.read_html(io.StringIO(response.text))
        pe_df = tables[0]
        pe_df.columns = ['Date', 'PE']
        
        # 终极数据清洗：使用正则表达式，只保留数字(0-9)和小数点(.)
        # 这样无论它加 '†' 还是 '*' 还是 'estimate'，统统都会被过滤掉
        pe_df['PE'] = pe_df['PE'].astype(str).replace(r'[^\d.]', '', regex=True).astype(float)
        
        # 保存这整整一百多年的真实 PE 历史！
        pe_df.to_csv('pe_data.csv', index=False)
        print(f"✅ 真实历史 PE 数据获取成功，最新 PE: {pe_df['PE'].iloc[0]:.2f}")
        
    except Exception as e:
        print(f"❌ PE 获取失败: {e}")
        sys.exit(1)

if __name__ == "__main__":
    update()
