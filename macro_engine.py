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
        # 1. VIX：越高越恐慌（越便宜），热度越低
        score_vix = 100 - min(vix * 3, 100)
        
        # 2. RSI：越高越超买，热度越高
        score_rsi = rsi
        
        # 3. Buffett：越高越泡沫，热度越高 (>2.0 基本满分)
        score_buffett = min(buffett * 50, 100)
        
        # 4. 【核心修复】ERP：越高越便宜（热度低），越低越危险（热度高）
        # 设定：ERP >= 5% (0.05) 为极度安全 (0分)
        # 设定：ERP <= 0% (0.00) 为极度危险 (100分)
        score_erp = 100 - max(0, min(erp * 2000, 100))
        
        # 计算综合热度
        heat = (score_vix + score_rsi + score_buffett + score_erp) / 4
        return heat
