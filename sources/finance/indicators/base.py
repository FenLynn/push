import pandas as pd
from abc import ABC, abstractmethod
import logging
from ..manager import DataManager
from ..plot import Plotter

class BaseIndicator(ABC):
    """指标基类"""
    
    def __init__(self, manager: DataManager, plotter: Plotter):
        self.manager = manager
        self.plotter = plotter
        self.logger = logging.getLogger(f"Push.Finance.{self.__class__.__name__}")
        # Default name from class name (e.g., CPIIndicator -> cpi)
        self.name = self.__class__.__name__.lower().replace('indicator', '')

    @abstractmethod
    def fetch_data(self) -> pd.DataFrame:
        """获取数据 (需返回包含 'date' 列的 DataFrame)"""
        pass

    @abstractmethod
    def plot(self, df: pd.DataFrame) -> str:
        """
        绘制图表
        Args:
            df: 数据
        Returns:
            str: 本地图片保存路径
        """
        pass

    def run(self, force=False):
        """执行流程: Fetch -> Check -> Plot -> Upload"""
        self.logger.info(f"Running {self.name}...")
        
        # 1. Fetch
        try:
            df = self.fetch_data()
        except Exception as e:
            self.logger.error(f"Fetch failed: {e}")
            return None

        # 2. Check Cache & Update
        needs_update, metadata = self.manager.check_update_needed(self.name, df, force)
        
        if not needs_update:
            url = metadata
            try:
                date_str = str(df.iloc[-1]['date'])
            except: 
                date_str = "cached"
            
            return {'url': url, 'date': date_str, 'name': self.name, 'value': self._get_latest_value(df)}

        # 3. Plot
        try:
            pic_path = self.plot(df)
            if not pic_path: return None
        except Exception as e:
            self.logger.error(f"Plot failed: {e}")
            return None
        
        # 4. Upload & Cache (metadata is latest_date here)
        # DISABLE UPLOAD FOR TESTING as per User Request
        latest_date = metadata
        # url = self.manager.save_plot_info(self.name, latest_date, pic_path)
        url = "local_test_mode"
        
        return {'url': url, 'date': latest_date, 'name': self.name, 'value': self._get_latest_value(df)}

    def _get_latest_value(self, df):
        """Helper to get latest value string"""
        try:
            # Try getting the second column (usually value)
            col = df.columns[1] 
            return str(df.iloc[-1][col])
        except:
            return ""
