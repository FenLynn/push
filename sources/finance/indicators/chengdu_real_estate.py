import pandas as pd
from .base import BaseIndicator
from core.d1_client import D1Client
from core.image_upload import upload_image_with_cdn
import logging

class ChengduRealEstateIndicator(BaseIndicator):
    """
    成都每日房产成交 (D1 Source)
    Transactions: New Home vs Second Hand
    """
    def __init__(self, manager, plotter):
        super().__init__(manager, plotter)
        self.d1 = D1Client()
        self.name = 'chengdu_real_estate'

    def fetch_data(self) -> pd.DataFrame:
        if not self.d1.enabled:
            return pd.DataFrame()

        # Fetch last 30 days for Chengdu
        sql = """
        SELECT date, category, value, unit 
        FROM estate_daily 
        WHERE city = 'Chengdu' 
          AND category IN ('NewHome_Count', 'SecondHand_Count')
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
            self.logger.error(f"Chengdu data parse error: {e}")
            return pd.DataFrame()

    def plot(self, df: pd.DataFrame) -> str:
        if df.empty: return None
        
        fig, ax = self.plotter.create_single_ax()
        
        # Split Data
        new_home = df[df['category'] == 'NewHome_Count']
        second_hand = df[df['category'] == 'SecondHand_Count']
        
        has_data = False
        
        if not new_home.empty:
            ax.plot(new_home['date'], new_home['value'], 
                   color='#e74c3c', linewidth=2.5, marker='o', markersize=6, 
                   label='新房成交(套)')
            self.plotter.draw_current_line(new_home['value'].iloc[-1], ax, '#e74c3c')
            has_data = True
            
        if not second_hand.empty:
            ax.plot(second_hand['date'], second_hand['value'], 
                   color='#3498db', linewidth=2.5, marker='s', markersize=6, 
                   label='二手成交(套)')
            self.plotter.draw_current_line(second_hand['value'].iloc[-1], ax, '#3498db')
            has_data = True
            
        if not has_data:
            return None

        self.plotter.fmt_single(fig, ax, 
                               title='成都每日楼市成交 (Transaction Flow)', 
                               ylabel='成交套数', 
                               rotation=30)
                               
        # Annotate latest values
        for sub_df, color, offset in [(new_home, '#e74c3c', 10), (second_hand, '#3498db', -15)]:
            if not sub_df.empty:
                last = sub_df.iloc[-1]
                ax.annotate(f"{int(last['value'])}", 
                           xy=(last['date'], last['value']), 
                           xytext=(5, offset), textcoords='offset points',
                           color=color, fontweight='bold',
                           arrowprops=None)

        path = "output/finance/chengdu_real_estate.png"
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
                'description': '成都新房/二手房成交趋势',
                'tags': ['estate', 'chengdu']
            }
        except Exception as e:
            self.logger.error(f"ChengduRealEstate run failed: {e}")
            return None
