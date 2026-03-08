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

        # 2. 缓存 df 供 MacroDigest 等读取（避免重复 fetch）
        self.manager.df_cache[self.name] = df

        # 3. Check Cache & Update
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
        latest_date = metadata
        url = self.manager.save_plot_info(self.name, latest_date, pic_path)
        if not url:
            self.logger.warning(f"Image upload failed for {self.name}, using local path")
            url = pic_path
        
        return {'url': url, 'date': latest_date, 'name': self.name, 'value': self._get_latest_value(df)}

    def _get_latest_value(self, df):
        """Helper to get latest value string（取最后一个非日期数值列）"""
        try:
            import pandas as pd
            # 找第一个数值列（排除 date 列）
            for col in df.columns:
                if col.lower() in ('date', '日期', 'time'): continue
                if pd.api.types.is_numeric_dtype(df[col]):
                    return str(round(df.iloc[-1][col], 4))
            return ""
        except:
            return ""
