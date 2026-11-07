#!/usr/bin/env bash
# 发布第三轮 5 个课题到小红书（公开可见）。用法：bash _发布.sh
cd "$(dirname "$0")" || exit 1
PY="C:/Users/hua/AppData/Local/hermes/hermes-agent/venv/Scripts/python.exe"
PUB="C:/Users/hua/.pi/agent/skills/xhs-courseware-post/scripts/publish_post.py"
mkdir -p logs
export PYTHONIOENCODING=utf-8

TOPICS=(落叶小画布 花生壳小鸡 冬日黄昏 墙边的花 小草六种画法)

i=0
for t in "${TOPICS[@]}"; do
  i=$((i+1))
  echo "==================== [$i/${#TOPICS[@]}] $t  $(date +%H:%M:%S) ===================="
  for try in 1 2 3; do
    out=$("$PY" "$PUB" "项目/$t-4-6岁/post.json" --visibility public 2>&1)
    echo "$out"
    if echo "$out" | grep -q "✓ 完成"; then break; fi
    if echo "$out" | grep -q "未登录"; then
      echo "!! 登录接口抖动，等 20 秒重试 ($try/3)"; sleep 20; continue
    fi
    if echo "$out" | grep -q "同标题"; then
      echo "!! 同标题已存在，跳过"; break
    fi
    echo "!! 失败，等 25 秒重试 ($try/3)"; sleep 25
  done
  echo "---- 第 $i 条结束 $(date +%H:%M:%S) ----"
  if [ $i -lt ${#TOPICS[@]} ]; then sleep 45; fi
done
echo "======== ALL PUBLISH DONE $(date +%H:%M:%S) ========"
