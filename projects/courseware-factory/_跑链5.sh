#!/bin/bash
# 5 条范画链，3+2 两个一组并行跑。日志 logs/uN.log
cd "C:/Users/hua/Documents/备份代码/小红书卖课件" || exit 1
export PYTHONIOENCODING=utf-8
PY="C:/Users/hua/AppData/Local/hermes/hermes-agent/venv/Scripts/python.exe"
mkdir -p logs

TOPICS=("手指印仙人掌" "保鲜袋拓印花海" "线描青花瓷瓶" "撕纸小怪兽" "松果猫头鹰")

n=0
while [ $n -lt 5 ]; do
  echo "=== 组 $((n/3+1)) 开始 $(date +%H:%M:%S) ==="
  pids=()
  for k in 0 1 2; do
    idx=$((n+k)); [ $idx -ge 5 ] && break
    t="${TOPICS[$idx]}"
    name=$(printf "u%d" $((idx+1)))
    ( "$PY" 工厂/pipeline.py "项目/${t}-4-6岁/project.json" --batch chain --no-ui \
        --ui-port $((18160+idx)) > "logs/${name}.log" 2>&1 ) &
    pids+=($!)
  done
  for p in "${pids[@]}"; do wait "$p"; done
  echo "=== 组 $((n/3+1)) 结束 $(date +%H:%M:%S) ==="
  n=$((n+3))
done
echo "ALL DONE $(date +%H:%M:%S)"
