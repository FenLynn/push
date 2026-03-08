from .base import BaseIndicator
import pandas as pd
import akshare as ak
import numpy as np

class LiquidityPortraitIndicator(BaseIndicator):
    """流动性画像 - 市值与 M2 对比 (10年期重构版)"""
    def __init__(self, manager, plotter):
        super().__init__(manager, plotter)
        self.name = "流动性画像"

    def fetch_data(self) -> pd.DataFrame:
        try:
            self.logger.info("Fetching Liquidity components with 10-year history (R8.11)...")
            
            # 1. 货币供应量 (M2)
            df_m2 = pd.DataFrame()
            try:
                df_m2_raw = ak.macro_china_money_supply()
                def parse_m2_date(d_str):
                    try:
                        y = int(d_str.split('年')[0])
                        m = int(d_str.split('年')[1].split('月')[0])
                        return pd.Timestamp(f"{y}-{m:02d}-01")
                    except: return None
                
                df_m2_raw['date'] = df_m2_raw['月份'].apply(parse_m2_date)
                m2_val_col = '货币和准货币(M2)-数量(亿元)'
                df_m2 = df_m2_raw.dropna(subset=['date'])[['date', m2_val_col]].rename(columns={m2_val_col: 'm2'})
                df_m2['m2'] = df_m2['m2'].astype(float)
            except: pass

            # 2. 指数 (SH Composite)
            df_idx = pd.DataFrame()
            try:
                df_idx = ak.index_zh_a_hist(symbol="000001", period="daily")
                df_idx = df_idx[['日期', '收盘']].rename(columns={'日期': 'date', '收盘': '上证明细'})
                df_idx['date'] = pd.to_datetime(df_idx['date'])
            except: pass

            if df_idx.empty or len(df_idx) < 100:
                self.logger.warning("Liquidity: Index data insufficient, skipping.")
                return None

            if df_m2.empty or len(df_m2) < 12:
                self.logger.warning("Liquidity: M2 data insufficient, skipping.")
                return None

            # 4. 市值对冲还原法
            current_total_cap = 880000 # 假设基准 or 从 spot 获取 (此处简化，逻辑同前)
            current_index_price = df_idx.iloc[-1]['上证明细']
            df_idx['market_cap'] = current_total_cap * (df_idx['上证明细'] / current_index_price)

            # 5. 鲁棒合并 + 线性插值
            df = pd.merge(df_idx, df_m2, on='date', how='outer').sort_values('date')
            df['m2'] = df['m2'].interpolate(method='linear').ffill().bfill()
            df['market_cap'] = df['market_cap'].ffill().bfill()
            df['上证明细'] = df['上证明细'].ffill().bfill()
            
            df['liquidity_ratio'] = (df['market_cap'] / df['m2']) * 100
            
            return df.drop_duplicates(subset=['date']).dropna().sort_values('date')
        except Exception as e:
            self.logger.error(f"Liquidity Fetch Error: {e}")
            return None

    def plot(self, df: pd.DataFrame) -> str:
        fig, axes = self.plotter.create_ratio_axes(ratios=[3, 1])
        ax_top, ax_bottom = axes[0], axes[1]
        
        latest_date = df['date'].max()
        df_short = df[df['date'] >= (latest_date - pd.DateOffset(months=13))].copy()
        
        # Color Palette - Premium Liquidity Theme
        c_m2 = '#1abc9c'      # Turquoise (流动性充裕)
        c_cap = '#3498db'     # Dodger Blue (风险资产)
        c_idx = '#e74c3c'     # Crimson (参考点位)
        c_ratio = '#8e44ad'   # Violet (比率)
        
        # --- Top: M2 vs Market Cap ---
        ax_top_twin = ax_top.twinx()
        ax_top.plot(df_short['date'], df_short['m2'] / 10000, color=c_m2, linewidth=2.5, label='广义货币 M2 (万亿)')
        ax_top.plot(df_short['date'], df_short['market_cap'] / 10000, color=c_cap, linewidth=2.5, linestyle='--', label='A股总市值 (万亿)')
        ax_top_twin.plot(df_short['date'], df_short['上证明细'], color=c_idx, alpha=0.4, linewidth=1.5, label='上证指数')
        
        # Draw current value lines
        self.plotter.draw_current_line(df_short.iloc[-1]['m2'] / 10000, ax_top, c_m2)
        self.plotter.draw_current_line(df_short.iloc[-1]['market_cap'] / 10000, ax_top, c_cap)
        
        # Merge legends
        h1, l1 = ax_top.get_legend_handles_labels()
        h2, l2 = ax_top_twin.get_legend_handles_labels()
        ax_top.legend(h1+h2, l1+l2, loc='upper left', frameon=True, framealpha=0.9, fontsize=9)
        
        self.plotter.fmt_twinx(fig, ax_top, ax_top_twin, title='流动性池: 市值与 M2 波动对比 (近13月)', 
                              ylabel_left='规模 (万亿)', ylabel_right='点位', 
                              data_left=[df_short['m2']/10000, df_short['market_cap']/10000], 
                              data_right=df_short['上证明细'])
        self.plotter.set_no_margins(ax_top)
        
        # --- Bottom: Ratio ---
        ratio = df['liquidity_ratio']
        ax_bottom.plot(df['date'], ratio, color=c_ratio, linewidth=1.2, alpha=0.8)
        self.plotter.fill_gradient(ax_bottom, df['date'], ratio, color=c_ratio, alpha_top=0.2)
        
        self.plotter.fmt_single(fig, ax_bottom, title='证券化比例 (10年回溯全景)', 
                               ylabel='证券化率 (%)', rotation=15, data=ratio)
        self.plotter.set_no_margins(ax_bottom)
        
        path = "output/finance/liquidity_portrait.png"
        self.plotter.save(fig, path)
        return path
