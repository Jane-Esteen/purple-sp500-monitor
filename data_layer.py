import yfinance as yf
import pandas as pd
from fredapi import Fred

FRED_KEY = os.environ.get("FRED_API_KEY")  # 一定要用这个方式读取

class DataLayer:
    def __init__(self, fred_key):
        self.fred = Fred(api_key=FRED_KEY)

    def market_data(self):
        # 下载10年历史数据
        spx = yf.download("^GSPC", period="10y", auto_adjust=True, threads=False)["Close"]
        vix = yf.download("^VIX", period="10y", auto_adjust=True, threads=False)["Close"]

        df = pd.concat([spx, vix], axis=1)
        df.columns = ["SPX", "VIX"]
        df = df.dropna()
        return df

    def macro_data(self):
        dgs10 = self.fred.get_series("DGS10")
        dgs2 = self.fred.get_series("DGS2")
        gdp = self.fred.get_series("GDP")
        wilshire = self.fred.get_series("WILL5000PRFC")
        hy = self.fred.get_series("BAMLH0A0HYM2")

        df = pd.DataFrame({
            "DGS10": dgs10,
            "DGS2": dgs2,
            "GDP": gdp,
            "WILL5000": wilshire,
            "HY": hy
        })
        df = df.dropna()
        return df
