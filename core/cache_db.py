"""
Unified Time Series Cache Database
统一时序数据缓存数据库

用途：
1. 存储历史金融数据（防止API失效后数据丢失）
2. 减少API调用频率
3. 支持离线分析

支持的数据类型：
- 港股通资金流向 (hsgt_north, hsgt_south)
- GDP, M2 等宏观指标
- 房产成交数据
- 任意时序数据
"""
import sqlite3
import json
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any, Union
import pandas as pd

# Database path
DATA_DIR = Path(__file__).parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)
DB_PATH = DATA_DIR / "cache.db"

# SQL Schema
SCHEMA = """
-- 通用时序数据表
CREATE TABLE IF NOT EXISTS time_series_cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    indicator TEXT NOT NULL,        -- 指标名称 (hsgt_north, m2, gdp...)
    date TEXT NOT NULL,              -- 日期 YYYY-MM-DD or YYYY-MM-DD HH:MM:SS
    frequency TEXT DEFAULT 'daily',  -- 频率 (daily, weekly, monthly, minute, quarterly, yearly)
    value_numeric REAL,              -- 数值型数据
    value_text TEXT,                 -- 文本型数据（JSON）
    metadata TEXT,                   -- 元数据（JSON）
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(indicator, date, frequency)
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_indicator_date ON time_series_cache(indicator, date);
CREATE INDEX IF NOT EXISTS idx_indicator_freq ON time_series_cache(indicator, frequency);
CREATE INDEX IF NOT EXISTS idx_date ON time_series_cache(date);

-- 元数据表（记录最后更新时间）
CREATE TABLE IF NOT EXISTS cache_metadata (
    indicator TEXT PRIMARY KEY,
    last_update TEXT,
    data_count INTEGER,
    earliest_date TEXT,
    latest_date TEXT,
    description TEXT,
    source TEXT,
    frequency TEXT DEFAULT 'daily'
);
"""

