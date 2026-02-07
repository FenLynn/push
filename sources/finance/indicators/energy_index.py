import akshare as ak
import pandas as pd
from .base import BaseIndicator

class EnergyIndexIndicator(BaseIndicator):
    """中国能源价格指数"""
    
    def fetch_data(self) -> pd.DataFrame:
        try:
            df = ak.macro_china_energy_index()
            cols = df.columns.tolist()
            date_col = next((c for c in cols if '日期' in c or 'date' in c.lower()), cols[0])
            val_col = next((c for c in cols if '最新值' in c or '指数' in c), cols[1])
            
            df = df.rename(columns={date_col: 'date', val_col: 'index'})
            df['date'] = pd.to_datetime(df['date'])
            df['index'] = pd.to_numeric(df['index'], errors='coerce')
            return df.dropna(subset=['index']).sort_values('date')
        except Exception as e:
            self.logger.error(f"Energy Index Fetch Error: {e}")
            raise e

    def plot(self, df: pd.DataFrame) -> str:
        fig, axes = self.plotter.create_ratio_axes(ratios=[3, 1])
        
        # 1. Standardized 13-month window
        latest_date = df['date'].max()
        short_threshold = latest_date - pd.DateOffset(months=13)
        df_short = df[df['date'] >= short_threshold].copy()
        
        # History: show available data (starts around 2011)
        df_long = df.copy() 
        
        color = '#273c75' # Energy blue
        
        # --- Top: Recent ---
        ax_top = axes[0]
        ax_top.plot(df_short['date'], df_short['index'], color=color, linewidth=3.5, label='能源价格指数')
        self.plotter.draw_current_line(df_short['index'].iloc[-1], ax_top, color)
        
        self.plotter.fmt_single(fig, ax_top, title='宏观数据-能源价格指数 (近期13月)', ylabel='指数', rotation=15, 
                               data=df_short['index'])
        self.plotter.set_no_margins(ax_top)
        
        # --- Bottom: History ---
        ax_bot = axes[1]
        ax_bot.plot(df_long['date'], df_long['index'], color=color, linewidth=1.5)
        # Gradient Fill
        self.plotter.fill_gradient(ax_bot, df_long['date'], df_long['index'], color=color)
        
        self.plotter.fmt_single(fig, ax_bot, title='历史走势 (自2011年)', ylabel='指数', rotation=15,
                              data=df_long['index'])
        self.plotter.set_no_margins(ax_bot)
        
        path = "output/finance/energy_index.png"
        self.plotter.save(fig, path)
        return path
