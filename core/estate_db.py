"""
Estate Database Manager
房产数据库管理器 - 使用 SQLite 存储每日成交数据

Features:
1. 每日数据存储
2. 按周/季度/年度汇总
3. 数据查询与导出
"""
import sqlite3
import os
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any

# Database path
DATA_DIR = Path(__file__).parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)
DB_PATH = DATA_DIR / "estate.db"

# SQL Schema
SCHEMA = """
-- 每日成交数据表
CREATE TABLE IF NOT EXISTS daily_transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,           -- 日期 YYYY-MM-DD
    city TEXT NOT NULL,           -- 城市 (成都/西安)
    region TEXT NOT NULL,         -- 区域 (全市/中心城区/郊区新城)
    total_area REAL DEFAULT 0,    -- 总成交面积 (㎡)
    resident_units INTEGER DEFAULT 0,  -- 住宅成交套数
    resident_area REAL DEFAULT 0,      -- 住宅成交面积 (㎡)
    non_resident_area REAL DEFAULT 0,  -- 非住宅面积 (㎡)
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(date, city, region)   -- 防止重复插入
);

-- 按周汇总视图
CREATE VIEW IF NOT EXISTS weekly_summary AS
SELECT 
    city,
    region,
    strftime('%Y-W%W', date) as week,
    SUM(total_area) as total_area,
    SUM(resident_units) as resident_units,
    SUM(resident_area) as resident_area,
    COUNT(*) as days_recorded
FROM daily_transactions
GROUP BY city, region, strftime('%Y-W%W', date);

-- 按月汇总视图
CREATE VIEW IF NOT EXISTS monthly_summary AS
SELECT 
    city,
    region,
    strftime('%Y-%m', date) as month,
    SUM(total_area) as total_area,
    SUM(resident_units) as resident_units,
    SUM(resident_area) as resident_area,
    COUNT(*) as days_recorded
FROM daily_transactions
GROUP BY city, region, strftime('%Y-%m', date);

-- 按季度汇总视图
CREATE VIEW IF NOT EXISTS quarterly_summary AS
SELECT 
    city,
    region,
    strftime('%Y', date) || '-Q' || ((CAST(strftime('%m', date) AS INTEGER) - 1) / 3 + 1) as quarter,
    SUM(total_area) as total_area,
    SUM(resident_units) as resident_units,
    SUM(resident_area) as resident_area,
    COUNT(*) as days_recorded
FROM daily_transactions
GROUP BY city, region, strftime('%Y', date), ((CAST(strftime('%m', date) AS INTEGER) - 1) / 3 + 1);

-- 按年汇总视图
CREATE VIEW IF NOT EXISTS yearly_summary AS
SELECT 
    city,
    region,
    strftime('%Y', date) as year,
    SUM(total_area) as total_area,
    SUM(resident_units) as resident_units,
    SUM(resident_area) as resident_area,
    COUNT(*) as days_recorded
FROM daily_transactions
GROUP BY city, region, strftime('%Y', date);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_date ON daily_transactions(date);
CREATE INDEX IF NOT EXISTS idx_city ON daily_transactions(city);
CREATE INDEX IF NOT EXISTS idx_city_date ON daily_transactions(city, date);
"""

