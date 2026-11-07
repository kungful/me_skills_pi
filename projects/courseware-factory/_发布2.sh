#!/usr/bin/env bash
# 等第一批 9 条发完，再发剩下 4 条（秋日小画合集 / 小兔子 / 小松鼠 / 小象）
cd "$(dirname "$0")" || exit 1
PY="C:/Users/hua/AppData/Local/hermes/hermes-agent/venv/Scripts/python.exe"
PUB="C:/Users/hua/.pi/agent/skills/xhs-courseware-post/scripts/publish_post.py"
export PYTHONIOENCODING=utf-8

# 等第一批结束（最多等 60 分钟）
for i in $(seq 1 240); do
  if grep -q "ALL PUBLISH DONE" logs/_pub.log 2>/dev/null; then break; fi
  sleep 15
done
echo "===== 第一批结束，开始第二批 $(date +%H:%M:%S) ====="

TOPICS=(秋日小画合集 小兔子吃萝卜 小松鼠藏松果 小象洗澡)
i=0
for t in "${TOPICS[@]}"; do
  i=$((i+1))
  echo "==================== [B$i/${#TOPICS[@]}] $t  $(date +%H:%M:%S) ===================="
  for try in 1 2 3; do
    out=$("$PY" "$PUB" "项目/$t-4-6岁/post.json" --visibility public 2>&1)
    echo "$out"
    if echo "$out" | grep -q "✓ 完成"; then break; fi
    if echo "$out" | grep -q "未登录"; then
      echo "!! 登录接口抖动，等 20 秒重试 ($try/3)"; sleep 20; continue
    fi
    if echo "$out" | grep -q "同标题"; then echo "!! 同标题已存在，跳过"; break; fi
    echo "!! 失败，等 25 秒重试 ($try/3)"; sleep 25
  done
  echo "---- 第 B$i 条结束 $(date +%H:%M:%S) ----"
  if [ $i -lt ${#TOPICS[@]} ]; then sleep 20; fi
done
echo "======== 第二批 ALL DONE $(date +%H:%M:%S) ========"
