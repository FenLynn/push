#!/usr/bin/env python3
"""
🚀 Cloudflare R2 Backup Script
Backs up TTRSS data and configuration to Cloudflare R2 Storage.
"""
import os
import sys
import boto3
import subprocess
import logging
from datetime import datetime
from botocore.exceptions import ClientError

# Setup Logger
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger('R2Backup')

# Load .env (Simple loader to avoid python-dotenv dependency if not present)
def load_env():
    env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
    if os.path.exists(env_path):
        with open(env_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    k, v = line.split('=', 1)
                    if k.strip() not in os.environ:
                        os.environ[k.strip()] = v.strip()

def run_command(cmd):
    """Run shell command"""
    try:
        subprocess.check_call(cmd, shell=True)
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Command failed: {cmd}\n{e}")
        return False

def main():
    load_env()
    
    # Config
    ACCOUNT_ID = os.getenv('R2_ACCOUNT_ID')
    ACCESS_KEY = os.getenv('R2_ACCESS_KEY')
    SECRET_KEY = os.getenv('R2_SECRET_KEY')
    BUCKET_NAME = os.getenv('R2_BUCKET_NAME', 'push-service')
    ENDPOINT_URL = os.getenv('R2_ENDPOINT')
    BACKUP_ENV = os.getenv('BACKUP_ENV', 'test')
    BACKUP_PASS = os.getenv('BACKUP_PASSWORD')
    
    if not all([ACCOUNT_ID, ACCESS_KEY, SECRET_KEY, ENDPOINT_URL]):
        logger.error("❌ Missing R2 credentials in .env")
        sys.exit(1)

    # Paths
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    BACKUP_DIR = os.path.join(BASE_DIR, 'backups')
    os.makedirs(BACKUP_DIR, exist_ok=True)
    
    TIME_STR = datetime.now().strftime('%Y%m%d_%H%M%S')
    ARCHIVE_NAME = f"push_backup_{BACKUP_ENV}_{TIME_STR}.tar.gz"
    ARCHIVE_PATH = os.path.join(BACKUP_DIR, ARCHIVE_NAME)
    
    # 1. Dump Database
    logger.info("💾 Dumping Database...")
    DB_DUMP = os.path.join(BACKUP_DIR, "ttrss_db.sql")
    # Check if we are in Docker or Host
    # Assuming Host script calling Docker
    cmd_dump = f"sudo docker exec push-postgres pg_dump -U ttrss ttrss > {DB_DUMP}"
    if not run_command(cmd_dump):
        logger.error("❌ Database dump failed. Is container running?")
        sys.exit(1)
        
    # 2. Create Tarball
    logger.info("📦 Creating Archive...")
    
    # Build file list
    files_to_backup = ["backups/ttrss_db.sql", ".env", ".private", "config", "data/push.db"]
    if os.path.exists(os.path.join(BASE_DIR, "data/task_scheduler.db")):
        files_to_backup.append("data/task_scheduler.db")
        
    file_list_str = " ".join(files_to_backup)

    cmd_tar = (
        f"cd {BASE_DIR} && "
        f"tar --exclude='backups/*.tar.gz*' --exclude='__pycache__' "
        f"-czf {ARCHIVE_PATH} {file_list_str}"
    )
    if not run_command(cmd_tar):
        sys.exit(1)
        
    # Cleanup Dump
    if os.path.exists(DB_DUMP):
        os.remove(DB_DUMP)
        
    # 3. Encrypt
    FINAL_PATH = ARCHIVE_PATH
    REMOTE_KEY = f"{BACKUP_ENV}/{ARCHIVE_NAME}"
    
    if BACKUP_PASS:
        logger.info("🔒 Encrypting...")
        ENC_PATH = f"{ARCHIVE_PATH}.enc"
        cmd_enc = (
            f"openssl enc -aes-256-cbc -salt -pbkdf2 -iter 100000 "
            f"-in {ARCHIVE_PATH} -out {ENC_PATH} -k '{BACKUP_PASS}'"
        )
        if run_command(cmd_enc):
            os.remove(ARCHIVE_PATH)
            FINAL_PATH = ENC_PATH
            REMOTE_KEY = f"{BACKUP_ENV}/{ARCHIVE_NAME}.enc"
        else:
            logger.error("❌ Encryption failed")
            sys.exit(1)
            
    # 4. Upload to R2
    logger.info(f"☁️ Uploading to R2: {BUCKET_NAME}/{REMOTE_KEY}")
    
    s3 = boto3.client(
        's3',
        endpoint_url=ENDPOINT_URL,
        aws_access_key_id=ACCESS_KEY,
        aws_secret_access_key=SECRET_KEY
    )
    
    try:
        s3.upload_file(FINAL_PATH, BUCKET_NAME, REMOTE_KEY)
        logger.info("✅ Upload Successful!")
        
        # List last 5 files to confirm
        # logger.info("📋 Recent backups:")
        # response = s3.list_objects_v2(Bucket=BUCKET_NAME, Prefix=f"{BACKUP_ENV}/")
        # if 'Contents' in response:
        #     for obj in sorted(response['Contents'], key=lambda x: x['LastModified'], reverse=True)[:5]:
        #         print(f"  - {obj['Key']} ({obj['Size']/1024/1024:.2f} MB)")
                
    except ClientError as e:
        logger.error(f"❌ Upload failed: {e}")
        sys.exit(1)
    finally:
        # Cleanup local
        if os.path.exists(FINAL_PATH):
            os.remove(FINAL_PATH)
            logger.info(f"🧹 Cleaned up local file: {FINAL_PATH}")

if __name__ == "__main__":
    main()
