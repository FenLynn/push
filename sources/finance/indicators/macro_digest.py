from .base import BaseIndicator
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime

# Import all necessary indicators
from .gdp import GDPIndicator
from .pmi import PMIIndicator
from .trade import TradeIndicator
from .keqiang_index import KeqiangIndicator
from .cpi import CPIIndicator
from .ppi import PPIIndicator
from .oil import OilIndicator
from .pig import PigIndicator
from .m2 import M2Indicator
from .social_finance import SocialFinanceIndicator
from .shibor import ShiborIndicator
from .lpr import LPRIndicator
from .forex import ForexIndicator
from .bond import BondIndicator
from .margin import MarginIndicator
from .market_leverage import MarketLeverageIndicator

class MacroDigestIndicator(BaseIndicator):
    """宏观经济“体检表” (Macro Scorecard)"""
    
    def fetch_data(self) -> pd.DataFrame:
        """
        Fetch representative data for:
        1. Growth: GDP(YoY), PMI(Mfg), Trade(Exp YoY), Keqiang(Index)
        2. Inflation: CPI, PPI, Oil(YoY), Pig(Price)
        3. Liquidity: M2(YoY), SocFin(YoY - approximated), Shibor(3M), LPR(1Y)
        4. Sentiment: Stock(Equity), Bond(10Y), Forex(USDCNY), Margin(Balance)
        """
        data = {}
        try:
            # Helper to get latest value or default
            def get_latest(cls, col_name, date_col='date', default=0.0):
                try:
                    ind = cls(self.manager, self.plotter)
                    df = ind.fetch_data()
                    if df is None or df.empty: return default
                    val = df.sort_values(date_col).iloc[-1][col_name]
                    return val if pd.notnull(val) else default
                except Exception as e:
                    self.logger.warning(f"Failed to fetch {cls.__name__}: {e}")
                    return default

            # --- Growth ---
            data['GDP增速'] = get_latest(GDPIndicator, 'gdp_growth', 5.0)
            data['制造业PMI'] = get_latest(PMIIndicator, 'manufacture', 50.0)
            data['出口增速'] = get_latest(TradeIndicator, 'export_yoy', 5.0)
            data['克强指数'] = get_latest(KeqiangIndicator, 'keqiang_index', 5.0)

            # --- Inflation ---
            data['CPI通胀'] = get_latest(CPIIndicator, 'cpi_m', 'date', 0.5)
            data['PPI通胀'] = get_latest(PPIIndicator, 'ppi_index_yoy', -1.0)

            # --- Liquidity ---
            data['M2增速'] = get_latest(M2Indicator, 'm2_growth', 8.5)
            data['社融增量'] = get_latest(SocialFinanceIndicator, 'value', 20000.0)
            data['Shibor3M'] = get_latest(ShiborIndicator, '3m', 2.0)
            data['LPR-1Y'] = get_latest(LPRIndicator, 'lpr1y', 3.4)

            # --- Sentiment ---
            data['人民币汇率'] = get_latest(ForexIndicator, 'USD', 715.0)
            data['10Y国债'] = get_latest(BondIndicator, 'y10', 2.1)
            data['两融余额'] = get_latest(MarginIndicator, 'balance', 15000.0)
            
            # Create DataFrame
            df = pd.DataFrame([data])
            df['date'] = pd.Timestamp.now()
            return df
            
        except Exception as e:
            self.logger.error(f"MacroDigest Fetch Error: {e}")
            raise e

    def plot(self, df: pd.DataFrame) -> str:
        # Create a Scorecard Plot instead of a time series
        fig = plt.figure(figsize=(10, 6), dpi=120)
        
        # Prepare Data for Heatmap
        # We need to normalize or categorize values to 'Cool', 'Neutral', 'Hot'
        # Since we only have current values here, we'll display Raw Values + Stylized Background
        
        # Structure: 4 Rows (Dimensions) x 3-4 Cols (Indicators)
        # Manually constructing the grid data for visualization
        
        #       | Ind 1 | Ind 2 | Ind 3 | Ind 4
        # Growth| GDP   | PMI   | Export| Keqiang
        # Inflat| CPI   | PPI   | ...   | ...
        
        metrics = [
            ['增长 (Growth)', 'GDP增速', df['GDP增速'].values[0] if 'GDP增速' in df else 0, '%', 5.0],
            ['增长 (Growth)', '制造业PMI', df['制造业PMI'].values[0] if '制造业PMI' in df else 50, '', 50.0],
            ['增长 (Growth)', '出口增速', df['出口增速'].values[0] if '出口增速' in df else 0, '%', 5.0],
            ['增长 (Growth)', '克强指数', df['克强指数'].values[0] if '克强指数' in df else 0, '%', 10.0],
            
            ['通胀 (Inflation)', 'CPI通胀', df['CPI通胀'].values[0] if 'CPI通胀' in df else 0, '%', 2.0],
            ['通胀 (Inflation)', 'PPI通胀', df['PPI通胀'].values[0] if 'PPI通胀' in df else 0, '%', 0.0],
            
            ['流动性 (Liquidity)', 'M2增速', df['M2增速'].values[0] if 'M2增速' in df else 0, '%', 8.5],
            ['流动性 (Liquidity)', '社融增量', df['社融增量'].values[0] if '社融增量' in df else 0, '亿', 20000],
            ['流动性 (Liquidity)', '1年LPR', df['LPR-1Y'].values[0] if 'LPR-1Y' in df else 0, '%', 3.4],
            
            ['情绪 (Sentiment)', 'CNY汇率', df['人民币汇率'].values[0]/10000 if '人民币汇率' in df and df['人民币汇率'].values[0] > 100 else df['人民币汇率'].values[0], '', 7.0], # Handle normalization if needed
            ['情绪 (Sentiment)', '10Y国债', df['10Y国债'].values[0] if '10Y国债' in df else 0, '%', 2.6],
            ['情绪 (Sentiment)', '两融余额', df['两融余额'].values[0] if '两融余额' in df else 0, '亿', 15000],
        ]
        
        # Clean up Forex Scaler (Source returns price, e.g. 715.45 for 100 units or 7.15? ForexIndicator returns raw)
        # Check logic: ForexIndicator returns columns 'USD', 'EUR'... typically ~700 something or 7 something.
        # Let's assume raw value.
        
        # Drawing
        ax = plt.gca()
        ax.axis('off')
        
        # Title
        plt.title('宏观经济核心指标记分卡 (Macro Scorecard)', fontsize=16, fontweight='bold', pad=20, color='#2c3e50')
        plt.text(0.5, 0.96, f"更新时间: {df['date'].iloc[0].strftime('%Y-%m-%d')}", ha='center', fontsize=10, color='#7f8c8d')
        
        # Grid Config
        rows = 4
        cols = 3
        cell_w = 1.0 / cols
        cell_h = 0.85 / rows
        start_y = 0.85
        
        # Access palette colors
        colors = {
            'Grow': '#e8f6f3', 'Inf': '#fdedec', 'Liq': '#eaf2f8', 'Sent': '#f4ecf7'
        }
        
        sections = {
            '增长 (Growth)': [], '通胀 (Inflation)': [], '流动性 (Liquidity)': [], '情绪 (Sentiment)': []
        }
        
        for m in metrics:
            if m[0] in sections: sections[m[0]].append(m)
            
        row_names = list(sections.keys())
        
        for i, section_name in enumerate(row_names):
            y = start_y - (i+1) * cell_h
            items = sections[section_name]
            
            # Row Header
            # plt.text(0, y + cell_h/2, section_name, fontsize=12, fontweight='bold', va='center')
            
            # Draw Cells
            for j, item in enumerate(items[:3]): # Max 3 per row for layout simplicity
                x = j * cell_w
                
                # Background Card
                bg_color = colors.get(section_name[:4], '#ffffff')
                rect = plt.Rectangle((x + 0.02, y + 0.02), cell_w - 0.04, cell_h - 0.04, 
                                   facecolor=bg_color, edgecolor='#bdc3c7', linewidth=0.5) # rx is not supported in Rectangle, use FancyBboxPatch if needed, but simple Rect ok
                ax.add_patch(rect)
                
                # Metric Name
                name = item[1]
                val = item[2]
                unit = item[3]
                ref = item[4]
                
                # Determine Color (Red/Green) based on comparison with Ref (Simplified logic)
                # Growth: > Ref = Good (Red), < Ref = Bad (Green)
                # Inflation: > Ref = High, < Ref = Low
                # Sentiment: depends.
                
                # Just use neutral dark color for value, let user judge
                val_color = '#2c3e50'
                
                # Special Formatting
                if name == 'CNY汇率' and val > 100: val = val / 100 # Adjust if it's 700+
                val_str = f"{val:.2f}{unit}"
                if '万' in unit or '亿' in unit: val_str = f"{int(val)}{unit}"
                
                plt.text(x + cell_w/2, y + cell_h*0.7, name, ha='center', va='center', fontsize=10, color='#7f8c8d')
                plt.text(x + cell_w/2, y + cell_h*0.35, val_str, ha='center', va='center', fontsize=16, fontweight='bold', color=val_color)
        
        plt.tight_layout()
        
        path = "output/finance/macro_digest.png"
        self.plotter.save(fig, path)
        return path
