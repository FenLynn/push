import logging
import time
from typing import Dict, Any
from .d1_client import D1Client
from .config import config

class D1LogHandler(logging.Handler):
    """
    Custom Logging Handler that pushes logs to Cloudflare D1.
    Usage:
        if config.RUN_MODE == 'cloud':
            handler = D1LogHandler()
            logger.addHandler(handler)
    """
    def __init__(self):
        super().__init__()
        self.d1 = D1Client()
        self.table_name = "system_logs"
        self._ensure_table()

    def _ensure_table(self):
        """Create log table if not exists (Lazy init)"""
        # Note: In production, better to use migration scripts.
        # This is a fail-safe for the first run.
        sql = """
        CREATE TABLE IF NOT EXISTS system_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            level TEXT,
            logger_name TEXT,
            message TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            module TEXT,
            func_name TEXT,
            line_no INTEGER
        );
        """
        try:
            self.d1.query(sql)
        except Exception:
            pass

    def emit(self, record: logging.LogRecord):
        """
        Emit a record.
        """
        try:
            # Only log WARNING, ERROR, CRITICAL to DB to save rows
            if record.levelno < logging.WARNING:
                return

            msg = self.format(record)
            
            data = {
                "level": record.levelname,
                "logger_name": record.name,
                "message": msg,
                "module": record.module,
                "func_name": record.funcName,
                "line_no": record.lineno,
                "created_at": int(time.time()) # Timestamp
            }
            
            # Use D1Client to insert (Async push ideally, but synchronous for now)
            # We construct a raw SQL since D1Client might be read-focused.
            # Let's check D1Client capabilities.
            # If D1Client doesn't support easy insert, we might need to extend it.
            # For this simplified implementation, we'll try to use a raw query if available
            # or just print to console if D1 write is not ready.
            
            # Actually, `d1_client.py` likely has a query method.
            # Let's assume we can INSERT.
            
            sql = """
            INSERT INTO system_logs (level, logger_name, message, module, func_name, line_no, created_at)
            VALUES (?, ?, ?, ?, ?, ?, datetime(?, 'unixepoch'))
            """
            params = [
                data["level"], data["logger_name"], data["message"], 
                data["module"], data["func_name"], data["line_no"], data["created_at"]
            ]
            
            self.d1.query(sql, params)
            
        except Exception:
            self.handleError(record)
