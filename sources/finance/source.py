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
    LPRIndicator, InternationalRateIndicator, InsuranceIndicator,
    NEVSaleIndicator, RealEstateIndicator,
    TradeIndicator, NewsIndicator,
    ScissorsGapIndicator, ElectricityIndicator, MunicipalRealEstateIndicator,
    MacroDigestIndicator, StockShareholderIndicator,
    ERPIndicator, MarketLeverageIndicator, BuffettIndicator,
    KeqiangIndicator, LiquidityPortraitIndicator,
    M1M2GapIndicator, MarketPEIndicator, CrossBorderIndicator, RealInterestRateIndicator
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
            # Phase 4: Industry and Real Estate
            NEVSaleIndicator(self.manager, self.plotter),
            RealEstateIndicator(self.manager, self.plotter),
            # Phase 5: Special Indicators
            TradeIndicator(self.manager, self.plotter),
            NewsIndicator(self.manager, self.plotter),
            # Phase 6: Advanced Macro
            ScissorsGapIndicator(self.manager, self.plotter),
            ElectricityIndicator(self.manager, self.plotter),
            MunicipalRealEstateIndicator(self.manager, self.plotter),
            MacroDigestIndicator(self.manager, self.plotter),
            # Phase 7: Stock Specific
            StockShareholderIndicator(self.manager, self.plotter, symbol='601318', name='中国平安'),
            # Phase 8: Advanced Macro & Sentiment
            ERPIndicator(self.manager, self.plotter),
            MarketLeverageIndicator(self.manager, self.plotter),
            BuffettIndicator(self.manager, self.plotter),
            KeqiangIndicator(self.manager, self.plotter),
            LiquidityPortraitIndicator(self.manager, self.plotter),
            # Phase 10: Advanced Market & Valuation
            M1M2GapIndicator(self.manager, self.plotter),
            MarketPEIndicator(self.manager, self.plotter),
            CrossBorderIndicator(self.manager, self.plotter),
            RealInterestRateIndicator(self.manager, self.plotter),
        ]
        self.logger = logging.getLogger("Push.Source.Finance")

    def run(self):
        self.logger.info("Starting Finance Run...")
        
        # Define Categories
        CATEGORY_MAP = {
            'macro_digest': '智能综述 & 舆情 (Intelligence & Sentiment)',
            'news': '智能综述 & 舆情 (Intelligence & Sentiment)',
            
            'cpi': '宏观经济 (Macro Economy)',
            'ppi': '宏观经济 (Macro Economy)',
            'pmi': '宏观经济 (Macro Economy)',
            'gdp': '宏观经济 (Macro Economy)',
            'm2': '宏观经济 (Macro Economy)',
            'socialfinance': '宏观经济 (Macro Economy)',
            'trade': '宏观经济 (Macro Economy)',
            'keqiang': '宏观经济 (Macro Economy)',
            'keqiang_index': '宏观经济 (Macro Economy)',
            'buffett': '宏观经济 (Macro Economy)',
            'buffett_indicator': '宏观经济 (Macro Economy)',
            'erp': '宏观经济 (Macro Economy)',
            
            'liquidity': '流动性与定价 (Liquidity & Pricing)',
            'liquidity_portrait': '流动性与定价 (Liquidity & Pricing)',
            'scissors_gap': '流动性与定价 (Liquidity & Pricing)',
            'international_rate': '流动性与定价 (Liquidity & Pricing)',
            'commodity': '流动性与定价 (Liquidity & Pricing)',
            'forex': '流动性与定价 (Liquidity & Pricing)',
            'margin': '流动性与定价 (Liquidity & Pricing)',
            'market_leverage': '流动性与定价 (Liquidity & Pricing)',
            
            'shibor': '利率与债市 (Interest Rate & Bond)',
            'lpr': '利率与债市 (Interest Rate & Bond)',
            'bond': '利率与债市 (Interest Rate & Bond)',
            
            'real_estate': '行业与板块 (Industry & Sector)',
            'nev_sale': '行业与板块 (Industry & Sector)',
            'oil': '行业与板块 (Industry & Sector)',
            'sox': '行业与板块 (Industry & Sector)',
            'insurance': '行业与板块 (Industry & Sector)',
            'pig': '行业与板块 (Industry & Sector)',
            'sugar': '行业与板块 (Industry & Sector)',
            'energyindex': '行业与板块 (Industry & Sector)',
            
            'm1_m2_gap': '深度分析 (Advanced Analysis)',
            'market_pe': '深度分析 (Advanced Analysis)',
            'cross_border': '深度分析 (Advanced Analysis)',
            'real_interest_rate': '深度分析 (Advanced Analysis)',
        }
        
        # Organize results by category
        sections = {
            '智能综述 & 舆情 (Intelligence & Sentiment)': [],
            '宏观经济 (Macro Economy)': [],
            '流动性与定价 (Liquidity & Pricing)': [],
            '利率与债市 (Interest Rate & Bond)': [],
            '利率与债市 (Interest Rate & Bond)': [],
            '行业与板块 (Industry & Sector)': [],
            '深度分析 (Advanced Analysis)': []
        }
        
        count = 0
        for ind in self.indicators:
            try:
                res = ind.run()
                if res:
                    # Enrich display name
                    names = {
                        'macro_digest': '宏观经济核心指标记分卡 (Macro Scorecard)',
                        'news': '新闻联播云图 (News Cloud)',
                        'cpi': 'CPI 居民消费价格指数', 
                        'socialfinance': '社融规模增量',
                        'ppi': 'PPI 工业生产者价格指数',
                        'pmi': 'PMI 采购经理人指数',
                        'm2': 'M2 货币供应量',
                        'gdp': 'GDP 国内生产总值',
                        'trade': '进出口贸易',
                        'keqiang': '克强指数',
                        'keqiang_index': '克强指数',
                        'erp': 'ERP 股债利差',
                        'buffett': '巴菲特指标',
                        'buffett_indicator': '巴菲特指标',
                        'liquidity': '流动性画像',
                        'liquidity_portrait': '流动性画像',
                        'scissors_gap': 'CPI-PPI 剪刀差',
                        'international_rate': '全球央行利率 (Fed/ECB/BOJ)',
                        'forex': '外汇市场 (USD/EUR/JPY)',
                        'commodity': '商品黄金 (Gold)',
                        'margin': '融资融券 (Leverage)',
                        'shibor': 'SHIBOR 银行间拆借利率',
                        'lpr': 'LPR 贷款报价利率',
                        'bond': '国债收益率 (10Y/2Y)',
                        'real_estate': '国房景气指数',
                        'nev_sale': '新能源车销量',
                        'oil': '成品油价格 (Gas/Diesel)',
                        'sox': '费城半导体指数 (SOX)',
                        'insurance': '保险保费收入',
                        'pig': '猪肉价格 (Pig)',
                        'sugar': '白糖期货 (Sugar)',
                        
                        'm1_m2_gap': 'M1-M2 剪刀差 (活化度)',
                        'market_pe': '全A市场估值 (上证PE)',
                        'cross_border': '中美利差 (10Y)',
                        'real_interest_rate': '中国实际利率 (真实成本)',
                        
                    }
                    res['display_name'] = names.get(ind.name, ind.name.upper())
                    
                    # Add meta info (optional, e.g. latest value)
                    if 'value' in res:
                         res['meta'] = str(res['value'])
                    
                    # Assign to category
                    cat = CATEGORY_MAP.get(ind.name, '行业与板块 (Industry & Sector)')
                    if cat not in sections:
                        sections['行业与板块 (Industry & Sector)'].append(res)
                    else:
                        sections[cat].append(res)
                    count += 1
            except Exception as e:
                self.logger.error(f"Indicator {ind.name} failed: {e}")
        
        self.logger.info(f"Generated {count} charts in {len(sections)} sections.")
        
        # Classify by update date (incremental logic)
        today = datetime.now().strftime("%Y-%m-%d")
        updated_today = []
        not_updated = []
        
        for section_items in sections.values():
            for item in section_items:
                if item.get('date') == today:
                    updated_today.append(item)
                else:
                    not_updated.append(item)
        
        # Render HTML
        data = {
            'today': today,
            'updated': updated_today,
            'cached': not_updated
        }
        
        html = self.render_template('finance.html', data)
        
        return Message(
            title=f"宏观日报 ({data['today']})",
            content=html,
            type='html',
            metadata={'source': 'finance'}
        )
