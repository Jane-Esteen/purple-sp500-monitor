import os
import yfinance as yf
import pandas as pd
from fredapi import Fred
import streamlit as st

FRED_KEY = os.environ.get("FRED_API_KEY")

class DataLayer:
    def __init__(self, fred_key=None):
        key = fred_key or FRED_KEY
        self.fred = Fred(api_key=key)

    def market_data(self):
        try:
            # 下载10年历史数据 (使用 Ticker 方式更稳定)
            spx = yf.Ticker("^GSPC").history(period="10y")["Close"]
            vix = yf.Ticker("^VIX").history(period="10y")["Close"]

            df = pd.concat([spx, vix], axis=1)
            df.columns = ["SPX", "VIX"]
            
            # 去除 yfinance 时间戳自带的时区信息，避免后续对齐报错
            if df.index.tz is not None:
                df.index = df.index.tz_localize(None)
                
            df = df.ffill().dropna()
            return df
        except Exception as e:
            raise Exception(f"Yahoo Finance 数据抓取异常: {e}")

    def macro_data(self):
        try:
            # 1. 抓取仍然存在于 FRED 上的数据
            dgs10 = self.fred.get_series("DGS10")
            dgs2 = self.fred.get_series("DGS2")
            gdp = self.fred.get_series("GDP")
            hy = self.fred.get_series("BAMLH0A0HYM2")
            
            # 2. 【核心修复】从 Yahoo Finance 抓取 Wilshire 5000 代替 FRED
            wilshire = yf.Ticker("^W5000").history(period="10y")["Close"]
            
            # 去除时区信息，确保能和 FRED 的时间戳完美对齐
            if wilshire.index.tz is not None:
                wilshire.index = wilshire.index.tz_localize(None)

            # 3. 拼接所有宏观数据
            df = pd.concat([dgs10, dgs2, gdp, wilshire, hy], axis=1)
            df.columns = ["DGS10", "DGS2", "GDP", "WILL5000", "HY"]

            # 4. ffill() 向下填充（解决GDP是季度数据的问题），然后 dropna()
            df = df.ffill().dropna()
            
            return df

        except Exception as e:
            st.error(f"FRED 数据抓取失败: {e}")
            return pd.DataFrame(columns=["DGS10", "DGS2", "GDP", "WILL5000", "HY"])
