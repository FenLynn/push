from .base import BaseIndicator
import pandas as pd
import akshare as ak
from datetime import datetime

class StockShareholderIndicator(BaseIndicator):
    """个股股东人数与股价联动分析 (筹码集中度监测)"""
    def __init__(self, manager, plotter, symbol='601318', name='中国平安'):
        super().__init__(manager, plotter)
        self.symbol = symbol
        self.stock_name = name
        self.name = f"{name}股东人数"

    def fetch_data(self) -> pd.DataFrame:
        try:
            self.logger.info(f"Fetching shareholder data for {self.symbol}...")
            # 1. 获取股东人数 (东方财富接口)
            df_holders = ak.stock_zh_a_gdhs_detail_em(symbol=self.symbol)
            df_holders = df_holders[['股东户数统计截止日', '股东户数-本次']].copy()
            df_holders.columns = ['date', 'holders']
            df_holders['date'] = pd.to_datetime(df_holders['date'])
            
            # 2. 确定时间范围 (取最近 20 条公告)
            df_holders = df_holders.sort_values('date').tail(20)
            start_date = df_holders['date'].min()
            end_date = df_holders['date'].max()
            
            # 3. 获取每日历史股价
            self.logger.info(f"Fetching daily price data from {start_date.date()} to {end_date.date()}...")
            df_price = ak.stock_zh_a_hist(symbol=self.symbol, period='daily', 
                                         start_date=start_date.strftime('%Y%m%d'),
                                         end_date=end_date.strftime('%Y%m%d'),
                                         adjust='qfq')
            df_price = df_price[['日期', '收盘']].copy()
            df_price.columns = ['date', 'close']
            df_price['date'] = pd.to_datetime(df_price['date'])
            
            # 4. 合并数据：以价格日期(每日)为基准，左连接股东人数
            df = pd.merge(df_price, df_holders, on='date', how='left')
            return df.sort_values('date')
        except Exception as e:
            self.logger.error(f"StockShareholder Fetch Error for {self.symbol}: {e}")
            return None

    def plot(self, df: pd.DataFrame) -> str:
        # 1. 创建单图双轴
        fig, ax1 = self.plotter.create_single_ax()
        ax2 = ax1.twinx()
        
        # 2. 股东人数 (左轴 - 柱状图，仅在有数据的日期显示)
        df_h = df.dropna(subset=['holders'])
        holders_wan = df_h['holders'] / 10000
        # 柱子加宽一点，使用半透明蓝色
        ax1.bar(df_h['date'], holders_wan, width=20, color='#3498db', alpha=0.25, label='股东人数 (万)')
        
        # 3. 股价 (右轴 - 连续折线图)
        # 使用红色渐变或醒目的线条
        ax2.plot(df['date'], df['close'], color='#e74c3c', linewidth=2.5, label='股价 (元)')
        # 股价下方添加淡淡的渐变填充
        self.plotter.fill_gradient(ax2, df['date'], df['close'], color='#e74c3c', alpha_top=0.15)
        
        # 4. 格式化
        self.plotter.fmt_twinx(fig, ax1, ax2, 
                              title=f"{self.stock_name} ({self.symbol}) 筹码集中度监测", 
                              ylabel_left='股东人数 (万户)', 
                              ylabel_right='股价 (复权收盘价)', 
                              data_left=holders_wan, 
                              data_right=df['close'])
        
        # 5. 特殊标注：标注最新一期数值
        latest_h = df_h.iloc[-1]
        latest_p = df.iloc[-1]
        
        # 标注最新股东人数
        ax1.text(latest_h['date'], latest_h['holders']/10000, f"{latest_h['holders']/10000:.1f}万", 
                 ha='center', va='bottom', color='#2980b9', fontsize=10, fontweight='bold',
                 bbox=dict(boxstyle='round,pad=0.2', facecolor='white', alpha=0.6, edgecolor='none'))
        
        # 标注最新股价
        ax2.text(latest_p['date'], latest_p['close'], f"{latest_p['close']:.2f}", 
                 ha='left', va='center', color='#c0392b', fontsize=10, fontweight='bold')

        # 去除 X 轴边距，让图表充满空间
        self.plotter.set_no_margins(ax1)
        
        path = f"output/finance/shareholder_{self.symbol}.png"
        self.plotter.save(fig, path)
        return path
