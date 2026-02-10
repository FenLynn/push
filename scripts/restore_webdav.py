"""
WebDAV Restore Script
WebDAV 恢复脚本 - 从 WebDAV 恢复备份

用法：
    python scripts/restore_webdav.py                    # 恢复最新备份
    python scripts/restore_webdav.py --date 2026-02-08  # 恢复指定日期
    python scripts/restore_webdav.py --list             # 列出所有备份
"""
import os
import sys
import argparse
import tarfile
from datetime import datetime
from pathlib import Path

try:
    from webdav3.client import Client
    WEBDAV_AVAILABLE = True
except ImportError:
    WEBDAV_AVAILABLE = False
    print("Error: webdavclient3 not installed. Run: pip install webdavclient3")
    sys.exit(1)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.env import get_env_config

def get_webdav_client():
    """获取 WebDAV 客户端"""
    env_config = get_env_config()
    
    options = {
        'webdav_hostname': env_config.get('backup', 'webdav_hostname', fallback=''),
        'webdav_login': env_config.get('backup', 'webdav_login', fallback=''),
        'webdav_password': env_config.get('backup', 'webdav_password', fallback=''),
    }
    
    if not options['webdav_hostname']:
        raise ValueError("WebDAV hostname not configured in .env")
    
    return Client(options)

def list_backups(remote_dir: str = "/push-backup/") -> list:
    """列出所有备份"""
    client = get_webdav_client()
    
    if not client.check(remote_dir):
        print(f"[Restore] Remote directory not found: {remote_dir}")
        return []
    
    files = client.list(remote_dir)
    backups = [f for f in files if f.endswith('.tar.gz')]
    backups.sort(reverse=True)  # 最新在前
    
    return backups

def download_backup(backup_name: str, local_path: str, remote_dir: str = "/push-backup/"):
    """下载备份"""
    client = get_webdav_client()
    
    remote_path = remote_dir + backup_name
    
    if not client.check(remote_path):
        print(f"[Restore] Backup not found: {remote_path}")
        return False
    
    print(f"[Restore] Downloading: {backup_name}")
    client.download_sync(remote_path=remote_path, local_path=local_path)
    print(f"[Restore] Downloaded to: {local_path}")
    
    return True

def extract_backup(archive_path: str, target_dir: Path):
    """解压备份"""
    print(f"[Restore] Extracting: {archive_path}")
    
    with tarfile.open(archive_path, "r:gz") as tar:
        # 安全检查（防止路径穿越）
        for member in tar.getmembers():
            if member.name.startswith('/') or '..' in member.name:
                print(f"[Restore] Skipping unsafe path: {member.name}")
                continue
            
            # 解压
            tar.extract(member, target_dir)
            print(f"  + {member.name}")
    
    print(f"[Restore] Extraction complete!")

def main():
    parser = argparse.ArgumentParser(description="Restore from WebDAV backup")
    parser.add_argument('--date', help='Backup date (YYYY-MM-DD)')
    parser.add_argument('--list', action='store_true', help='List all backups')
    parser.add_argument('--force', action='store_true', help='Overwrite existing files')
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("Push Project WebDAV Restore")
    print("=" * 60)
    
    try:
        # 列出备份
        if args.list:
            backups = list_backups()
            if backups:
                print("\nAvailable backups:")
                for b in backups:
                    print(f"  - {b}")
            else:
                print("No backups found.")
            return
        
        # 确定备份文件
        if args.date:
            backup_name = f"push-backup-{args.date}.tar.gz"
        else:
            # 使用最新备份
            backups = list_backups()
            if not backups:
                print("[Restore] No backups found!")
                return
            backup_name = backups[0]
            print(f"[Restore] Using latest backup: {backup_name}")
        
        # 下载
        tmp_dir = Path("/tmp/push-restore")
        tmp_dir.mkdir(exist_ok=True)
        local_archive = tmp_dir / backup_name
        
        if not download_backup(backup_name, str(local_archive)):
            return
        
        # 解压
        base_dir = Path(__file__).parent.parent
        
        if not args.force:
            # 检查是否会覆盖现有文件
            print("\n[Restore] Warning: This will overwrite existing files!")
            response = input("Continue? (yes/no): ")
            if response.lower() != 'yes':
                print("[Restore] Cancelled.")
                return
        
        extract_backup(str(local_archive), base_dir)
        
        print("\n[Restore] ✅ Restore completed successfully!")
        print("\nRestored files:")
        print("  - data/*.db")
        print("  - .env")
        print("  - config/*.opml")
    
    except Exception as e:
        print(f"[Restore] Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
