#!/bin/bash
# 9 条范画链，3 个一组并行跑。日志 logs/tN.log
cd "C:/Users/hua/Documents/备份代码/小红书卖课件" || exit 1
export PYTHONIOENCODING=utf-8
PY="C:/Users/hua/AppData/Local/hermes/hermes-agent/venv/Scripts/python.exe"
mkdir -p logs

TOPICS=("树叶逃跑啦" "把秋天装进罐子" "路灯下的小猫" \
        "蚂蚁搬月亮" "黑白小甲虫的花园" "棉签点彩大树" \
        "纸杯长颈鹿" "会翻跟头的西瓜" "秋日小画合集")

n=0
while [ $n -lt 9 ]; do
  echo "=== 组 $((n/3+1)) 开始 $(date +%H:%M:%S) ==="
  pids=()
  for k in 0 1 2; do
    idx=$((n+k)); [ $idx -ge 9 ] && break
    t="${TOPICS[$idx]}"
    name=$(printf "t%d" $((idx+1)))
    ( "$PY" 工厂/pipeline.py "项目/${t}-4-6岁/project.json" --batch chain --no-ui \
        --ui-port $((18110+idx)) > "logs/${name}.log" 2>&1 ) &
    pids+=($!)
  done
  for p in "${pids[@]}"; do wait "$p"; done
  echo "=== 组 $((n/3+1)) 结束 $(date +%H:%M:%S) ==="
  n=$((n+3))
done
echo "ALL DONE $(date +%H:%M:%S)"
