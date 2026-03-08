def simple_backtest(price, rsi_signal):
    signal = (rsi_signal < 40).astype(int)
    returns = price.pct_change()
    strategy = returns * signal.shift()
    curve = (1 + strategy).cumprod()
    return curve
