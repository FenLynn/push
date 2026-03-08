from .base import BaseIndicator
import pandas as pd
import akshare as ak
import numpy as np

class BuffettIndicator(BaseIndicator):
    """巴菲特指标 (A股市值 / GDP) - 采用 10 年期平滑重构模型"""
    def __init__(self, manager, plotter):
        super().__init__(manager, plotter)
        self.name = "巴菲特指标"

    def fetch_data(self) -> pd.DataFrame:
        try:
            self.logger.info("Fetching Buffett indicator with 10-year linear smoothing (R8.11)...")
            # 1. 获取基准指数 (SH Composite)
            df_idx = pd.DataFrame()
            idx_sources = [
                ('EM Hist', lambda: ak.index_zh_a_hist(symbol="000001", period="daily")),
                ('EM Daily', lambda: ak.stock_zh_index_daily_em(symbol="sh000001"))
            ]
            for sname, sfunc in idx_sources:
                try:
                    df_tmp = sfunc()
                    if df_tmp is not None and not df_tmp.empty:
                        df_tmp.columns = [c.strip() for c in df_tmp.columns]
                        date_col = '日期' if '日期' in df_tmp.columns else 'date'
                        val_col = '收盘' if '收盘' in df_tmp.columns else 'close'
                        df_idx = df_tmp[[date_col, val_col]].rename(columns={date_col: 'date', val_col: '上证指数'})
                        df_idx['date'] = pd.to_datetime(df_idx['date'])
                        break
                except: continue
            
            if df_idx.empty or len(df_idx) < 100:
                self.logger.warning("Buffett: SH Index data insufficient, skipping.")
                return None

            # 2. 采用对冲还原法计算历史市值
            try:
                df_spot = ak.stock_zh_a_spot_em()
                current_total_cap = df_spot['总市值'].sum() / 1e8 # 亿元
                current_index_price = df_idx.iloc[-1]['上证指数']
                df_idx['total_cap'] = current_total_cap * (df_idx['上证指数'] / current_index_price)
            except:
                df_idx['total_cap'] = df_idx['上证指数'] * 265.0

            # 3. GDP TTM 逻辑
            df_gdp_ttm = pd.DataFrame()
            try:
                df_gdp_raw = ak.macro_china_gdp()
                def parse_q(q_str):
                    y = int(q_str.split('年')[0])
                    if '第1季度' in q_str and '-' not in q_str: return (y, 1)
                    if '1-2季度' in q_str: return (y, 2)
                    if '1-3季度' in q_str: return (y, 3)
                    if '1-4季度' in q_str: return (y, 4)
                    return None
                df_gdp_raw['q_info'] = df_gdp_raw['季度'].apply(parse_q)
                df_gdp_raw = df_gdp_raw.dropna(subset=['q_info'])
                df_gdp_raw['year'] = df_gdp_raw['q_info'].apply(lambda x: x[0])
                df_gdp_raw['q'] = df_gdp_raw['q_info'].apply(lambda x: x[1])
                df_gdp_raw = df_gdp_raw.sort_values(['year', 'q'])
                
                df_gdp_raw['val_cum'] = df_gdp_raw['国内生产总值-绝对值']
                df_gdp_raw['val_single'] = df_gdp_raw['val_cum']
                mask = df_gdp_raw['q'] > 1
                df_gdp_raw.loc[mask, 'val_single'] = df_gdp_raw['val_cum'].diff()
                df_gdp_raw['gdp_ttm'] = df_gdp_raw['val_single'].rolling(4).sum()
                
                def q_to_date(row):
                    y, q = row['year'], row['q']
                    m = {1: '03-31', 2: '06-30', 3: '09-30', 4: '12-31'}[q]
                    return pd.Timestamp(f"{y}-{m}")
                df_gdp_raw['date'] = df_gdp_raw.apply(q_to_date, axis=1)
                df_gdp_ttm = df_gdp_raw.dropna(subset=['gdp_ttm'])[['date', 'gdp_ttm']].rename(columns={'gdp_ttm': 'gdp'})
            except:
                dr_q = pd.date_range(start='2010-03-31', end='2030-12-31', freq='QE')
                df_gdp_ttm = pd.DataFrame({'date': dr_q, 'gdp': [1200000] * len(dr_q)})
                self.logger.warning("Buffett: GDP data unavailable, using flat placeholder.")

            # 4. 鲁棒合并 + 线性插值 (消除台阶感)
            df = pd.merge(df_idx, df_gdp_ttm, on='date', how='outer').sort_values('date')
            df['total_cap'] = df['total_cap'].ffill().bfill()
            # 核心改进：改用线性插值，使 GDP 增长平滑
            df['gdp'] = df['gdp'].interpolate(method='linear').ffill().bfill()
            
            df['buffett_ratio'] = (df['total_cap'] / df['gdp']) * 100
            return df.drop_duplicates(subset=['date']).dropna(subset=['buffett_ratio']).sort_values('date')
        except Exception as e:
            self.logger.error(f"Buffett Fetch Error: {e}")
            return None

    def plot(self, df: pd.DataFrame) -> str:
        fig, axes = self.plotter.create_ratio_axes(ratios=[3, 1])
        ax_top, ax_bottom = axes[0], axes[1]
        
        latest_date = df['date'].max()
        df_short = df[df['date'] >= (latest_date - pd.DateOffset(months=13))].copy()
        
        c_bf = '#8e44ad'    # Wisteria/Violet
        c_warn = '#c0392b'  # Warning Red
        c_safe = '#27ae60'  # Safe Green
        
        # --- Top: Recent Smooth Ratio ---
        ax_top.plot(df_short['date'], df_short['buffett_ratio'], color=c_bf, linewidth=3, label='证券化率 (市值/GDP)')
        self.plotter.fill_gradient(ax_top, df_short['date'], df_short['buffett_ratio'], color=c_bf, alpha_top=0.2)
        
        # Horizontal Warning Lines
        ax_top.axhline(75, color=c_warn, linestyle='--', linewidth=1.5, alpha=0.7, label='警戒线 (75%)')
        ax_top.axhline(50, color=c_safe, linestyle='--', linewidth=1.5, alpha=0.7, label='安全线 (50%)')
        
        self.plotter.draw_current_line(df_short.iloc[-1]['buffett_ratio'], ax_top, c_bf)
        
        # Legend
        ax_top.legend(loc='upper left', frameon=True, framealpha=0.9, fontsize=9)
        
        self.plotter.fmt_single(fig, ax_top, title='巴菲特指标: 估值天平 (近期13月)', 
                               ylabel='证券化率 (%)', rotation=15, 
                               data=df_short['buffett_ratio'])
        self.plotter.set_no_margins(ax_top)
        
        # --- Bottom: Full History ---
        ax_bottom.plot(df['date'], df['buffett_ratio'], color=c_bf, linewidth=1.2, alpha=0.8)
        self.plotter.fmt_single(fig, ax_bottom, title='10年历史全景走势', 
                               ylabel='证券化率 (%)', rotation=15, 
                               data=df['buffett_ratio'])
        self.plotter.set_no_margins(ax_bottom)
        
        path = "output/finance/buffett_indicator.png"
        self.plotter.save(fig, path)
        return path
