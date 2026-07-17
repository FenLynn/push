import akshare as ak
import pandas as pd
import numpy as np
from .base import BaseIndicator
import time

class InternationalRateIndicator(BaseIndicator):
    """国际主要央行利率 (美联储, 欧洲央行, 日本央行)"""
    def fetch_data(self) -> pd.DataFrame:
        try:
            # 1. USA Fed Rate
            df_usa = ak.macro_bank_usa_interest_rate()
            df_usa = df_usa[['日期', '今值']].rename(columns={'日期': 'date', '今值': 'usa'})
            df_usa['date'] = pd.to_datetime(df_usa['date'])
            df_usa['usa'] = pd.to_numeric(df_usa['usa'], errors='coerce')
            
            # 2. Euro ECB Rate (Try multiple times or handle failure)
            df_eur = pd.DataFrame(columns=['date', 'eur'])
            try:
                df_eur = ak.macro_bank_euro_interest_rate()
                df_eur = df_eur[['日期', '今值']].rename(columns={'日期': 'date', '今值': 'eur'})
                df_eur['date'] = pd.to_datetime(df_eur['date'])
                df_eur['eur'] = pd.to_numeric(df_eur['eur'], errors='coerce')
            except Exception as e:
                self.logger.warning(f"Euro Rate Fetch Failed: {e}")

            # 3. Japan BOJ Rate
            df_jpy = pd.DataFrame(columns=['date', 'jpy'])
            try:
                df_jpy = ak.macro_bank_japan_interest_rate()
                df_jpy = df_jpy[['日期', '今值']].rename(columns={'日期': 'date', '今值': 'jpy'})
                df_jpy['date'] = pd.to_datetime(df_jpy['date'])
                df_jpy['jpy'] = pd.to_numeric(df_jpy['jpy'], errors='coerce')
            except Exception as e:
                self.logger.warning(f"Japan Rate Fetch Failed: {e}")

            # China reference: 1Y LPR. It is a loan prime rate rather than the
            # same policy instrument as the overseas series, so render it gray.
            cached_lpr = self.manager.df_cache.get('lpr')
            if cached_lpr is not None and {'date', 'lpr1y'}.issubset(cached_lpr.columns):
                df_cn = cached_lpr[['date', 'lpr1y']].rename(columns={'lpr1y': 'cn'}).copy()
            else:
                df_cn = ak.macro_china_lpr()[['TRADE_DATE', 'LPR1Y']].rename(
                    columns={'TRADE_DATE': 'date', 'LPR1Y': 'cn'}
                )
            df_cn['date'] = pd.to_datetime(df_cn['date'])
            df_cn['cn'] = pd.to_numeric(df_cn['cn'], errors='coerce')
            
            # Merge
            df = pd.merge(df_usa, df_eur, on='date', how='outer')
            df = pd.merge(df, df_jpy, on='date', how='outer')
            df = pd.merge(df, df_cn, on='date', how='outer')
            df = df.sort_values('date')
            
            # Forward fill to create continuous rates
            df[['usa', 'eur', 'jpy', 'cn']] = df[['usa', 'eur', 'jpy', 'cn']].ffill()
            
            return df.dropna(subset=['usa'], how='all') # Keep if at least one is present
        except Exception as e:
            self.logger.error(f"International Rate Fetch Error: {e}")
            raise e

    def plot(self, df: pd.DataFrame) -> str:
        fig, axes = self.plotter.create_ratio_axes(ratios=[3, 1])
        df['date'] = pd.to_datetime(df['date'])
        
        # 1. Standardized 13-month window
        latest_date = df['date'].max()
        short_threshold = latest_date - pd.DateOffset(months=15)
        df_short = df[df['date'] >= short_threshold].copy()
        
        # 2. History (last 20 years)
        df_long = df.iloc[-500:].copy() # Since it's decision based, 500 points is a lot
        
        # Color Palette - Global Central Bank Theme
        c_usa = '#e74c3c'  # Crimson (美联储 - 全球定价基准)
        c_eur = '#3498db'  # Dodger Blue (欧央行)
        c_jpy = '#9b59b6'  # Amethyst (日央行)
        c_cn = '#8A94A0'
        
        # --- Top (Recent) ---
        ax_top = axes[0]
        ax_top.step(df_short['date'], df_short['usa'], where='post', color=c_usa, linewidth=3, label='Fed (USA)')
        if 'eur' in df_short.columns:
            ax_top.step(df_short['date'], df_short['eur'], where='post', color=c_eur, linewidth=2.5, label='ECB (Euro)')
        if 'jpy' in df_short.columns:
            ax_top.step(df_short['date'], df_short['jpy'], where='post', color=c_jpy, linewidth=2.5, label='BOJ (Japan)')
        ax_top.step(df_short['date'], df_short['cn'], where='post', color=c_cn,
                    linewidth=1.8, linestyle='--', label='中国1Y LPR（参考）')
        
        # Draw current value line for Fed
        self.plotter.draw_current_line(df_short.iloc[-1]['usa'], ax_top, c_usa)
        
        # Explicit legend
        ax_top.legend(loc='upper right', frameon=True, framealpha=0.9, fontsize=9)
            
        self.plotter.fmt_single(fig, ax_top, title='全球视野-主要央行基准利率（近15个月）',
                               ylabel='利率 (%)', rotation=15, 
                               data=[df_short['usa'], df_short.get('eur', [0]), df_short.get('jpy', [0]), df_short['cn']])
        self.plotter.set_no_margins(ax_top)
        
        # --- Bottom (History) ---
        ax_bot = axes[1]
        ax_bot.plot(df_long['date'], df_long['usa'], color=c_usa, linewidth=1.5, alpha=0.9, label='USA')
        if 'eur' in df_long.columns:
            ax_bot.plot(df_long['date'], df_long['eur'], color=c_eur, linewidth=1.2, alpha=0.7, label='Euro')
        if 'jpy' in df_long.columns:
            ax_bot.plot(df_long['date'], df_long['jpy'], color=c_jpy, linewidth=1.2, alpha=0.7, label='Japan')
        ax_bot.plot(df_long['date'], df_long['cn'], color=c_cn, linewidth=1.1,
                    alpha=0.8, linestyle='--', label='China 1Y LPR')
            
        # Gradient Fill for USA (emphasize dominance)
        self.plotter.fill_gradient(ax_bot, df_long['date'], df_long['usa'], color=c_usa, alpha_top=0.2)
        
        self.plotter.fmt_single(fig, ax_bot, title='全球主要利率历史趋势 (20年全景)', 
                               ylabel='利率 (%)', rotation=15, 
                               data=[df_long['usa'], df_long.get('eur', [0]), df_long.get('jpy', [0]), df_long['cn']])
        self.plotter.set_no_margins(ax_bot)
        
        path = "output/finance/international_rate.png"
        self.plotter.save(fig, path)
        return path
