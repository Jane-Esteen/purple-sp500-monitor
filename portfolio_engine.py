class PortfolioEngine:
    @staticmethod
    def position_model(heat_score):
        if heat_score > 80:
            return 0.2
        if heat_score > 65:
            return 0.4
        if heat_score > 50:
            return 0.6
        if heat_score > 35:
            return 0.8
        return 1.0
