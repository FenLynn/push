# Push Project (Systematic Edition)

A unified TTRSS + Push Notification system running on Docker.

## 📂 Directory Structure

- `core/`, `sources/`, `channels/`: Python application code.
- `config/`: TTRSS and other configurations.
- `data/`: 
  - `postgres/`: (Currently managed by Docker Volume `db_data`)
  - `push.db`: Local application cache.
- `scripts/`: System management scripts.
  - `backup_webdav.sh`: **Encrypt & Backup** (to WebDAV).
  - `restore_webdav.sh`: **Restore** (from WebDAV).
  - `docker_entrypoint.sh`: Container entrypoint.
- `.env`: Environment variables (Secrets).
- `docker-compose.yml`: Service definition.

## 🚀 Quick Start

### 1. Start Services
```bash
docker compose up -d
```

### 2. Manual Run
```bash
docker exec -it push-service python main.py run all
```

## 🛡️ Backup & Restore (WebDAV)

### Backup
Auto-encrypts and uploads to Nutstore. (Configure `WEBDAV_*` and `BACKUP_ENV` in `.env`)
```bash
./scripts/backup_webdav.sh
```

### Restore
Interactive restoration from Test or Prod environment.
```bash
./scripts/restore_webdav.sh
```

## 🧹 Maintenance
Files in `../push.bak` are legacy backups/junk and can be deleted after verification.

## ☁️ Cloud Native Architecture
- **Backup**: Automated to **Cloudflare R2** (`scripts/backup_r2.py`).
- **CI/CD**: GitHub Actions auto-builds Docker images to GHCR.
- **Stateless**: `scripts/cleanup.py` enforces 7-day retention for output/backups.

## ☁️ Cloud Native Architecture
- **Backup**: Automated to **Cloudflare R2** (`scripts/backup_r2.py`).
- **CI/CD**: GitHub Actions auto-builds Docker images to GHCR.
- **Stateless**: `scripts/cleanup.py` enforces 7-day retention for output/backups.
