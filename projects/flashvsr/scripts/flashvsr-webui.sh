#!/bin/bash
# /scripts/start.d/flashvsr-webui.sh —— 容器启动时由 PID 1 拉起（前台常驻，退出自动重启）
export PATH=/root/miniconda3/bin:/usr/local/cuda/bin:$PATH
export GRADIO_TEMP_DIR=/root/uploads
export TZ=Asia/Shanghai
export PYTHONUNBUFFERED=1
mkdir -p /root/logs /root/outputs /root/uploads
# 清掉 gradio 自己的临时上传目录（64 位十六进制名），不动用户放进去的文件
find /root/uploads -mindepth 1 -maxdepth 1 -type d -regextype posix-extended      -regex '.*/[0-9a-f]{64}' -exec rm -rf {} + 2>/dev/null
cd /root/app || exit 1

# 只允许一个实例（避免重复拉起抢 7860）
exec 9>/var/lock/flashvsr-webui.lock
flock -n 9 || { echo "[start.d] another instance holds the lock, skip" >> /root/logs/webui.log; exit 0; }

while true; do
  echo "[start.d] flashvsr webui launch $(date '+%F %T %Z')" >> /root/logs/webui.log
  /root/miniconda3/bin/python /root/app/app.py >> /root/logs/webui.log 2>&1
  echo "[start.d] exited rc=$? ; restart in 5s" >> /root/logs/webui.log
  sleep 5
done
