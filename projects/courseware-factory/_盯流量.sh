#!/usr/bin/env bash
# 每 30 分钟拉一次流量快照，共 12 次（6 小时）
cd "$(dirname "$0")" || exit 1
PY="C:/Users/hua/AppData/Local/hermes/hermes-agent/venv/Scripts/python.exe"
export PYTHONIOENCODING=utf-8
for i in $(seq 1 12); do
  echo "########## 第 $i 次 $(date '+%m-%d %H:%M') ##########"
  "$PY" _看流量.py --diff 2>&1 | tail -30
  [ $i -lt 12 ] && sleep 1800
done
echo "########## 监控结束 $(date '+%m-%d %H:%M') ##########"
