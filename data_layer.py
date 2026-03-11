import os
import yfinance as yf
import pandas as pd
from fredapi import Fred
import streamlit as st

FRED_KEY = os.environ.get("FRED_API_KEY")

class DataLayer:
    def __init__(self, fred_key=None):
        # 兼容传入的 key 或环境变量
        key = fred_key or FRED_KEY
        self.fred = Fred(api_key=key)

    def market_data(self):
        try:
            # 下载10年历史数据
            spx = yf.download("^GSPC", period="10y", auto_adjust=True, threads=False)["Close"]
            vix = yf.download("^VIX", period="10y", auto_adjust=True, threads=False)["Close"]

            # 将 Series 组合成 DataFrame
            df = pd.concat([spx, vix], axis=1)
            df.columns = ["SPX", "VIX"]
            
            # 向下填充缺失值（比如有些日子VIX停盘但SPX开盘），然后去掉头部的NaN
            df = df.ffill().dropna()
            return df
        except Exception as e:
            raise Exception(f"Yahoo Finance 数据抓取异常: {e}")

    def macro_data(self):
        try:
            dgs10 = self.fred.get_series("DGS10")
            dgs2 = self.fred.get_series("DGS2")
            gdp = self.fred.get_series("GDP")
            wilshire = self.fred.get_series("WILL5000PRFC")
            hy = self.fred.get_series("BAMLH0A0HYM2")

            # 使用 pd.concat 按照日期对齐数据
            df = pd.concat([dgs10, dgs2, gdp, wilshire, hy], axis=1)
            df.columns = ["DGS10", "DGS2", "GDP", "WILL5000", "HY"]

            # 【关键修复】：使用 ffill() 填充季度数据！
            # 因为 GDP 是季度的，其他是日更的。如果不 ffill 直接 dropna，会删掉所有数据。
            df = df.ffill().dropna()
            
            return df

        except Exception as e:
            st.error(f"FRED 数据抓取失败: {e}")
            # 返回带有正确列名的空 DataFrame，防止后续代码报错
            return pd.DataFrame(columns=["DGS10", "DGS2", "GDP", "WILL5000", "HY"])
