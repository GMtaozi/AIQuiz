#!/usr/bin/env bash
# 数据库每日备份脚本 —— 由宿主机 cron 调用（容器内无 cron，遵循单一职责）
#
# 安装 crontab:
#   crontab -e
#   0 2 * * * /opt/AIQuiz/deploy/backup.sh >> /var/log/aiquiz-backup.log 2>&1
#
# 可选环境变量:
#   BACKUP_DIR      备份输出目录（默认 deploy/backups）
#   RETENTION_DAYS  备份保留天数（默认 14）
set -euo pipefail

COMPOSE_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKUP_DIR="${BACKUP_DIR:-$COMPOSE_DIR/backups}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"
DB_NAME="${POSTGRES_DB:-exam_system}"
DB_USER="${POSTGRES_USER:-postgres}"

mkdir -p "$BACKUP_DIR"
STAMP="$(date +%Y%m%d_%H%M%S)"
FILE="$BACKUP_DIR/${DB_NAME}_${STAMP}.sql.gz"

echo "[$(date '+%F %T')] 开始备份 $DB_NAME -> $FILE"
docker compose -f "$COMPOSE_DIR/docker-compose.yml" exec -T db \
  pg_dump -U "$DB_USER" "$DB_NAME" | gzip > "$FILE"
echo "[$(date '+%F %T')] 备份完成 ($(du -h "$FILE" | cut -f1))"

# 恢复方法（手动执行）:
#   gunzip -c <file>.sql.gz | docker compose exec -T db psql -U postgres exam_system

find "$BACKUP_DIR" -name "${DB_NAME}_*.sql.gz" -mtime +"$RETENTION_DAYS" -delete
echo "[$(date '+%F %T')] 已清理 ${RETENTION_DAYS} 天前的旧备份"
