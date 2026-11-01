#!/bin/bash
# 重启 WebUI（只杀 comm=python 的进程，避免误杀自己的 ssh shell）
export PATH=/root/miniconda3/bin:$PATH
for p in $(pgrep -f 'app[.]py'); do
  if [ "$(cat /proc/$p/comm 2>/dev/null)" = "python" ]; then
    kill "$p" 2>/dev/null && echo "killed $p"
  fi
done
sleep 2
mkdir -p /root/logs /root/outputs /root/uploads
cd /root/app || exit 1
nohup setsid /root/miniconda3/bin/python /root/app/app.py >> /root/logs/webui.log 2>&1 < /dev/null &
sleep 18
curl -sS -o /dev/null -w 'local 7860 -> %{http_code}\n' --max-time 8 http://127.0.0.1:7860/
