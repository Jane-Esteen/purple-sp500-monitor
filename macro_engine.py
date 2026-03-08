class MacroEngine:
    @staticmethod
    def macro_regime(yield_curve, credit_spread):
        if yield_curve < 0 and credit_spread > 5:
            return "衰退风险"
        if yield_curve > 1 and credit_spread < 3:
            return "扩张期"
        return "经济晚周期"

    @staticmethod
    def market_heat(vix, rsi, buffett, erp):
        score_vix = 100 - min(vix * 3, 100)
        score_rsi = rsi
        score_buffett = min(buffett * 50, 100)
        score_erp = max(0, min(erp * 200, 100))
        heat = (score_vix + score_rsi + score_buffett + score_erp) / 4
        return heat
