from .base import BaseIndicator
import pandas as pd
import akshare as ak
import numpy as np

class KeqiangIndicator(BaseIndicator):
    """克强指数 - 电力、货运、贷款综合经济指标 (10年期重构版)"""
    def __init__(self, manager, plotter):
        super().__init__(manager, plotter)
        self.name = "克强指数"

    def fetch_data(self) -> pd.DataFrame:
        try:
            self.logger.info("Fetching Keqiang Index components with 10-year reconstruction (R8.12)...")
            
            # 1. 工业用电量
            df_elec = pd.DataFrame()
            try:
                df_elec_raw = ak.macro_china_society_electricity()
                df_elec = df_elec_raw[['统计时间', '全社会用电量同比']].copy()
                df_elec.columns = ['date', 'elec_yoy']
                df_elec['date'] = pd.to_datetime(df_elec['date'].astype(str).str.replace('.', '-'), errors='coerce')
                df_elec = df_elec.dropna()
            except: pass
            
            # 2. 铁路货运
            df_rail = pd.DataFrame()
            try:
                df_rail_raw = ak.macro_china_railway_transport()
                # 兼容性寻找列名
                yoy_col = [c for c in df_rail_raw.columns if '同比' in str(c)][0]
                date_col = df_rail_raw.columns[0]
                df_rail = df_rail_raw[[date_col, yoy_col]].copy()
                df_rail.columns = ['date', 'rail_yoy']
                df_rail['date'] = pd.to_datetime(df_rail['date'].astype(str).str.replace('.', '-'), errors='coerce')
                df_rail = df_rail.dropna()
            except: pass

            # 3. 贷款
            df_loan = pd.DataFrame()
            try:
                df_loan_raw = ak.macro_china_loan_growth() 
                yoy_col = [c for c in df_loan_raw.columns if '同比' in str(c)][0]
                date_col = df_loan_raw.columns[0]
                df_loan = df_loan_raw[[date_col, yoy_col]].copy()
                df_loan.columns = ['date', 'loan_yoy']
                df_loan['date'] = pd.to_datetime(df_loan['date'].astype(str).str.replace('.', '-'), errors='coerce')
                df_loan = df_loan.dropna()
            except: pass
            
            # 4. 10年期全量补全与自愈
            dr = pd.date_range(end=pd.Timestamp.now().normalize(), periods=3650, freq='D')
            df_final = pd.DataFrame({'date': dr})
            
            # 合并数据
            if not df_elec.empty: df_final = pd.merge(df_final, df_elec, on='date', how='left')
            else: df_final['elec_yoy'] = float('nan')
            
            if not df_rail.empty: df_final = pd.merge(df_final, df_rail, on='date', how='left')
            else: df_final['rail_yoy'] = float('nan')
            
            if not df_loan.empty: df_final = pd.merge(df_final, df_loan, on='date', how='left')
            else: df_final['loan_yoy'] = float('nan')
            
            # 线性插值消除台阶，数据不足时保留 NaN（不注入随机数）
            for col in ['elec_yoy', 'rail_yoy', 'loan_yoy']:
                if col in df_final.columns:
                    df_final[col] = df_final[col].interpolate(method='linear').ffill().bfill()
            
            # 5. 计算综合克强指数: 0.4*用电 + 0.25*铁路 + 0.35*贷款
            df_final['keqiang_index'] = (
                df_final['elec_yoy'] * 0.4 + 
                df_final['rail_yoy'] * 0.25 + 
                df_final['loan_yoy'] * 0.35
            )
            
            return df_final.sort_values('date')
        except Exception as e:
            self.logger.error(f"Keqiang Index Fetch Error: {e}")
            return None

    def plot(self, df: pd.DataFrame) -> str:
        fig, axes = self.plotter.create_ratio_axes(ratios=[3, 1])
        ax_top, ax_bottom = axes[0], axes[1]
        
        latest_date = df['date'].max()
        df_short = df[df['date'] >= (latest_date - pd.DateOffset(months=13))].copy()
        
        # Color Palette - Professional & Layered
        c_kj = '#2c3e50'    # Midnight Blue (Combined Index)
        c_elec = '#f1c40f'  # Flat Gold (Electricity)
        c_rail = '#e67e22'  # Carrot Orange (Railway)
        c_loan = '#16a085'  # Greenish Teal (Loan)
        
        # --- Top: Recent Trend ---
        ax_top.plot(df_short['date'], df_short['keqiang_index'], color=c_kj, linewidth=3.5, label='克强指数 (综合)')
        ax_top.plot(df_short['date'], df_short['elec_yoy'], color=c_elec, linestyle='--', alpha=0.6, label='用电同比')
        ax_top.plot(df_short['date'], df_short['rail_yoy'], color=c_rail, linestyle='--', alpha=0.6, label='货运同比')
        ax_top.plot(df_short['date'], df_short['loan_yoy'], color=c_loan, linestyle='--', alpha=0.6, label='贷款同比')
        
        self.plotter.draw_current_line(df_short.iloc[-1]['keqiang_index'], ax_top, c_kj)
        
        # Explicit Legend Fix
        ax_top.legend(loc='upper right', frameon=True, framealpha=0.9, fontsize=9)
        
        self.plotter.fmt_single(fig, ax_top, title='克强指数: 经济景气三剑客 (近期13月)', 
                               ylabel='同比增长 (%)', rotation=15, 
                               data=df_short['keqiang_index'])
        self.plotter.set_no_margins(ax_top)
        
        # --- Bottom: 10 Year History ---
        ax_bottom.plot(df['date'], df['keqiang_index'], color=c_kj, linewidth=1.2, alpha=0.8, label='历史走势')
        self.plotter.fill_gradient(ax_bottom, df['date'], df['keqiang_index'], color=c_kj, alpha_top=0.2)
        ax_bottom.axhline(0, color='#95a5a6', linestyle='-', alpha=0.3)
        
        self.plotter.fmt_single(fig, ax_bottom, title='10年历史全景走势', 
                               ylabel='同比增长 (%)', rotation=15, 
                               data=df['keqiang_index'])
        self.plotter.set_no_margins(ax_bottom)
        
        path = "output/finance/keqiang_index.png"
        self.plotter.save(fig, path)
        return path
