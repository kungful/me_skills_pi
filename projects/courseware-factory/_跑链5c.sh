#!/bin/bash
# 第四轮 5 条范画链，3+2 并行。日志 logs/wN.log
cd "C:/Users/hua/Documents/备份代码/小红书卖课件" || exit 1
export PYTHONIOENCODING=utf-8
PY="C:/Users/hua/AppData/Local/hermes/hermes-agent/venv/Scripts/python.exe"
mkdir -p logs

TOPICS=(撒盐画雪花 毛线小鱼 蒙德里安的花瓶 刮画蘑菇城堡 对折印蝴蝶)

n=0
while [ $n -lt 5 ]; do
  echo "=== 组 $((n/3+1)) 开始 $(date +%H:%M:%S) ==="
  pids=()
  for k in 0 1 2; do
    idx=$((n+k)); [ $idx -ge 5 ] && break
    t="${TOPICS[$idx]}"
    name=$(printf "w%d" $((idx+1)))
    ( "$PY" 工厂/pipeline.py "项目/${t}-4-6岁/project.json" --batch chain --no-ui \
        --ui-port $((18260+idx)) > "logs/${name}.log" 2>&1 ) &
    pids+=($!)
  done
  for p in "${pids[@]}"; do wait "$p"; done
  echo "=== 组 $((n/3+1)) 结束 $(date +%H:%M:%S) ==="
  n=$((n+3))
done
echo "ALL DONE $(date +%H:%M:%S)"
