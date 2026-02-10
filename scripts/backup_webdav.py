"""
WebDAV Backup Script
WebDAV 备份脚本 - 定时备份数据库和配置文件

功能：
1. 备份所有 SQLite 数据库
2. 备份配置文件 (.env, OPML)
3. 压缩并上传到 WebDAV
4. 保留最近 30 天备份
"""
import os
import sys
import tarfile
import shutil
from datetime import datetime, timedelta
from pathlib import Path

try:
    from webdav3.client import Client
    WEBDAV_AVAILABLE = True
except ImportError:
    WEBDAV_AVAILABLE = False
    print("Warning: webdavclient3 not installed. Run: pip install webdavclient3")

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.env import get_env_config

def get_webdav_client():
    """获取 WebDAV 客户端"""
    if not WEBDAV_AVAILABLE:
        raise ImportError("webdavclient3 not installed")
    
    env_config = get_env_config()
    
    # 从环境变量读取 WebDAV 配置
    options = {
        'webdav_hostname': env_config.get('backup', 'webdav_hostname', fallback=''),
        'webdav_login': env_config.get('backup', 'webdav_login', fallback=''),
        'webdav_password': env_config.get('backup', 'webdav_password', fallback=''),
    }
    
    if not options['webdav_hostname']:
        raise ValueError("WebDAV hostname not configured in .env")
    
    return Client(options)

def create_backup_archive(output_path: str, base_dir: Path) -> str:
    """
    创建备份压缩包
    
    Args:
        output_path: 输出文件路径
        base_dir: 项目根目录
        
    Returns:
        str: 压缩包路径
    """
    print(f"[Backup] Creating archive: {output_path}")
    
    with tarfile.open(output_path, "w:gz") as tar:
        # 备份数据库
        data_dir = base_dir / "data"
        if data_dir.exists():
            for db_file in data_dir.glob("*.db"):
                arcname = f"data/{db_file.name}"
                tar.add(db_file, arcname=arcname)
                print(f"  + {arcname}")
        
        # 备份 .env
        env_file = base_dir / ".env"
        if env_file.exists():
            tar.add(env_file, arcname=".env")
            print(f"  + .env")
        
        # 备份 OPML
        opml_dir = base_dir / "config"
        if opml_dir.exists():
            for opml in opml_dir.glob("*.opml"):
                arcname = f"config/{opml.name}"
                tar.add(opml, arcname=arcname)
                print(f"  + {arcname}")
        
        # 备份最新图表（可选，大小可能较大）
        # output_dir = base_dir / "output" / "finance"
        # if output_dir.exists():
        #     for png in output_dir.glob("*.png"):
        #         arcname = f"output/finance/{png.name}"
        #         tar.add(png, arcname=arcname)
    
    file_size = Path(output_path).stat().st_size / (1024 * 1024)  # MB
    print(f"[Backup] Archive created: {file_size:.2f} MB")
    
    return output_path

def upload_to_webdav(local_path: str, remote_dir: str = "/push-backup/"):
    """
    上传到 WebDAV
    
    Args:
        local_path: 本地文件路径
        remote_dir: 远程目录
    """
    try:
        client = get_webdav_client()
        
        # 确保远程目录存在
        if not client.check(remote_dir):
            client.mkdir(remote_dir)
            print(f"[WebDAV] Created directory: {remote_dir}")
        
        # 上传文件
        remote_path = remote_dir + Path(local_path).name
        print(f"[WebDAV] Uploading to: {remote_path}")
        
        client.upload_sync(remote_path=remote_path, local_path=local_path)
        print(f"[WebDAV] Upload successful!")
        
        return True
    
    except Exception as e:
        print(f"[WebDAV] Upload failed: {e}")
        return False

def cleanup_old_backups(remote_dir: str = "/push-backup/", keep_days: int = 30):
    """
    清理旧备份
    
    Args:
        remote_dir: 远程目录
        keep_days: 保留天数
    """
    try:
        client = get_webdav_client()
        
        if not client.check(remote_dir):
            return
        
        # 列出所有文件
        files = client.list(remote_dir)
        
        cutoff_date = datetime.now() - timedelta(days=keep_days)
        
        for file in files:
            if not file.endswith('.tar.gz'):
                continue
            
            # 从文件名提取日期 (push-backup-YYYY-MM-DD.tar.gz)
            try:
                date_str = file.split('-')[-1].replace('.tar.gz', '')
                file_date = datetime.strptime(date_str, '%Y-%m-%d')
                
                if file_date < cutoff_date:
                    remote_path = remote_dir + file
                    client.clean(remote_path)
                    print(f"[WebDAV] Deleted old backup: {file}")
            except:
                pass
    
    except Exception as e:
        print(f"[WebDAV] Cleanup failed: {e}")

def main():
    print("=" * 60)
    print("Push Project WebDAV Backup")
    print("=" * 60)
    
    # 项目根目录
    base_dir = Path(__file__).parent.parent
    
    # 临时目录
    tmp_dir = Path("/tmp/push-backup")
    tmp_dir.mkdir(exist_ok=True)
    
    # 备份文件名
    today = datetime.now().strftime('%Y-%m-%d')
    archive_name = f"push-backup-{today}.tar.gz"
    archive_path = tmp_dir / archive_name
    
    try:
        # 1. 创建压缩包
        create_backup_archive(str(archive_path), base_dir)
        
        # 2. 上传到 WebDAV
        if WEBDAV_AVAILABLE:
            if upload_to_webdav(str(archive_path)):
                print("[Backup] ✅ Backup completed successfully")
                
                # 3. 清理旧备份
                cleanup_old_backups()
            else:
                print("[Backup] ❌ Upload failed, but local backup exists at:", archive_path)
        else:
            print(f"[Backup] WebDAV not available. Local backup saved to: {archive_path}")
    
    except Exception as e:
        print(f"[Backup] Error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # 可选：删除本地临时文件
        # if archive_path.exists():
        #     archive_path.unlink()
        pass

if __name__ == "__main__":
    main()