class CacheDB:
    """统一缓存数据库管理类"""
    
    def __init__(self, db_path: str = None):
        self.db_path = db_path or str(DB_PATH)
        self._init_db()
    
    def _init_db(self):
        """初始化数据库"""
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript(SCHEMA)
            conn.commit()
    
    def save_time_series(
        self, 
        indicator: str, 
        data: Union[pd.DataFrame, List[Dict]], 
        frequency: str = 'daily',
        date_column: str = 'date',
        value_column: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> int:
        """
        保存时序数据
        
        Args:
            indicator: 指标名称
            data: DataFrame 或 字典列表
            frequency: 数据频率
            date_column: 日期列名
            value_column: 数值列名（如果是单列数据）
            metadata: 额外元数据
            
        Returns:
            int: 插入/更新的记录数
        """
        if isinstance(data, pd.DataFrame):
            records = data.to_dict('records')
        else:
            records = data
        
        count = 0
        sql = """
        INSERT OR REPLACE INTO time_series_cache 
        (indicator, date, frequency, value_numeric, value_text, metadata, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        
        with sqlite3.connect(self.db_path) as conn:
            for record in records:
                # 提取日期
                record_date = record.get(date_column)
                if isinstance(record_date, (datetime, pd.Timestamp)):
                    record_date = record_date.strftime('%Y-%m-%d')
                elif not isinstance(record_date, str):
                    record_date = str(record_date)
                
                # 提取数值
                if value_column and value_column in record:
                    value_numeric = float(record[value_column]) if record[value_column] is not None else None
                    value_text = None
                else:
                    # 存储整行数据为 JSON
                    value_numeric = None
                    # Remove date to avoid duplication
                    record_copy = {k: v for k, v in record.items() if k != date_column}
                    value_text = json.dumps(record_copy, ensure_ascii=False)
                
                # 元数据
                meta_json = json.dumps(metadata, ensure_ascii=False) if metadata else None
                
                conn.execute(sql, (
                    indicator,
                    record_date,
                    frequency,
                    value_numeric,
                    value_text,
                    meta_json,
                    datetime.now().isoformat()
                ))
                count += 1
            
            conn.commit()
            
            # 更新元数据
            self._update_metadata(conn, indicator, frequency)
        
        print(f"[CacheDB] Saved {count} records for '{indicator}'")
        return count
    
    def load_time_series(
        self,
        indicator: str,
        start_date: Optional[Union[str, date]] = None,
        end_date: Optional[Union[str, date]] = None,
        frequency: str = 'daily',
        as_dataframe: bool = True
    ) -> Union[pd.DataFrame, List[Dict]]:
        """
        加载时序数据
        
        Args:
            indicator: 指标名称
            start_date: 开始日期
            end_date: 结束日期
            frequency: 数据频率
            as_dataframe: 是否返回 DataFrame
            
        Returns:
            DataFrame 或 字典列表
        """
        sql = "SELECT * FROM time_series_cache WHERE indicator = ? AND frequency = ?"
        params = [indicator, frequency]
        
        if start_date:
            sql += " AND date >= ?"
            params.append(str(start_date) if not isinstance(start_date, str) else start_date)
        
        if end_date:
            sql += " AND date <= ?"
            params.append(str(end_date) if not isinstance(end_date, str) else end_date)
        
        sql += " ORDER BY date"
        
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(sql, params)
            rows = cursor.fetchall()
        
        if not rows:
            return pd.DataFrame() if as_dataframe else []
        
        # 解析数据
        records = []
        for row in rows:
            record = {'date': row['date']}
            
            if row['value_numeric'] is not None:
                record['value'] = row['value_numeric']
            
            if row['value_text']:
                # JSON 解析
                try:
                    text_data = json.loads(row['value_text'])
                    record.update(text_data)
                except:
                    record['value_text'] = row['value_text']
            
            records.append(record)
        
        if as_dataframe:
            df = pd.DataFrame(records)
            df['date'] = pd.to_datetime(df['date'])
            return df
        return records
    
    def get_latest_date(self, indicator: str, frequency: str = 'daily') -> Optional[str]:
        """获取指标最新日期"""
        sql = "SELECT MAX(date) as max_date FROM time_series_cache WHERE indicator = ? AND frequency = ?"
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(sql, (indicator, frequency))
            result = cursor.fetchone()
            return result[0] if result and result[0] else None
    
    def get_earliest_date(self, indicator: str, frequency: str = 'daily') -> Optional[str]:
        """获取指标最早日期"""
        sql = "SELECT MIN(date) as min_date FROM time_series_cache WHERE indicator = ? AND frequency = ?"
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(sql, (indicator, frequency))
            result = cursor.fetchone()
            return result[0] if result and result[0] else None
    
    def get_data_count(self, indicator: str, frequency: str = 'daily') -> int:
        """获取数据记录数"""
        sql = "SELECT COUNT(*) FROM time_series_cache WHERE indicator = ? AND frequency = ?"
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(sql, (indicator, frequency))
            return cursor.fetchone()[0]
    
    def _update_metadata(self, conn: sqlite3.Connection, indicator: str, frequency: str):
        """更新元数据表"""
        # 获取统计信息
        stats_sql = """
        SELECT 
            COUNT(*) as count,
            MIN(date) as earliest,
            MAX(date) as latest
        FROM time_series_cache
        WHERE indicator = ? AND frequency = ?
        """
        cursor = conn.execute(stats_sql, (indicator, frequency))
        stats = cursor.fetchone()
        
        # 更新或插入元数据
        meta_sql = """
        INSERT OR REPLACE INTO cache_metadata 
        (indicator, last_update, data_count, earliest_date, latest_date, frequency)
        VALUES (?, ?, ?, ?, ?, ?)
        """
        conn.execute(meta_sql, (
            indicator,
            datetime.now().isoformat(),
            stats[0],
            stats[1],
            stats[2],
            frequency
        ))
    
    def list_indicators(self) -> List[Dict]:
        """列出所有指标"""
        sql = "SELECT * FROM cache_metadata ORDER BY last_update DESC"
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(sql)
            return [dict(row) for row in cursor.fetchall()]
    
    def delete_indicator(self, indicator: str) -> int:
        """删除指标所有数据"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("DELETE FROM time_series_cache WHERE indicator = ?", (indicator,))
            deleted = cursor.rowcount
            conn.execute("DELETE FROM cache_metadata WHERE indicator = ?", (indicator,))
            conn.commit()
        print(f"[CacheDB] Deleted {deleted} records for '{indicator}'")
        return deleted
    
    def get_stats(self) -> Dict:
        """获取数据库统计信息"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            
            # 总体统计
            cursor = conn.execute("""
                SELECT 
                    COUNT(DISTINCT indicator) as total_indicators,
                    COUNT(*) as total_records,
                    MIN(date) as earliest_date,
                    MAX(date) as latest_date
                FROM time_series_cache
            """)
            stats = dict(cursor.fetchone())
            
            # 按指标统计
            cursor = conn.execute("SELECT * FROM cache_metadata")
            stats['indicators'] = [dict(row) for row in cursor.fetchall()]
            
            return stats

# CLI Test
if __name__ == "__main__":
    print("=" * 50)
    print("Unified Cache Database Test")
    print("=" * 50)
    
    db = CacheDB()
    
    # Test data
    test_df = pd.DataFrame({
        'date': pd.date_range('2026-01-01', periods=10, freq='D'),
        'north_flow': [100.5, 200.3, -50.2, 150.0, 300.1, -20.5, 80.7, 120.3, 90.2, 110.5],
        'south_flow': [50.2, 80.1, -30.5, 70.3, 150.2, -10.3, 40.1, 60.5, 50.3, 70.1]
    })
    
    print("\n--- Saving test data ---")
    db.save_time_series('hsgt_test', test_df, frequency='daily')
    
    print("\n--- Loading data ---")
    loaded = db.load_time_series('hsgt_test', start_date='2026-01-05')
    print(loaded)
    
    print("\n--- Metadata ---")
    print(f"Latest date: {db.get_latest_date('hsgt_test')}")
    print(f"Count: {db.get_data_count('hsgt_test')}")
    
    print("\n--- Database Stats ---")
    stats = db.get_stats()
    print(f"Total indicators: {stats['total_indicators']}")
    print(f"Total records: {stats['total_records']}")