class EstateDB:
    """房产数据库管理类"""
    
    def __init__(self, db_path: str = None):
        self.db_path = db_path or str(DB_PATH)
        self._init_db()
    
    def _init_db(self):
        """初始化数据库"""
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript(SCHEMA)
            conn.commit()
    
    def insert_daily(self, data: Dict[str, Any]) -> bool:
        """
        插入每日数据
        
        Args:
            data: {
                'date': '2026-02-09',
                'city': '成都',
                'region': '全市',
                'total_area': 1939.93,
                'resident_units': 18,
                'resident_area': 1939.93,
            }
            
        Returns:
            bool: 成功/失败
        """
        sql = """
        INSERT OR REPLACE INTO daily_transactions 
        (date, city, region, total_area, resident_units, resident_area, non_resident_area)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(sql, (
                    data.get('date', date.today().isoformat()),
                    data.get('city', ''),
                    data.get('region', ''),
                    data.get('total_area', 0),
                    data.get('resident_units', 0),
                    data.get('resident_area', 0),
                    data.get('non_resident_area', 0),
                ))
                conn.commit()
            return True
        except Exception as e:
            print(f"[EstateDB] Insert error: {e}")
            return False
    
    def insert_batch(self, data_list: List[Dict]) -> int:
        """批量插入"""
        success = 0
        for data in data_list:
            if self.insert_daily(data):
                success += 1
        return success
    
    def get_daily(self, city: str, d: Optional[date] = None) -> List[Dict]:
        """获取某日数据"""
        d = d or date.today()
        sql = "SELECT * FROM daily_transactions WHERE city = ? AND date = ?"
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(sql, (city, d.isoformat()))
            return [dict(row) for row in cursor.fetchall()]
    
    def get_weekly(self, city: str, week: Optional[str] = None) -> List[Dict]:
        """获取周汇总"""
        if not week:
            week = date.today().strftime('%Y-W%W')
        sql = "SELECT * FROM weekly_summary WHERE city = ? AND week = ?"
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(sql, (city, week))
            return [dict(row) for row in cursor.fetchall()]
    
    def get_monthly(self, city: str, month: Optional[str] = None) -> List[Dict]:
        """获取月汇总"""
        if not month:
            month = date.today().strftime('%Y-%m')
        sql = "SELECT * FROM monthly_summary WHERE city = ? AND month = ?"
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(sql, (city, month))
            return [dict(row) for row in cursor.fetchall()]
    
    def get_quarterly(self, city: str, quarter: Optional[str] = None) -> List[Dict]:
        """获取季度汇总"""
        if not quarter:
            m = date.today().month
            q = (m - 1) // 3 + 1
            quarter = f"{date.today().year}-Q{q}"
        sql = "SELECT * FROM quarterly_summary WHERE city = ? AND quarter = ?"
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(sql, (city, quarter))
            return [dict(row) for row in cursor.fetchall()]
    
    def get_yearly(self, city: str, year: Optional[str] = None) -> List[Dict]:
        """获取年度汇总"""
        if not year:
            year = str(date.today().year)
        sql = "SELECT * FROM yearly_summary WHERE city = ? AND year = ?"
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(sql, (city, year))
            return [dict(row) for row in cursor.fetchall()]
    
    def get_range(self, city: str, start: date, end: date) -> List[Dict]:
        """获取日期范围内的数据"""
        sql = """
        SELECT * FROM daily_transactions 
        WHERE city = ? AND date BETWEEN ? AND ?
        ORDER BY date
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(sql, (city, start.isoformat(), end.isoformat()))
            return [dict(row) for row in cursor.fetchall()]
    
    def export_csv(self, output_path: str, city: Optional[str] = None):
        """导出为 CSV"""
        import csv
        sql = "SELECT * FROM daily_transactions"
        params = ()
        if city:
            sql += " WHERE city = ?"
            params = (city,)
        sql += " ORDER BY date DESC"
        
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(sql, params)
            rows = cursor.fetchall()
        
        if rows:
            with open(output_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=rows[0].keys())
                writer.writeheader()
                writer.writerows([dict(row) for row in rows])
            print(f"[EstateDB] Exported {len(rows)} rows to {output_path}")
    
    def get_stats(self) -> Dict:
        """获取数据库统计"""
        sql = """
        SELECT 
            COUNT(*) as total_records,
            COUNT(DISTINCT date) as unique_dates,
            COUNT(DISTINCT city) as cities,
            MIN(date) as earliest_date,
            MAX(date) as latest_date
        FROM daily_transactions
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(sql)
            return dict(cursor.fetchone())

# CLI Test
if __name__ == "__main__":
    print("=" * 50)
    print("Estate Database Manager Test")
    print("=" * 50)
    
    db = EstateDB()
    
    # Insert test data
    test_data = [
        {'date': '2026-02-09', 'city': '成都', 'region': '全市', 'total_area': 1939.93, 'resident_units': 18, 'resident_area': 1939.93},
        {'date': '2026-02-09', 'city': '成都', 'region': '郊区新城', 'total_area': 1939.93, 'resident_units': 18, 'resident_area': 1939.93},
    ]
    
    print("\n--- Inserting test data ---")
    inserted = db.insert_batch(test_data)
    print(f"Inserted: {inserted}")
    
    print("\n--- Daily Data ---")
    print(db.get_daily('成都'))
    
    print("\n--- Stats ---")
    print(db.get_stats())
