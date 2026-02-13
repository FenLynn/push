import akshare as ak
import pandas as pd
from .base import BaseIndicator

class SugarIndicator(BaseIndicator):
    """食糖现货价格"""
    def fetch_data(self) -> pd.DataFrame:
        try:
            df = ak.index_sugar_msweet()
            # Debug: print columns if needed
            # print(f"Sugar columns: {df.columns}")
            
            cols = df.columns.tolist()
            # Find date column: look for '日期', 'date', or 'time'
            date_col = next((c for c in cols if any(x in str(c).lower() for x in ['日期', 'date', 'time'])), None)
            
            # Find value column: look for '指数', '价格', 'price', 'value', 'close'
            val_col = next((c for c in cols if any(x in str(c).lower() for x in ['指数', '价格', 'price', 'value', 'close']) and c != date_col), None)
            
            if not date_col or not val_col:
                # Fallback: assume 0 is date, 1 is value
                date_col = cols[0]
                val_col = cols[1]

            df = df.rename(columns={date_col: 'date', val_col: 'price'})
            df['date'] = pd.to_datetime(df['date'], errors='coerce')
            df['price'] = pd.to_numeric(df['price'], errors='coerce')
            return df.dropna(subset=['price', 'date']).sort_values('date')
        except TypeError as e:
            if "Invalid value" in str(e) and "dtype 'str'" in str(e):
                 self.logger.warning(f"Sugar Data Source Error (Akshare Upstream Bug): {e}. SkippingSugar.")
                 return pd.DataFrame() # Return empty to skip safely
            self.logger.error(f"Sugar Fetch Error: {e}", exc_info=True)
            raise e
        except Exception as e:
            self.logger.error(f"Sugar Fetch Error: {e}", exc_info=True)
            raise e

    def plot(self, df: pd.DataFrame) -> str:
        fig, axes = self.plotter.create_ratio_axes(ratios=[3, 1])
        df['date'] = pd.to_datetime(df['date'])
        
        # 1. Standardized 13-month window
        latest_date = df['date'].max()
        short_threshold = latest_date - pd.DateOffset(months=13)
        df_short = df[df['date'] >= short_threshold].copy()
        
        # History: show ~10-20 years (Daily data)
        df_long = df.iloc[-5000:].copy() 
        
        color = '#e67e22' # Carrot Orange (Premium)
        
        # --- Top: Recent ---
        ax_top = axes[0]
        ax_top.plot(df_short['date'], df_short['price'], color=color, linewidth=3, label='中国食糖指数')
        self.plotter.draw_current_line(df_short['price'].iloc[-1], ax_top, color)
        
        self.plotter.fmt_single(fig, ax_top, title='行业数据-中国食糖指数 (近期13月)', ylabel='指数', rotation=15, data=df_short['price'])
        self.plotter.set_no_margins(ax_top)
        
        # --- Bottom: History ---
        ax_bot = axes[1]
        ax_bot.plot(df_long['date'], df_long['price'], color=color, linewidth=1.5)
        # Gradient Fill
        self.plotter.fill_gradient(ax_bot, df_long['date'], df_long['price'], color=color)
        
        self.plotter.fmt_single(fig, ax_bot, title='历史走势 (20年)', ylabel='指数', rotation=15, data=df_long['price'])
        self.plotter.set_no_margins(ax_bot)
        
        path = "output/finance/sugar.png"
        self.plotter.save(fig, path)
        return path
