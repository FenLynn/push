"""
Core Database Module - Unified SQLite Storage
"""
import sqlite3
import pandas as pd
import os
import logging
from datetime import datetime

class CoreDB:
    """全局数据库管理类 (SQLite)"""
    
    _instance = None
    
    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(CoreDB, cls).__new__(cls, *args, **kwargs)
        return cls._instance

    def __init__(self, db_path=None):
        if not hasattr(self, 'initialized'):
            if db_path is None:
                # Default to data/push.db
                base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                data_dir = os.path.join(base_dir, 'data')
                if not os.path.exists(data_dir):
                    os.makedirs(data_dir)
                db_path = os.path.join(data_dir, 'push.db')
            
            self.db_path = os.path.abspath(db_path)
            self.logger = logging.getLogger('Push.CoreDB')
            self.initialized = True
            self._init_db()

    def _init_db(self):
        """初始化数据库连接"""
        try:
            # 测试连接
            with sqlite3.connect(self.db_path) as conn:
                self.logger.info(f"Connected to database: {self.db_path}")
        except Exception as e:
            self.logger.error(f"Failed to connect to database: {e}")

    def get_connection(self):
        """获取数据库连接 (Context Manager friendly)"""
        return sqlite3.connect(self.db_path)

    def save_monitor_data(self, df: pd.DataFrame, table_name: str, if_exists='append', unique_index=None):
        """
        保存监控数据到数据库
        
        Args:
            df: Pandas DataFrame
            table_name: 表名
            if_exists: 'fail', 'replace', 'append'
            unique_index: 唯一索引列名 (list), 用于避免重复插入
        """
        if df.empty:
            return

        conn = self.get_connection()
        try:
            # 如果指定了唯一索引，先处理去重 (简单策略：先读出来对比，或者使用临时表)
            # 这里为了简单，如果 if_exists='append' 且有 unique_index，我们做 "INSERT OR IGNORE" 逻辑
            # 但 pandas 默认不支持 upsert。
            # 策略: 
            # 1. 存入 temp 表
            # 2. 执行 INSERT OR IGNORE INTO target SELECT * FROM temp
            
            if if_exists == 'append' and unique_index:
                temp_table = f"{table_name}_temp"
                df.to_sql(temp_table, conn, if_exists='replace', index=False)
                
                # 构建主键/唯一约束（如果表不存在，先建表）
                # 这里假设表已经存在或者第一次通过 temp 推断。
                # 简化逻辑：直接使用 pandas to_sql，如果报错再处理？不，pandas 不处理 deduplication。
                
                # 推荐方式：由调用者保证 df 只有新数据，或者使用 unique constraint + INSERT OR IGNORE
                # 考虑到用户新手，我们实现一个简单的 "增量更新"：
                # 读取现有表 -> 过滤掉已存在的数据 -> append
                
                try:
                    existing = pd.read_sql(f'SELECT * FROM "{table_name}"', conn)
                    # 假设 unique_index 是日期列
                    # 过滤 df
                    # 这是一个简化的去重逻辑
                    if not existing.empty:
                        # 构造唯一键集合
                        # 假设 unique_index 是 ['date']
                        if isinstance(unique_index, str): unique_index = [unique_index]
                        
                        existing_keys = set(existing[unique_index].apply(tuple, axis=1))
                        current_keys = df[unique_index].apply(tuple, axis=1)
                        
                        # 筛选出不在 existing_keys 中的行
                        df = df[~current_keys.isin(existing_keys)]
                        
                    if df.empty:
                        self.logger.info(f"Table {table_name}: No new data to append.")
                        return
                    
                except Exception:
                    # 表可能不存在，忽略错误直接写入
                    pass

            df.to_sql(table_name, conn, if_exists=if_exists, index=False)
            self.logger.info(f"Saved {len(df)} rows to {table_name}")
            
        except Exception as e:
            self.logger.error(f"Error saving to {table_name}: {e}")
        finally:
            conn.close()

    def get_monitor_data(self, table_name: str, limit: int = None, order_by: str = None) -> pd.DataFrame:
        """获取数据"""
        conn = self.get_connection()
        try:
            sql = f'SELECT * FROM "{table_name}"'
            if order_by:
                sql += f" ORDER BY {order_by}"
            if limit:
                sql += f" LIMIT {limit}"
            
            return pd.read_sql(sql, conn)
        except Exception as e:
            self.logger.error(f"Error reading {table_name}: {e}")
            return pd.DataFrame()
        finally:
            conn.close()

# Global Instance
db = CoreDB()
