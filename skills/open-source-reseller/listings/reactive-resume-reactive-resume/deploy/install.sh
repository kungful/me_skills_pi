#!/usr/bin/env bash
# 三条命令跑起来：bash install.sh
set -euo pipefail
cd "$(dirname "$0")"

command -v docker >/dev/null || { echo "先装 Docker：https://docs.docker.com/engine/install/"; exit 1; }
docker compose version >/dev/null || { echo "缺 compose 插件（docker compose v2）"; exit 1; }
docker info >/dev/null 2>&1 || { echo "Docker 没启动（Docker Desktop 打开了吗？）"; exit 1; }

if [ ! -f .env ]; then
  cp .env.example .env
  PW="$(head -c 18 /dev/urandom | od -An -tx1 | tr -d ' \n')"
  SECRET="$(head -c 32 /dev/urandom | od -An -tx1 | tr -d ' \n')"
  sed -i.bak "s/改成你的数据库密码/$PW/g; s/^AUTH_SECRET=\"\"/AUTH_SECRET=\"$SECRET\"/" .env && rm -f .env.bak
  echo "已生成 .env（随机数据库密码 + AUTH_SECRET）"
fi

echo "→ 拉镜像 + 启动（首次约 3–10 分钟，取决于网速）"
docker compose up -d --wait --wait-timeout 300

echo
echo "✅ 起来了： $(grep -E '^APP_URL' .env)"
echo "   看日志: docker compose logs --tail=50 reactive-resume"
echo "   停止:   docker compose down      （数据在 volume 里，不会丢）"
