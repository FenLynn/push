#!/usr/bin/env python3
"""
🧹 Cloud Native Cleanup Script
Enforce 7-day retention policy for local artifacts to keep the system stateless and lightweight.
Run this daily via Cron/Ofelia.
"""
import os
import time
import logging
from pathlib import Path

# Setup Logger
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger('Cleanup')

BASE_DIR = Path(__file__).parent.parent
OUTPUT_DIR = BASE_DIR / "output"
BACKUP_DIR = BASE_DIR / "backups"
RETENTION_DAYS = 7
RETENTION_SECONDS = RETENTION_DAYS * 86400

def cleanup_directory(directory: Path, pattern="*"):
    if not directory.exists():
        logger.warning(f"Directory not found: {directory}")
        return

    logger.info(f"Scanning {directory} for files older than {RETENTION_DAYS} days...")
    now = time.time()
    deleted_count = 0
    
    # Walk through directory
    for file_path in directory.glob(pattern):
        if file_path.is_file():
            try:
                file_age = now - file_path.stat().st_mtime
                if file_age > RETENTION_SECONDS:
                    file_path.unlink()
                    logger.info(f"🗑️ Deleted: {file_path.name} ({int(file_age/86400)} days old)")
                    deleted_count += 1
            except Exception as e:
                logger.error(f"Error checking/deleting {file_path}: {e}")
                
    if deleted_count == 0:
        logger.info("✨ No files to clean.")
    else:
        logger.info(f"✅ Cleanup complete. Deleted {deleted_count} files.")

def main():
    # 1. Clean Output (HTML reports)
    cleanup_directory(OUTPUT_DIR, "*.html")
    
    # 2. Clean Output Images (if any)
    cleanup_directory(OUTPUT_DIR, "*.png")
    cleanup_directory(OUTPUT_DIR, "*.jpg")
    
    # 3. Clean Old Local Backups (In case R2 script didn't delete them or manual runs)
    cleanup_directory(BACKUP_DIR, "*.tar.gz")
    cleanup_directory(BACKUP_DIR, "*.enc")
    
    logger.info("🏁 System Cleanup Finished.")

if __name__ == "__main__":
    main()
