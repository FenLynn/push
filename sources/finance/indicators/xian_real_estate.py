import pandas as pd
from .base import BaseIndicator
from core.d1_client import D1Client
from core.image_upload import upload_image_with_cdn
import logging

class XianRealEstateIndicator(BaseIndicator):
    """
    西安二手房挂牌库存 (D1 Source)
    Inventory Pressure
    """
    def __init__(self, manager, plotter):
        super().__init__(manager, plotter)
        self.d1 = D1Client()
        self.name = 'xian_real_estate'

    def fetch_data(self) -> pd.DataFrame:
        if not self.d1.enabled:
            return pd.DataFrame()

        # Fetch last 30 days for Xian
        sql = """
        SELECT date, category, value, unit 
        FROM estate_daily 
        WHERE city = 'Xian' 
          AND category = 'SecondHand_Count_Anjuke'
          AND date >= date('now', '-30 days', 'localtime')
        ORDER BY date ASC
        """
        res = self.d1.query(sql)
        
        real_rows = []
        if res.get('success') and res.get('data'):
             rows = res['data']
             if isinstance(rows, list) and len(rows) > 0 and 'results' in rows[0]:
                 real_rows = rows[0]['results']
        
        if not real_rows:
            return pd.DataFrame()

        try:
            df = pd.DataFrame(real_rows)
            df['date'] = pd.to_datetime(df['date'])
            df['value'] = pd.to_numeric(df['value'], errors='coerce')
            return df
        except Exception as e:
            self.logger.error(f"Xian data parse error: {e}")
            return pd.DataFrame()

    def plot(self, df: pd.DataFrame) -> str:
        if df.empty: return None
        
        fig, ax = self.plotter.create_single_ax()
        
        color = '#f39c12' # Orange
        
        # Plot Line
        ax.plot(df['date'], df['value'], color=color, linewidth=2, marker='o', markersize=4, label='二手挂牌量(套)')
        
        # Fill Area (Gradient-like effect using simple fill for now, or use plotter helper)
        self.plotter.fill_gradient(ax, df['date'], df['value'], color=color, alpha_top=0.3)
        
        self.plotter.fmt_single(fig, ax, 
                               title='西安二手房挂牌库存 (Inventory Pressure)', 
                               ylabel='挂牌套数', 
                               rotation=30)
                               
        # Annotate latest
        last = df.iloc[-1]
        ax.annotate(f"{int(last['value'])}", 
                   xy=(last['date'], last['value']), 
                   xytext=(0, 10), textcoords='offset points',
                   color=color, fontweight='bold', ha='center')

        path = "output/finance/xian_real_estate.png"
        self.plotter.save(fig, path)
        return path

    def run(self):
        try:
            df = self.fetch_data()
            if df.empty: return None
            
            img_path = self.plot(df)
            if not img_path: return None
            
            url = upload_image_with_cdn(img_path)
            if not url: return None
            
            latest_date = df['date'].max().strftime('%Y-%m-%d')
            
            return {
                'name': self.name,
                'value': 'Chart', 
                'date': latest_date,
                'plot_url': url,
                'description': '西安二手房挂牌库存趋势',
                'tags': ['estate', 'xian']
            }
        except Exception as e:
            self.logger.error(f"XianRealEstate run failed: {e}")
            return None
