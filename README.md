# Push Project (Systematic Edition)

A unified TTRSS + Push Notification system running on Docker.

## 📂 Directory Structure

- `core/`, `sources/`, `channels/`: Python application code.
- `config/`: TTRSS and other configurations.
- `data/`: 
  - `postgres/`: (Currently managed by Docker Volume `db_data`)
  - `push.db`: Local application cache.
- `scripts/`: System management scripts.
  - `backup_r2.py`: **R2 Backup**.
  - `cleanup.py`: **Stateless Cleanup**.
  - `docker_entrypoint.sh`: Container entrypoint.
- `.env`: Environment variables (Secrets).
- `docker-compose.yml`: Service definition.

## 🚀 Quick Start (Deployment)

### 1. Start Services
```bash
docker compose up -d
```

### 2. Manual Run
```bash
# Standard run (Respects schedule)
docker exec -it push-service python main.py run all

# Force run (Bypass trading day/holiday checks)
docker exec -it push-service python main.py run all --force
```

## 🔄 Git Workflow (How to Update)

### 1. Update Code (Routine)
Runs on GitHub Actions, just pull locally.
```bash
git pull origin main
```

### 2. Deployment (On VPS)
Pull the latest image automatically built by GitHub.
```bash
docker pull ghcr.io/fenlynn/push:main
docker compose up -d
```

## ☁️ Cloud Native Architecture
- **Backup**: Automated to **Cloudflare R2** (`scripts/backup_r2.py`).
- **CI/CD**: GitHub Actions auto-builds Docker images to GHCR.
- **Stateless**: `scripts/cleanup.py` enforces 7-day retention for output/backups.

## 🧹 Maintenance
Files in `../push.bak` are legacy backups/junk and can be deleted after verification.
