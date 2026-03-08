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
    def erp(pe, rate):
        earnings_yield = 1 / pe
        return earnings_yield - rate

    @staticmethod
    def buffett_indicator(market_cap, gdp):
        return market_cap / gdp
