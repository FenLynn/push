import akshare as ak
import pandas as pd
from .base import BaseIndicator
from .cpi import CPIIndicator

class RealInterestRateIndicator(BaseIndicator):
    """中国实际利率 (名义利率 - CPI)"""
    
    def fetch_data(self) -> pd.DataFrame:
        try:
            # 1. Nominal Rate (Bond 10Y) - Daily
            df_bond = ak.bond_zh_us_rate()
            df_bond = df_bond[['日期', '中国国债收益率10年']].rename(columns={'日期':'date', '中国国债收益率10年':'nominal'})
            df_bond['date'] = pd.to_datetime(df_bond['date'])
            df_bond['nominal'] = pd.to_numeric(df_bond['nominal'], errors='coerce')
            
            # 2. Inflation (CPI Monthly) - Monthly
            cached_cpi = self.manager.df_cache.get('cpi')
            if cached_cpi is not None and not cached_cpi.empty:
                df_cpi = cached_cpi[['date', 'cpi_y']].rename(columns={'cpi_y': 'cpi'}).copy()
            else:
                df_cpi = CPIIndicator._normalize_nbs_frame(ak.macro_china_cpi())
                df_cpi = df_cpi[['date', 'cpi_y']].rename(columns={'cpi_y': 'cpi'})
            
            # 两种频率先统一为月度：10 年国债取自然月均值，CPI 保持月度同比。
            # 不把月度 CPI 人为复制成每日值，避免制造不存在的日频“实际利率”。
            df_bond['month'] = df_bond['date'].dt.to_period('M')
            df_cpi['month'] = df_cpi['date'].dt.to_period('M')
            bond_monthly = df_bond.groupby('month', as_index=False)['nominal'].mean()
            cpi_monthly = df_cpi.groupby('month', as_index=False)['cpi'].last()
            df = pd.merge(bond_monthly, cpi_monthly, on='month', how='inner')
            df['date'] = df['month'].dt.to_timestamp('M')
            df = df.drop(columns=['month'])
            
            # Calculate Real Rate
            df['real'] = df['nominal'] - df['cpi']
            
            return df.dropna().sort_values('date')
        except Exception as e:
            self.logger.error(f"RealRate Fetch Error: {e}")
            return None

    def plot(self, df: pd.DataFrame) -> str:
        fig, axes = self.plotter.create_ratio_axes(ratios=[3, 1])
        
        # 1. Standardized 13-month window
        latest_date = df['date'].max()
        short_threshold = latest_date - pd.DateOffset(months=13)
        df_short = df[df['date'] >= short_threshold].copy()
        
        # History: 10 Years
        long_threshold = latest_date - pd.DateOffset(years=10)
        df_long = df[df['date'] >= long_threshold].copy()
        
        c_nom = '#e74c3c' # Red (Nominal)
        c_real = '#2c3e50' # Blue (Real)
        c_cpi = '#95a5a6' # Gray (Inflation)
        
        # --- Top: Nominal vs Real ---
        ax_top = axes[0]
        ax_top.plot(df_short['date'], df_short['nominal'], color=c_nom, label='名义利率(10Y)', linestyle='--')
        ax_top.plot(df_short['date'], df_short['real'], color=c_real, linewidth=2.5, label='实际利率(真实成本)')
        
        # Fill area between 0 and Real
        ax_top.fill_between(df_short['date'], df_short['real'], 0, color=c_real, alpha=0.1)

        self.plotter.draw_current_line(df_short['real'].iloc[-1], ax_top, c_real)
        
        self.plotter.fmt_single(fig, ax_top, title='真实资金成本-实际利率 (近期13月)', 
                               ylabel='利率(%)', rotation=15, 
                               data=[df_short['nominal'], df_short['real']])
        self.plotter.set_no_margins(ax_top)
        
        # --- Bottom: 10Y History ---
        ax_bot = axes[1]
        ax_bot.plot(df_long['date'], df_long['real'], color=c_real, linewidth=1.5)
        # Gradient Fill
        self.plotter.fill_gradient(ax_bot, df_long['date'], df_long['real'], color=c_real)
        ax_bot.axhline(y=0, color='gray', linestyle='--')
        
        self.plotter.fmt_single(fig, ax_bot, title='历史实际利率 (10年)', 
                               ylabel='Yield (%)', rotation=15, 
                               data=df_long['real'])
        self.plotter.set_no_margins(ax_bot)
        
        path = "output/finance/real_interest_rate.png"
        self.plotter.save(fig, path)
        return path
