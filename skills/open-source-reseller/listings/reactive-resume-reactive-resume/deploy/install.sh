#!/usr/bin/env bash
# 一键部署（Ubuntu/Debian 验证）。失败就照 docs/quickstart.md 手动做。
set -euo pipefail
cd "$(dirname "$0")"

command -v docker >/dev/null || { echo "先装 Docker: https://docs.docker.com/engine/install/"; exit 1; }
[ -f .env ] || cp .env.example .env
echo "→ 启动服务…"
docker compose up -d --build
sleep 5
docker compose ps
echo "→ 打开 http://127.0.0.1:8080 自检；日志：docker compose logs -f"
