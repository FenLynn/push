from .base import BaseIndicator
import pandas as pd
import akshare as ak
from .cpi import CPIIndicator
from .ppi import PPIIndicator

class ScissorsGapIndicator(BaseIndicator):
    """CPI-PPI 剪刀差 (反映工业利润空间)"""
    def fetch_data(self) -> pd.DataFrame:
        try:
            # Re-use CPI and PPI data fetching logic
            cpi = CPIIndicator(self.manager, self.plotter)
            ppi = PPIIndicator(self.manager, self.plotter)
            
            df_cpi = cpi.fetch_data()
            df_ppi = ppi.fetch_data()
            
            # Robust CPI column detection
            cpi_value_col = None
            if 'cpi_y' in df_cpi.columns:
                cpi_value_col = 'cpi_y'
            elif 'value' in df_cpi.columns:
                cpi_value_col = 'value'
            else:
                # Fallback - use first numeric column after date
                numeric_cols = df_cpi.select_dtypes(include=['float64', 'int64']).columns.tolist()
                if numeric_cols:
                    cpi_value_col = numeric_cols[0]
            
            if not cpi_value_col:
                raise ValueError("Could not find CPI value column")
                
            df_cpi = df_cpi[['date', cpi_value_col]].rename(columns={cpi_value_col: 'cpi'})
            
            # Robust PPI column detection  
            ppi_value_col = None
            if 'ppi' in df_ppi.columns:
                ppi_value_col = 'ppi'
            elif 'ppi_growth' in df_ppi.columns:
                ppi_value_col = 'ppi_growth'
            elif 'value' in df_ppi.columns:
                ppi_value_col = 'value'
            else:
                # Fallback - use first numeric column after date
                numeric_cols = df_ppi.select_dtypes(include=['float64', 'int64']).columns.tolist()
                if numeric_cols:
                    ppi_value_col = numeric_cols[0]
            
            if not ppi_value_col:
                raise ValueError("Could not find PPI value column")
                
            df_ppi = df_ppi[['date', ppi_value_col]].rename(columns={ppi_value_col: 'ppi'})
            
            df = pd.merge(df_cpi, df_ppi, on='date', how='inner')
            df['gap'] = df['cpi'] - df['ppi']
            return df.sort_values('date')
        except Exception as e:
            self.logger.error(f"ScissorsGap Fetch Error: {e}")
            raise e

    def plot(self, df: pd.DataFrame) -> str:
        fig, axes = self.plotter.create_ratio_axes(ratios=[3, 1])
        
        # 1. 13-month window
        latest_date = df['date'].max()
        short_threshold = latest_date - pd.DateOffset(months=13)
        df_short = df[df['date'] >= short_threshold].copy()
        
        # 2. History (last 10 years)
        df_long = df.iloc[-120:].copy()
        
        # Color Palette - Scissors Gap Theme
        c_cpi = '#e74c3c'     # Crimson (消费端价格)
        c_ppi = '#2c3e50'     # Midnight Blue (生产端成本)
        c_gap = '#16a085'     # Green Sea (利润空间)
        
        # --- Top (Recent) ---
        ax_top = axes[0]
        ax_top.plot(df_short['date'], df_short['cpi'], 'o-', color=c_cpi, linewidth=2.5, 
                   markersize=6, markeredgecolor='white', markeredgewidth=1, label='CPI 同比 (%)')
        ax_top.plot(df_short['date'], df_short['ppi'], 's-', color=c_ppi, linewidth=2.5, 
                   markersize=6, markeredgecolor='white', markeredgewidth=1, label='PPI 同比 (%)')
        
        # Enhanced fill gap with higher alpha
        ax_top.fill_between(df_short['date'], df_short['cpi'], df_short['ppi'], 
                           where=(df_short['cpi'] >= df_short['ppi']), color=c_cpi, alpha=0.15, label='CPI>PPI (利润压缩)')
        ax_top.fill_between(df_short['date'], df_short['cpi'], df_short['ppi'], 
                           where=(df_short['cpi'] < df_short['ppi']), color=c_ppi, alpha=0.15, label='PPI>CPI (成本上涨)')
        
        # Explicit legend
        ax_top.legend(loc='upper right', frameon=True, framealpha=0.9, fontsize=9)
        
        self.plotter.fmt_single(fig, ax_top, title='CPI-PPI 剪刀差: 工业利润空间 (近期13月)', 
                               ylabel='同比 (%)', rotation=15, 
                               data=[df_short['cpi'], df_short['ppi']])
        self.plotter.set_no_margins(ax_top)

        # --- Bottom (Gap History) ---
        ax_bot = axes[1]
        ax_bot.plot(df_long['date'], df_long['gap'], color=c_gap, linewidth=1.5, alpha=0.9, label='Gap (CPI-PPI)')
        self.plotter.fill_gradient(ax_bot, df_long['date'], df_long['gap'], color=c_gap, alpha_top=0.25)
        ax_bot.axhline(y=0, color='#95a5a6', linestyle='--', linewidth=1.5, alpha=0.7)
        
        # Draw current value line
        self.plotter.draw_current_line(df_long.iloc[-1]['gap'], ax_bot, c_gap)
        
        self.plotter.fmt_single(fig, ax_bot, title='剪刀差历史走势 (10年全景)', 
                               ylabel='Gap (%)', rotation=15, 
                               data=[df_long['gap']])
        self.plotter.set_no_margins(ax_bot)
        
        path = "output/finance/scissors_gap.png"
        self.plotter.save(fig, path)
        return path
