import akshare as ak
import pandas as pd
from .base import BaseIndicator
import numpy as np

class GDPIndicator(BaseIndicator):
    """GDP 国内生产总值"""
    
    def fetch_data(self) -> pd.DataFrame:
        try:
            df = ak.macro_china_gdp()
            
            # Parse quarter to date
            # Format: "2025年第1-4季度" or "2025年第1季度"
            def parse_quarter_info(q_str):
                import re
                match = re.search(r'(\d{4})年第(\d+)(?:-(\d+))?季度', q_str)
                if match:
                    year = int(match.group(1))
                    q_start = int(match.group(2))
                    q_end = int(match.group(3)) if match.group(3) else int(match.group(2))
                    # Use end of quarter for date
                    month = q_end * 3
                    date = pd.Timestamp(year=year, month=month, day=1) + pd.offsets.MonthEnd(0)
                    return pd.Series({'date': date, 'year': year, 'q_start': q_start, 'q_end': q_end})
                return pd.Series({'date': pd.NaT, 'year': None, 'q_start': None, 'q_end': None})
            
            quarter_info = df['季度'].apply(parse_quarter_info)
            df = pd.concat([df, quarter_info], axis=1)
            
            # Rename columns
            df = df.rename(columns={
                '国内生产总值-绝对值': 'gdp_cumulative',
                '国内生产总值-同比增长': 'gdp_growth'
            })
            
            # Calculate single quarter GDP
            # For single quarter rows (q_start == q_end), use cumulative directly
            # For cumulative rows, calculate difference
            df = df.sort_values(['year', 'q_end'], ascending=[False, False])
            df['gdp_single'] = df['gdp_cumulative']
            
            # For each year, calculate single quarter values
            for year in df['year'].unique():
                if pd.isna(year):
                    continue
                year_mask = df['year'] == year
                year_data = df[year_mask].sort_values('q_end')
                
                # Calculate single quarter GDP by subtraction
                for idx in year_data.index:
                    q_end = df.loc[idx, 'q_end']
                    if q_end > 1:
                        # Find previous quarter cumulative
                        prev_q = q_end - 1
                        prev_mask = (df['year'] == year) & (df['q_end'] == prev_q)
                        if prev_mask.any():
                            prev_cumulative = df.loc[prev_mask, 'gdp_cumulative'].values[0]
                            df.loc[idx, 'gdp_single'] = df.loc[idx, 'gdp_cumulative'] - prev_cumulative
            
            return df.sort_values('date')
        except Exception as e:
            self.logger.error(f"GDP Fetch Error: {e}")
            raise e

    def plot(self, df: pd.DataFrame) -> str:
        # Use 3:1 ratio layout
        fig, axes = self.plotter.create_ratio_axes(ratios=[3, 1])
        
        df['date'] = pd.to_datetime(df['date'])
        
        # Get only single quarter data (q_start == q_end) for recent 4 quarters
        df_single = df[df['q_start'] == df['q_end']].copy()
        df_short = df_single.iloc[-4:].copy()    # Recent 4 quarters
        df_long = df_single.iloc[-80:].copy()    # History 80 quarters
        
        # Colors
        c_single = '#3498DB'       # Single quarter - Blue
        c_cumulative = '#E74C3C'   # Cumulative - Red
        c_growth = '#F39C12'       # Growth rate - Orange
        
        # --- Top: Recent (4 Quarters) - Dual bars + Growth ---
        ax_top = axes[0]
        
        # Prepare data for grouped bars
        x = np.arange(len(df_short))
        width = 0.35
        
        # Draw bars
        bars1 = ax_top.bar(x - width/2, df_short['gdp_single'], width, 
                          label='单季度GDP', color=c_single, alpha=0.8)
        bars2 = ax_top.bar(x + width/2, df_short['gdp_cumulative'], width,
                          label='累计GDP', color=c_cumulative, alpha=0.8)
        
        ax_top.set_xticks(x)
        ax_top.set_xticklabels([f'Q{int(q)}' for q in df_short['q_end']], rotation=0)
        
        # Growth rate on right axis
        ax_top_r = ax_top.twinx()
        ax_top_r.plot(x, df_short['gdp_growth'], 'D-', color=c_growth,
                     linewidth=2, markersize=5, label='同比增长(%)')
        
        # Format top
        self.plotter.fmt_twinx(fig, ax_top, ax_top_r,
                             title='宏观数据-GDP (近期4季度)',
                             ylabel_left='GDP(亿元)',
                             ylabel_right='同比增长(%)',
                             rotation=0)
        ax_top.margins(x=0.1)
        
        # --- Bottom: History (20 Years) - Growth Rate ---
        ax_bot = axes[1]
        ax_bot.plot(df_long['date'], df_long['gdp_growth'], color=c_growth,
                   linewidth=1.5, label='GDP同比增长(%)')
        ax_bot.fill_between(df_long['date'], df_long['gdp_growth'], 
                           color=c_growth, alpha=0.3)
        ax_bot.axhline(y=0, color='black', linestyle='--', linewidth=0.8, alpha=0.5)
        
        # Format bottom with internal title
        self.plotter.fmt_single(fig, ax_bot,
                              title='历史走势 (20年)',
                              ylabel='GDP同比增长(%)',
                              rotation=15)
        self.plotter.set_no_margins(ax_bot)
        
        # Save
        path = "output/finance/gdp.png"
        self.plotter.save(fig, path)
        return path
