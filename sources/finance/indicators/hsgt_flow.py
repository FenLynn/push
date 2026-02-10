"""
HK-Connect Capital Flow Indicator
港股通资金流向指标

数据源：AkShare - 东方财富
说明：自2024年8月19日起，北向资金不再披露盘中实时买卖金额，只能获取日终数据
"""
import akshare as ak
import pandas as pd
from .base import BaseIndicator
from core.cache_db import CacheDB

class HKConnectFlowIndicator(BaseIndicator):
    """港股通资金流向（北向资金 + 南向资金）"""
    
    def __init__(self):
        super().__init__()
        self.cache_db = CacheDB()
    
    def fetch_data(self) -> pd.DataFrame:
        """
        获取港股通资金流向数据
        
        策略：
        1. 尝试从 AkShare 获取最新数据
        2. 合并缓存的历史数据
        3. 更新缓存
        """
        try:
            # 获取最新数据（日级）
            # 接口: stock_hsgt_hist_em (东方财富-沪深港通资金流向-历史数据)
            df_new = ak.stock_hsgt_hist_em()
            
            # 数据清洗
            df_new = df_new.rename(columns={
                '日期': 'date',
                '沪股通': 'hk_sh',          # 沪股通净流入
                '深股通': 'hk_sz',          # 深股通净流入
                '北向': 'north_flow',        # 北向合计
                '南向': 'south_flow',        # 南向（港股通）
            })
            
            # 只保留需要的列
            cols_to_keep = ['date', 'north_flow', 'south_flow']
            if 'hk_sh' in df_new.columns:
                cols_to_keep.extend(['hk_sh', 'hk_sz'])
            
            df_new = df_new[[c for c in cols_to_keep if c in df_new.columns]]
            
            df_new['date'] = pd.to_datetime(df_new['date'])
            
            # 转换为数值
            for col in df_new.columns:
                if col != 'date':
                    df_new[col] = pd.to_numeric(df_new[col], errors='coerce')
            
            # 保存到缓存
            self.cache_db.save_time_series('hsgt_flow', df_new, frequency='daily')
            
            self.logger.info(f"Fetched {len(df_new)} records from AkShare")
            
        except Exception as e:
            self.logger.error(f"Failed to fetch from AkShare: {e}")
            self.logger.info("Loading from cache...")
        
        # 从缓存加载所有数据
        df = self.cache_db.load_time_series('hsgt_flow', frequency='daily')
        
        if df.empty:
            self.logger.warning("No data in cache, using fallback")
            return self._generate_fallback()
        
        return df.sort_values('date')
    
    def _generate_fallback(self) -> pd.DataFrame:
        """生成模拟数据（备用）"""
        dates = pd.date_range(end=pd.Timestamp.now(), periods=365, freq='D')
        import numpy as np
        
        # 模拟北向资金波动
        north = np.cumsum(np.random.randn(365) * 30 + 10)  # 平均流入
        south = np.cumsum(np.random.randn(365) * 20 + 5)
        
        return pd.DataFrame({
            'date': dates,
            'north_flow': north,
            'south_flow': south
        })
    
    def plot(self, df: pd.DataFrame) -> str:
        """绘制港股通资金流向图"""
        fig, axes = self.plotter.create_ratio_axes(ratios=[3, 1])
        
        # 只显示近13个月
        latest_date = df['date'].max()
        threshold = latest_date - pd.DateOffset(months=13)
        df_short = df[df['date'] >= threshold].copy()
        
        # 历史更长：2年
        long_threshold = latest_date - pd.DateOffset(years=2)
        df_long = df[df['date'] >= long_threshold].copy()
        
        # 颜色
        c_north = '#e74c3c'  # 红色（北向）
        c_south = '#3498db'  # 蓝色（南向）
        
        # --- Top: 资金流向对比 ---
        ax_top = axes[0]
        
        # 绘制北向资金
        ax_top.plot(df_short['date'], df_short['north_flow'], 
                   color=c_north, linewidth=2.5, label='北向资金（沪深股通）')
        
        # 绘制南向资金
        if 'south_flow' in df_short.columns:
            ax_top.plot(df_short['date'], df_short['south_flow'], 
                       color=c_south, linewidth=2.5, label='南向资金（港股通）', alpha=0.8)
        
        # 当前值线
        self.plotter.draw_current_line(df_short['north_flow'].iloc[-1], ax_top, c_north)
        
        self.plotter.fmt_single(fig, ax_top, 
                               title='港股通资金流向 (近13月)', 
                               ylabel='净流入 (亿元)', 
                               rotation=15,
                               data=[df_short['north_flow']])
        self.plotter.set_no_margins(ax_top)
        
        # --- Bottom: 累计流入 ---
        ax_bot = axes[1]
        
        # 计算累计
        df_long['north_cumsum'] = df_long['north_flow'].cumsum()
        
        # 面积图
        ax_bot.fill_between(df_long['date'], df_long['north_cumsum'], 0,
                           color=c_north, alpha=0.3)
        ax_bot.plot(df_long['date'], df_long['north_cumsum'], 
                   color=c_north, linewidth=1.5, label='北向累计')
        
        # 零线
        ax_bot.axhline(y=0, color='gray', linestyle='--', linewidth=0.8)
        
        self.plotter.fmt_single(fig, ax_bot, 
                               title='北向资金累计流入 (2年)', 
                               ylabel='累计 (亿元)', 
                               rotation=15,
                               data=df_long['north_cumsum'])
        self.plotter.set_no_margins(ax_bot)
        
        path = "output/finance/hsgt_flow.png"
        self.plotter.save(fig, path)
        return path
