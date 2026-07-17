import akshare as ak
import pandas as pd
from .base import BaseIndicator

class OilIndicator(BaseIndicator):
    """中国成品油价调整"""
    def fetch_data(self) -> pd.DataFrame:
        try:
            df = ak.energy_oil_hist()
            df = df.rename(columns={'调整日期': 'date', '汽油价格': 'gasoline', '柴油价格': 'diesel'})
            df['date'] = pd.to_datetime(df['date'])
            df['gasoline'] = pd.to_numeric(df['gasoline'], errors='coerce')
            df['diesel'] = pd.to_numeric(df['diesel'], errors='coerce')
            df = df.dropna(subset=['gasoline']).sort_values('date').copy()
            # The feed may publish the next adjustment before its effective
            # date.  The miniapp's "current price" must not jump early.
            today = pd.Timestamp.now(tz='Asia/Shanghai').tz_localize(None).normalize()
            df = df[df['date'] <= today].copy()
            # Approximate pump-equivalent values using standard reference
            # densities. These are explicitly estimates, not local retail quotes.
            df['gasoline_liter_est'] = df['gasoline'] * 0.00074
            df['diesel_liter_est'] = df['diesel'] * 0.00084
            next_date = df['date'].shift(-1)
            df['days_current'] = (next_date - df['date']).dt.days
            df.loc[df.index[-1], 'days_current'] = max(
                0, (pd.Timestamp.now().normalize() - df.iloc[-1]['date']).days
            )
            return df
        except Exception as e:
            self.logger.error(f"Oil Fetch Error: {e}")
            raise e

    def plot(self, df: pd.DataFrame) -> str:
        fig, axes = self.plotter.create_ratio_axes(ratios=[3, 1])
        
        # 1. Standardized 13-month window
        latest_date = df['date'].max()
        short_threshold = latest_date - pd.DateOffset(months=15)
        df_short = df[df['date'] >= short_threshold].copy()
        
        # History: show 200 adjustments
        df_long = df.iloc[-200:].copy() 
        
        # Color Palette - Premium Oil Theme
        c_gasoline = '#C95A55'
        c_diesel = '#3976A8'
        
        # --- Top: Recent ---
        ax_top = axes[0]
        ax_top.step(df_short['date'], df_short['gasoline'], where='post', color=c_gasoline, linewidth=3.5, label='汽油价格', zorder=3)
        ax_top.step(df_short['date'], df_short['diesel'], where='post', color=c_diesel, linewidth=3, label='柴油价格', zorder=2)
        # Draw current value line for gasoline
        self.plotter.draw_current_line(df_short['gasoline'].iloc[-1], ax_top, c_gasoline)
        
        # Explicit legend
        ax_top.legend(loc='upper left', frameon=True, framealpha=0.9, fontsize=9)
        
        self.plotter.fmt_single(fig, ax_top, title='行业数据-中国油价变动（近15个月）',
                              ylabel='元/吨', rotation=15, data=[df_short['gasoline'], df_short['diesel']])
        self.plotter.set_no_margins(ax_top)
        
        # --- Bottom: History ---
        ax_bot = axes[1]
        baseline = min(df_long['gasoline'].min(), df_long['diesel'].min()) * 0.96
        self.plotter.fill_gradient(ax_bot, df_long['date'], df_long['gasoline'],
                                   color=c_gasoline, alpha_top=0.13, baseline=baseline,
                                   zorder=1, step='post')
        self.plotter.fill_gradient(ax_bot, df_long['date'], df_long['diesel'],
                                   color=c_diesel, alpha_top=0.11, baseline=baseline,
                                   zorder=1, step='post')
        ax_bot.step(df_long['date'], df_long['gasoline'], where='post', color=c_gasoline,
                    alpha=0.9, linewidth=1.8, label='汽油', zorder=4)
        ax_bot.step(df_long['date'], df_long['diesel'], where='post', color=c_diesel,
                    alpha=0.9, linewidth=1.5, label='柴油', zorder=4)
        
        self.plotter.fmt_single(fig, ax_bot, title='历史走势 (200次调整全景)', 
                              ylabel='元/吨', rotation=15,
                              data=[df_long['gasoline'], df_long['diesel']])
        self.plotter.set_no_margins(ax_bot)
        
        path = "output/finance/oil.png"
        self.plotter.save(fig, path)
        return path
