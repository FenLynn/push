from .base import BaseIndicator
import pandas as pd
import akshare as ak
import numpy as np

class MarketLeverageIndicator(BaseIndicator):
    """市场杠杆率 - 两融余额 vs 自由流通市值 (10年期重构版)"""
    def __init__(self, manager, plotter):
        super().__init__(manager, plotter)
        self.name = "两融杠杆率"

    def fetch_data(self) -> pd.DataFrame:
        try:
            self.logger.info("Fetching Leverage components with 10-year reconstruction (R8.11)...")
            
            # 1. 两融余额 (SSE Total - Faster & More Accurate)
            df_margin = pd.DataFrame()
            try:
                # 使用宏观数据接口，避免每日详情接口挂死
                df_sse_raw = ak.macro_china_market_margin_sh()
                df_sse_raw['date'] = pd.to_datetime(df_sse_raw['日期'])
                # 融资融券余额 (Total Margin Balance)
                df_sse_raw['margin_balance'] = pd.to_numeric(df_sse_raw['融资融券余额'], errors='coerce')
                
                df_margin = df_sse_raw[['date', 'margin_balance']].sort_values('date')
            except Exception as e:
                self.logger.error(f"Market Margin Fetch Error: {e}")

            # 2. 指数 (SH Composite)
            df_idx = pd.DataFrame()
            try:
                df_idx = ak.index_zh_a_hist(symbol="000001", period="daily")
                df_idx = df_idx[['日期', '收盘']].rename(columns={'日期': 'date', '收盘': '上征指数'})
                df_idx['date'] = pd.to_datetime(df_idx['date'])
            except: pass

            if df_idx.empty or len(df_idx) < 100:
                self.logger.warning("Leverage: Index data insufficient, skipping.")
                return None

            if df_margin.empty or len(df_margin) < 50:
                self.logger.warning("Leverage: Margin data insufficient, skipping.")
                return None

            # 4. 流通市值对冲还原法
            current_float_cap = 640000 
            current_index_price = df_idx.iloc[-1]['上征指数']
            df_idx['float_cap'] = current_float_cap * (df_idx['上征指数'] / current_index_price)

            # 5. 鲁棒合并
            df = pd.merge(df_idx, df_margin[['date', 'margin_balance']], on='date', how='outer').sort_values('date')
            df['margin_balance'] = df['margin_balance'].ffill().bfill()
            df['float_cap'] = df['float_cap'].ffill().bfill()
            df['上征指数'] = df['上征指数'].ffill().bfill()
            
            # 杠杆率 = 两融余额 / 流通市值 * 100
            df['leverage_ratio'] = (df['margin_balance'] / (df['float_cap'] * 1e8)) * 100
            
            return df.drop_duplicates(subset=['date']).dropna().sort_values('date')
        except Exception as e:
            self.logger.error(f"Market Leverage Fetch Error: {e}")
            return None

    def plot(self, df: pd.DataFrame) -> str:
        fig, axes = self.plotter.create_ratio_axes(ratios=[3, 1])
        ax_top, ax_bottom = axes[0], axes[1]
        
        latest_date = df['date'].max()
        df_short = df[df['date'] >= (latest_date - pd.DateOffset(months=13))].copy()
        
        # Top: Leverage Ratio (Recent)
        ax_top.plot(df_short['date'], df_short['leverage_ratio'], color='#e67e22', linewidth=2.5, label='两融杠杆率 (%)')
        ax_top_twin = ax_top.twinx()
        ax_top_twin.plot(df_short['date'], df_short['上征指数'], color='gray', alpha=0.3, label='上证指数')
        
        self.plotter.fmt_twinx(fig, ax_top, ax_top_twin, title='市场杠杆热度 (10年期全场景对齐) - 近13月', 
                              ylabel_left='杠杆率 (%)', ylabel_right='点位', 
                              data_left=df_short['leverage_ratio'], data_right=df_short['上征指数'])
        
        # Bottom: Historical Full View
        ax_bottom.plot(df['date'], df['leverage_ratio'], color='#d35400', linewidth=1, alpha=0.7)
        self.plotter.fill_gradient(ax_bottom, df['date'], df['leverage_ratio'], color='#d35400', alpha_top=0.1)
        self.plotter.fmt_single(fig, ax_bottom, title='杠杆率 10 年期全景趋势', ylabel='%', data=df['leverage_ratio'])
        
        path = "output/finance/market_leverage.png"
        self.plotter.save(fig, path)
        return path
