import numpy as np
import pandas as pd


class FactorEngine:

    @staticmethod
    def rsi(series, window=14):
        delta = series.diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        avg_gain = gain.rolling(window).mean()
        avg_loss = loss.rolling(window).mean()
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi

    @staticmethod
    def moving_average(series, window=200):
        return series.rolling(window).mean()

    @staticmethod
    def erp(pe, ten_year_rate):
        if ten_year_rate == 0 or pd.isna(ten_year_rate):
            return np.nan
        # 正确公式：盈利收益率 (1 / PE) - 十年期美债收益率
        earnings_yield = 1 / pe
        return earnings_yield - ten_year_rate


    @staticmethod
    def buffett_indicator(market_cap, gdp):
        if gdp == 0 or pd.isna(gdp):
            return np.nan  # 或者返回0
        return market_cap / gdp

