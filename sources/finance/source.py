from ..base import BaseSource
from core import Message
from .manager import DataManager
from .plot import Plotter
from .indicators import (
    CPIIndicator, SocialFinanceIndicator,
    MarginIndicator, ForexIndicator, CommodityIndicator,
    SOXIndicator, ShiborIndicator, BondIndicator,
    GDPIndicator, PPIIndicator, PMIIndicator, M2Indicator,
    SugarIndicator, CommodityIndexIndicator, EnergyIndexIndicator,
    PigIndicator, OilIndicator,
    LPRIndicator, InternationalRateIndicator, InsuranceIndicator
)
from datetime import datetime
import logging

class FinanceSource(BaseSource):
    def __init__(self, **kwargs):
        super().__init__()
        self.manager = DataManager()
        self.plotter = Plotter()
        self.indicators = [
            CPIIndicator(self.manager, self.plotter),
            SocialFinanceIndicator(self.manager, self.plotter),
            MarginIndicator(self.manager, self.plotter),
            ForexIndicator(self.manager, self.plotter),
            CommodityIndicator(self.manager, self.plotter),
            SOXIndicator(self.manager, self.plotter),
            ShiborIndicator(self.manager, self.plotter),
            BondIndicator(self.manager, self.plotter),
            # Phase 1: Core Macro Indicators
            GDPIndicator(self.manager, self.plotter),
            PPIIndicator(self.manager, self.plotter),
            PMIIndicator(self.manager, self.plotter),
            M2Indicator(self.manager, self.plotter),
            # Phase 2: Price and Commodity Indices
            SugarIndicator(self.manager, self.plotter),
            CommodityIndexIndicator(self.manager, self.plotter),
            EnergyIndexIndicator(self.manager, self.plotter),
            PigIndicator(self.manager, self.plotter),
            OilIndicator(self.manager, self.plotter),
            # Phase 3: Financial Interest Rates
            LPRIndicator(self.manager, self.plotter),
            InternationalRateIndicator(self.manager, self.plotter),
            InsuranceIndicator(self.manager, self.plotter),
        ]
        self.logger = logging.getLogger("Push.Source.Finance")

    def run(self):
        self.logger.info("Starting Finance Run...")
        results = []
        for ind in self.indicators:
            try:
                res = ind.run()
                if res:
                    # Enrich display name
                    names = {'cpi': 'CPI 居民消费价格指数', 'socialfinance': '社融规模增量'}
                    res['display_name'] = names.get(ind.name, ind.name.upper())
                    results.append(res)
            except Exception as e:
                self.logger.error(f"Indicator {ind.name} failed: {e}")
        
        count = len(results)
        self.logger.info(f"Generated {count} charts.")
        
        # Render HTML
        data = {
            'items': results,
            'today': datetime.now().strftime("%Y-%m-%d"),
            'title': '宏观经济日报'
        }
        
        html = self.render_template('finance_v2.html', data)
        
        return Message(
            title=f"宏观日报 ({data['today']})",
            content=html,
            type='html',
            metadata={'source': 'finance'}
        )
